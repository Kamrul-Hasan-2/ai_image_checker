"""
Vast AI Server - AI Image Checker
Replace Modal with FastAPI for Vast AI deployment
All services remain unchanged
"""

import os
import sys
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import base64
import io
import requests
from PIL import Image
import traceback
import asyncio
from image_loader import load_image_safe
from concurrent.futures import ThreadPoolExecutor

# Thread pool for running blocking CPU/IO work concurrently
_executor = ThreadPoolExecutor(max_workers=8)


# ---------------------------------------------------------------------------
# Request / Response models — makes /docs show a proper interactive form
# ---------------------------------------------------------------------------
class ImageItem(BaseModel):
    id: int = Field(..., example=1)
    position_id: int = Field(..., example=1)
    image: str = Field(..., example="https://cdn.bdstall.com/product-image/sample.jpg")

class ListingRequest(BaseModel):
    """id-only request body used by /image_checker and /weight_checker."""
    id: int = Field(..., example=141462, description="BDStall listing id")

class CheckRequest(BaseModel):
    """
    /image_checker accepts two shapes:

    * **id-only (preferred)** — `{"id": 141462}`. The listing's title, category,
      description and images are fetched from BDStall's `product_details` API,
      only images with `ai_verified` 0 or 1 are checked, and the response is
      `{"results": [{"image_id", "position_id", "error_id"}, ...]}` carrying one
      entry per error actually found.
    * **legacy full payload** — `{category, title, description, images: [...]}`,
      which still returns one flag object per image. Kept working so BDStall can
      switch over on its own schedule; `shipping_weight`/`weight_mismatch` live
      on /weight_checker now.
    """
    id: Optional[int] = Field(None, example=141462, description="BDStall listing id — send this alone for the id-only contract")
    category: Optional[str] = Field(None, example="laptop")
    title: Optional[str] = Field(None, example="HP EliteBook 840 G8")
    description: Optional[str] = Field(None, example="14 inch business laptop with Intel Core i5")
    image: Optional[str] = Field(None, description="Legacy single-image URL or base64")
    images: Optional[List[ImageItem]] = Field(None, example=[{"id": 1, "position_id": 1, "image": "https://cdn.bdstall.com/product-image/sample.jpg"}])
    pipeline: Optional[str] = Field("full", example="full")
    shipping_weight: Optional[float] = Field(None, example=0.4, description="Legacy seller-submitted shipping weight in kg — use /weight_checker instead")

# Weight sanity check: seller-submitted shipping_weight vs the product's known
# published weight. Error catalog entry (https://www.bdstall.com/api/item_ai/ai_error_list/):
# error_id 24 = "Weight differs from recorded product weight".
WEIGHT_MISMATCH_ERROR_ID = 24
WEIGHT_TOLERANCE_FACTOR  = 1.10  # allow up to 10% over the known product weight
# Shipping is never billed below 0.1 kg, so any weight the lookup returns under
# that is treated as 0.1 kg. Without this, a 0.03 kg item (SD card, cable) gives
# an allowed_max of 0.033 kg and a seller declaring the 0.1 kg minimum gets
# flagged for a weight they had no way to declare any lower.
MIN_SHIPPING_WEIGHT_KG = 0.1
# A percentage tolerance alone is far too tight on light items: 10% of a 0.15 kg
# estimate is 15 grams, which no real parcel can respect — a boxed 0.15 kg
# temperature meter genuinely ships at 0.25 kg once the carton, padding and the
# courier's rounded-up slab are counted, and sellers were being flagged for it.
# So allow a flat absolute slack as well and flag only when the declared weight
# clears BOTH limits. On heavy items the percentage is the larger of the two, so
# this changes nothing there — it only stops the nuisance flags on small goods.
WEIGHT_ABSOLUTE_SLACK_KG = 0.2


def _floor_weight_kg(value):
    """Raise a looked-up weight to the 0.1 kg shipping minimum; None stays None."""
    if value is None:
        return None
    return max(float(value), MIN_SHIPPING_WEIGHT_KG)


def _allowed_max_weight_kg(reference: float) -> float:
    """
    Highest shipping weight still accepted for a product estimated at `reference`
    kg — the more generous of the percentage tolerance and the absolute slack.
    """
    return max(reference * WEIGHT_TOLERANCE_FACTOR,
               reference + WEIGHT_ABSOLUTE_SLACK_KG)


# Market-price check: how far above the going rate a listing may sit before it
# is flagged. Wide on purpose — real shops differ on the same item by a third
# (warranty, import channel, stock age and bundled accessories all move the
# number), so only a price clear of this margin is worth a human's attention.
try:
    PRICE_TOLERANCE_PCT = float(os.environ["PRICE_TOLERANCE_PCT"])
except (KeyError, ValueError):
    PRICE_TOLERANCE_PCT = 0.25
# BDStall's error catalog has no price entry yet. Until one exists this stays
# unset and the response carries a verdict without claiming a catalog id — a
# made-up id would be filed against sellers under the wrong reason.
try:
    PRICE_MISMATCH_ERROR_ID = int(os.environ["PRICE_MISMATCH_ERROR_ID"])
except (KeyError, ValueError):
    PRICE_MISMATCH_ERROR_ID = None


def _fmt_bdt(value) -> str:
    """Format a price for human-facing prose — 3,800 — with no decimals."""
    return f"{float(value):,.0f}"


def _price_narration(our_price, market_price) -> str:
    """One plain sentence naming both numbers, for the seller to act on."""
    return (f"Listed at BDT {_fmt_bdt(our_price)}, above the BDT "
            f"{_fmt_bdt(market_price)} other shops in Bangladesh charge for it.")


def _fmt_kg(value) -> str:
    """Format a weight for human-facing prose — 3.2, 0.45, 200 — with no trailing zeros."""
    return f"{float(value):.3f}".rstrip("0").rstrip(".") or "0"


def _weight_narration(declared, estimated=None, category=None, category_max=None) -> Optional[str]:
    """
    One plain sentence explaining a weight mismatch.

    BDStall shows sellers Bangla text and builds its own message from
    declared_weight_kg/estimated_weight_kg, so this is a fallback only — it stays
    factual and free of advice.
    """
    if estimated is not None:
        direction = "above" if declared > estimated else "below"
        return (
            f"Declared shipping weight ({_fmt_kg(declared)} kg) is well {direction} the "
            f"estimated actual weight ({_fmt_kg(estimated)} kg) for this product."
        )
    if category_max is not None:
        return (
            f"Declared shipping weight ({_fmt_kg(declared)} kg) exceeds the maximum "
            f"plausible weight ({_fmt_kg(category_max)} kg) for a "
            f"{category or 'product'} listing."
        )
    return None


# Per-image check -> BDStall error_list id, for the id-only response. Mapped by
# field name, never by the flag's value: a soft screenshot flag sets
# screen_short=4, which would otherwise be misread as the watermark id.
# The tuple order is the order errors appear for a given image.
IMAGE_ERROR_IDS = (
    ("blur_image",        5),   # Blurry image
    ("watermark",         4),   # contains watermark or banner
    ("promotional_text",  3),   # Promotional text found
    ("screen_short",      8),   # Screenshot not allowed
    ("category_mismatch", 2),   # Wrong category image
    ("background_error",  6),   # Invalid background
    ("illegal",           9),   # Prohibited image
    ("stock_photo",      10),   # Stock image detected
)

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env before importing services so flags are set
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass  # dotenv optional — values can be set as real env vars

# Lightweight services used by the weight-only request path. Heavy image/ML
# modules are imported by _load_image_dependencies() only when image_checker is
# actually called.
from gemini_service import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    estimate_known_product_weight_kg as gemini_estimate_weight_kg,
)
from gemini_price_service import (
    estimate_market_price_bdt as gemini_estimate_market_price,
)
from bdstall_api import (
    ProductDetailsError,
    fetch_product_details,
    listing_images_pending_check,
    listing_shipping_weight_kg,
)

QualityCheckService = None
OCRService = None
CLIPService = None
USE_QWEN2VL = False
GROQ_API_KEY = ""
GROQ_MODEL = ""
get_qwen_service = None
groq_moderate_image = None
estimate_known_product_weight_kg = None
plausible_max_weight_kg = None
compute_screenshot_score = None
apply_screenshot_decision = None
detect_promotional_text = None
detect_watermark_visual = None


def _load_image_dependencies() -> None:
    """Import image/ML modules exactly once, on the first image request."""
    global QualityCheckService, OCRService, CLIPService
    global USE_QWEN2VL, GROQ_API_KEY, GROQ_MODEL
    global get_qwen_service, groq_moderate_image, estimate_known_product_weight_kg
    global plausible_max_weight_kg, compute_screenshot_score, apply_screenshot_decision
    global detect_promotional_text, detect_watermark_visual

    if QualityCheckService is not None:
        return

    from quality_service import QualityCheckService as quality_service_class
    from ocr_service import OCRService as ocr_service_class
    from clip_service import CLIPService as clip_service_class
    from qwen_service import (
        USE_QWEN2VL as use_qwen2vl,
        GROQ_API_KEY as groq_api_key,
        GROQ_MODEL as groq_model,
        get_qwen_service as qwen_service_factory,
        groq_moderate_image as groq_image_moderator,
        estimate_known_product_weight_kg as groq_weight_lookup,
    )
    from weight_reference import plausible_max_weight_kg as category_weight_ceiling
    from screenshot_detector import compute_screenshot_score as screenshot_score
    from screenshot_detector import apply_screenshot_decision as screenshot_decision
    from promotional_detector import detect_promotional_text as promo_detector
    from watermark_detector import detect_watermark_visual as watermark_detector

    QualityCheckService = quality_service_class
    OCRService = ocr_service_class
    CLIPService = clip_service_class
    USE_QWEN2VL = use_qwen2vl
    GROQ_API_KEY = groq_api_key
    GROQ_MODEL = groq_model
    get_qwen_service = qwen_service_factory
    groq_moderate_image = groq_image_moderator
    estimate_known_product_weight_kg = groq_weight_lookup
    plausible_max_weight_kg = category_weight_ceiling
    compute_screenshot_score = screenshot_score
    apply_screenshot_decision = screenshot_decision
    detect_promotional_text = promo_detector
    detect_watermark_visual = watermark_detector

# Create FastAPI app
app = FastAPI(
    title="AI Image Checker",
    version="1.0.0",
    description="AI-powered image quality and content moderation API",
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS — allow all origins so /docs Swagger UI and external callers work
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global service instances
image_checker = None
_image_checker_init_lock = None


class ImageChecker:
    """Image Checker Service"""
    
    def __init__(self):
        """Initialize all services"""
        print("Initializing services...")
        _load_image_dependencies()
        
        # Set environment variables
        os.environ["TRANSFORMERS_CACHE"] = os.path.expanduser("~/.cache/huggingface")
        os.environ["HF_HOME"] = os.path.expanduser("~/.cache/huggingface")
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        
        try:
            self.quality_service = QualityCheckService()
            self.ocr_service = OCRService(languages=['en'])
            self.clip_service = CLIPService(model_name="openai/clip-vit-base-patch32")

            # Qwen2-VL local model — only load when USE_QWEN2VL=True in .env
            self.qwen2b_service = get_qwen_service()
            if self.qwen2b_service:
                print("✅ Qwen2-VL local model loaded")
            else:
                print("⏭️  Qwen2-VL disabled (USE_QWEN2VL=False)")

            if GROQ_API_KEY:
                print(f"✅ Groq API configured (model: {GROQ_MODEL})")
            else:
                print("⏭️  Groq API not configured (GROQ_API_KEY not set)")

            provider = self._weight_lookup_provider()
            if provider:
                name = provider[0]
                model = GEMINI_MODEL if name == "gemini" else GROQ_MODEL
                print(f"✅ Weight lookup: {name} (model: {model})")
            else:
                print("⏭️  Weight lookup disabled — no GEMINI_API_KEY or GROQ_API_KEY")

            print("✅ All services initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing services: {e}")
            raise
    
    def load_image(self, image_input: str) -> Image.Image:
        """Load image from URL or base64 (SSRF-guarded, size-capped, data-URL safe)."""
        return load_image_safe(image_input)
    
    async def process_single_image(self, image_input: str, category: str, pipeline_mode: str, title: str = None, description: str = None, image_id: int = None, position_id: int = None) -> Dict[str, Any]:
        """
        Process a single image through the AI pipeline
        
        Args:
            image_input: Image URL or base64 string
            category: Product category
            pipeline_mode: Processing mode (full/fast)
            title: Optional product title to match against OCR text
            description: Optional product description to match against OCR text
            image_id: Optional image ID to include in response
            position_id: Optional position ID to include in response
        """
        # Exception categories where promotional_text is always 0.
        # Vehicle and real-estate listings legitimately contain price, phone,
        # and location text as part of the product description — not promotions.
        exception_categories = [
            "car", "car accessories",
            "bike", "bike accessories",
            "three wheeler", "bicycle", "bicycle accessories",
            "commercial vehicle", "rental", "vehicle equipment",
            "real estate", "realestate", "property", "apartment",
            "flat", "land", "plot", "house", "office space",
            "commercial property", "residential property",
            "cow", "cattle", "livestock", "poultry", "goat", "sheep",
            "buffalo", "animal", "pet", "bird", "fish",
        ]
        # Real-estate category names vary widely; use substring matching so
        # "Residential Real Estate", "Real Estate & Property", etc. all match.
        _real_estate_keywords = ("real estate", "realestate", "property", "apartment",
                                 "flat", "plot", "house", "office space")
        _livestock_keywords = ("cow", "cattle", "livestock", "poultry", "goat", "sheep",
                               "buffalo", "animal", "pet", "bird", "fish")
        _cat_lower = category.lower().strip()
        is_exception_category = (
            _cat_lower in exception_categories
            or any(kw in _cat_lower for kw in _real_estate_keywords)
            or any(kw in _cat_lower for kw in _livestock_keywords)
        )
        
        debug_info = {}
        
        try:
            print(f"\n🔍 Processing image (ID: {image_id}, Position: {position_id})")
            print(f"   Category: {category}, Title: {title}, Description: {description}")
            
            loop = asyncio.get_event_loop()

            # Download image
            image = await loop.run_in_executor(_executor, self.load_image, image_input)
            print(f"✅ Image loaded: {image.size}")

            # Resize copy for OCR/CLIP (quality check needs full resolution)
            max_size = 800
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image_small = image.resize(new_size, Image.Resampling.LANCZOS)
            else:
                image_small = image

            # Quality check (full res) + OCR (small) — run concurrently
            quality_result, ocr_result = await asyncio.gather(
                loop.run_in_executor(_executor, self.quality_service.check_image, image),
                loop.run_in_executor(_executor, self.ocr_service.extract_text, image_small),
            )
            image = image_small  # switch to small image for remaining steps

            opencv_risk           = quality_result.get("opencv_risk", 0.0)
            screenshot_confidence = quality_result.get("screenshot_confidence", 0.0)
            blur_confidence       = quality_result.get("blur_confidence", 0.0)
            print(f"✅ Quality+OCR done - blur: {blur_confidence:.2f}, text: {ocr_result.get('full_text','')[:40]}...")
            ocr_risk = ocr_result.get("ocr_risk", 0.0)
            watermark_confidence_ocr = ocr_result.get("watermark_confidence", 0.0)
            promo_confidence_ocr = ocr_result.get("promotional_confidence", 0.0)
            watermark_keywords = ocr_result.get("watermark_keywords_found", False)
            seller_watermark = ocr_result.get("seller_watermark_found", False)
            bd_marketplace = ocr_result.get("bd_marketplace_watermark", False)
            has_price = ocr_result.get("has_price", False)
            has_phone_number = ocr_result.get("has_phone_number", False)
            has_ecommerce_ui = ocr_result.get("has_ecommerce_ui", False)
            has_link = ocr_result.get("has_link", False)
            promotional_detected_ocr = ocr_result.get("promotional_detected", False)
            
            print(f"✅ OCR done - text: {ocr_result.get('full_text', '')[:50]}..., promo conf: {promo_confidence_ocr:.2f}")
            
            # NEW: Visual promo indicators
            visual_promo_score = ocr_result.get("visual_promo_score", 0.0)
            strong_price_indicator = ocr_result.get("strong_price_indicator", False)
            has_button_ui = ocr_result.get("has_button_ui", False)
            has_promotional_sticker = ocr_result.get("has_promotional_sticker", False)
            digit_count = ocr_result.get("digit_count", 0)
            
            # Vocabulary-aware promotional text detection
            # Runs BEFORE product-photo guard so the guard can see a trustworthy signal.
            promo_detection = detect_promotional_text(
                ocr_extracted_data=ocr_result.get("extracted_data", []),
                full_ocr_text=ocr_result.get("full_text", ""),
                title=title or "",
                description=description or "",
                category=category,
                image_id=image_id or 0,
            )
            promotional_detected_ocr = promo_detection["is_promotional"]
            promo_detection_confidence = promo_detection["confidence_score"]
            print(f"✅ Promo detector: is_promotional={promotional_detected_ocr}, confidence={promo_detection_confidence}")

            # If the vocabulary-aware detector found zero promotional patterns,
            # the OCR sticker heuristic is a false positive — clear it.
            # The sticker detector cannot distinguish "www.apc.com" printed on the
            # device body from a seller overlay sticker; the vocab detector can.
            if promo_detection_confidence == 0 and not promotional_detected_ocr:
                has_promotional_sticker = False

            # CLIP product check + body verification — run both concurrently
            # Use a 224px image for CLIP (its native resolution — no quality loss)
            clip_img = image.resize((224, 224), Image.Resampling.BILINEAR)
            has_title_or_description = bool(title or description)

            if has_title_or_description:
                product_check, body_verification = await asyncio.gather(
                    loop.run_in_executor(_executor, self.clip_service.detect_product_photo, clip_img),
                    loop.run_in_executor(_executor, self.clip_service.verify_image_body_content,
                                         clip_img, title or "", description or ""),
                )
                image_body_match      = body_verification.get("body_matches", False)
                body_match_confidence = body_verification.get("confidence", 0.0)
            else:
                product_check = await loop.run_in_executor(
                    _executor, self.clip_service.detect_product_photo, clip_img
                )
                image_body_match      = False
                body_match_confidence = 0.0

            is_product_photo        = product_check.get("is_product_photo", False)
            product_photo_confidence = product_check.get("product_score", 0.0)
            print(f"✅ CLIP done: product={is_product_photo}({product_photo_confidence:.2f}), body_match={image_body_match}({body_match_confidence:.2f})")
            
            # NEW STEP 2: Check if product title/description matches OCR text
            # If title/description provided but doesn't match OCR = PROMOTIONAL (mismatch)
            is_title_match = False
            title_description_mismatch = False
            
            if has_title_or_description:
                full_text = ocr_result.get("full_text", "").lower()
                
                # Combine title and description for matching
                combined_text = ""
                if title:
                    combined_text += title.lower().strip() + " "
                if description:
                    combined_text += description.lower().strip()
                
                combined_text = combined_text.strip()
                
                # Check if title/description words appear in OCR text (fuzzy match)
                product_words = [w for w in combined_text.split() if len(w) > 1]  # Filter short words (>1 char)
                # Consider match if >= 60% of significant product words found in OCR text
                if len(product_words) > 0:
                    matched_words = sum(1 for word in product_words if word in full_text)
                    match_ratio = matched_words / len(product_words)
                    is_title_match = match_ratio >= 0.6
                    
                    print(f"✅ Title match: {is_title_match} ({matched_words}/{len(product_words)} words matched)")
                    print(f"   OCR text: {full_text[:50]}...")
                    print(f"   Product words: {product_words}")
                    
                    # If title/description provided but doesn't match OCR = MISMATCH
                    if not is_title_match and len(full_text) > 10:  # Only if OCR has meaningful text
                        title_description_mismatch = True
                        print(f"⚠️  Title/Description MISMATCH detected")
            
            # CLIP analysis (skipped for speed - can be enabled if needed)
            clip_risk = 0.0

            # Qwen/Groq scores initialised here — set later in watermark block
            qwen_risk = 0.0
            qwen_promo_score = 0.0
            qwen_watermark_score = 0.0
            qwen_illegal_score = 0.0
            
            # Calculate final scores - only flag clear mobile UI screenshots
            screenshot_detected = screenshot_confidence > 0.90

            # OCR + CLIP based screenshot detection (catches web/app screenshots
            # that pass the OpenCV mobile-UI check above)
            img_w, img_h = image.size
            ocr_screenshot = compute_screenshot_score(ocr_result, product_check, img_w, img_h)
            if ocr_screenshot["is_screenshot"]:
                screenshot_detected = True
                print(f"📸 Screenshot detected by OCR scorer: score={ocr_screenshot['screenshot_score']:.2f}, reasons={ocr_screenshot['reasons']}")
            elif ocr_screenshot["flag_for_review"]:
                print(f"⚠️  Possible screenshot (flag): score={ocr_screenshot['screenshot_score']:.2f}, reasons={ocr_screenshot['reasons']}")

            # Blur: trust the blur check result directly so the caller uses the
            # same decision the quality service already made.
            blur_conf = quality_result.get("blur_confidence", 0.0)
            blur_detected = not quality_result['checks']['blur']['passed']
            
            # ── DYNAMIC VISUAL WATERMARK DETECTION ───────────────────────────────
            # Run watermark detection + Groq (if enabled) concurrently
            wm_fn = lambda: detect_watermark_visual(image, is_product_photo, product_photo_confidence)

            if self.qwen2b_service:
                visual_wm, qwen_raw = await asyncio.gather(
                    loop.run_in_executor(_executor, wm_fn),
                    loop.run_in_executor(_executor, self.qwen2b_service.moderate_image, image),
                )
            elif GROQ_API_KEY:
                visual_wm, qwen_raw = await asyncio.gather(
                    loop.run_in_executor(_executor, wm_fn),
                    loop.run_in_executor(_executor, groq_moderate_image, image),
                )
            else:
                visual_wm = await loop.run_in_executor(_executor, wm_fn)
                qwen_raw  = None

            if qwen_raw:
                qwen_risk            = 1.0 if qwen_raw.get("decision") == "BLOCK" else 0.0
                qwen_promo_score     = 1.0 if qwen_raw.get("is_promotional") else 0.0
                qwen_watermark_score = 1.0 if qwen_raw.get("has_watermark") else 0.0
                qwen_illegal_score   = 1.0 if "illegal_content" in qwen_raw.get("violations", []) else 0.0

            visual_watermark_detected = visual_wm["is_visual_watermark"]
            print(f"✅ Visual watermark: score={visual_wm['visual_watermark_score']:.3f}, "
                  f"detected={visual_watermark_detected}, signals={visual_wm['signal_scores']}")

            # ── KEYWORD-BASED WATERMARK DETECTION ────────────────────────────────
            # Catches known marketplaces (bikroy, daraz, bdstall, shutterstock…)
            # Seller shop overlays are excluded for product photos since keywords like
            # "shop", "store", "house", "mart" are common in product names.
            watermark_risk = ocr_risk * watermark_confidence_ocr
            # Explicit, high-precision string matches (marketplace domain / stock-photo
            # or Watermarkly phrase) — these are trusted unconditionally.
            strong_keyword_watermark = watermark_keywords or bd_marketplace
            if is_product_photo and product_photo_confidence > 0.30:
                # For confirmed products: only explicit watermarks or BD marketplace matter
                # seller_watermark produces too many false positives ("Mobile Shop Display" etc.)
                weak_keyword_watermark = False
            else:
                # For non-products: apply full watermark check including seller text
                weak_keyword_watermark = watermark_risk > 0.2 or seller_watermark

            # ── VISION-MODEL VETO ─────────────────────────────────────────────────
            # Qwen/Groq actually looks at the image; the OpenCV visual detector and the
            # generic seller-keyword match are proxies that can misfire on ordinary
            # glare, backdrops, or brand/business text. When the vision model ran and
            # confidently reports no watermark, don't let those weak/proxy signals alone
            # flip the result — but never override a strong, precise keyword match.
            if qwen_raw is not None and qwen_raw.get("_moderation_ok", True) and not qwen_raw.get("has_watermark", False):
                if weak_keyword_watermark or visual_watermark_detected:
                    print("ℹ️  Vision-model veto: no watermark seen, ignoring weak heuristic signal(s)")
                weak_keyword_watermark = False
                visual_watermark_detected = False

            keyword_watermark = strong_keyword_watermark or weak_keyword_watermark

            # Final watermark decision: keyword OR visual — either is sufficient
            # For product photos, visual detector uses a higher threshold (see watermark_detector.py)
            watermark_detected = keyword_watermark or visual_watermark_detected
            
            # Check if product text only (from OCR)
            is_product_text_only = ocr_result.get("is_product_text_only", False)
            
            # ========================================================================
            # PROMOTIONAL DETECTION LOGIC - CRITICAL FOR PRODUCT IMAGES
            # ========================================================================
            # Five-tier detection system:
            #
            # 0. STRONG SIGNAL OVERRIDE (HIGHEST PRIORITY — checked before anything else):
            #    - Any BD phone number found in the image (017/013/014/015/016/018/019...,
            #      +880/+88 prefixed, or Bengali digits) = PROMOTIONAL, no exceptions.
            #    - Any website/social link found (www., .com, .net, .bd, .org, fb.com,
            #      whatsapp, telegram, imo, viber, messenger, ...) = PROMOTIONAL, no exceptions.
            #    - Also: promotional sticker, or e-commerce UI + real price.
            #    - This overrides "looks like a product photo" — a seller's phone number
            #      or website overlaid on a genuine product photo is still promotional.
            #
            # 1. VISUAL PRODUCT DETECTION (CLIP-based):
            #    - If image shows actual product (e.g., camera in box, phone on table)
            #    - Text on product/packaging is NOT promotional
            #    - Example: "Imou 3K 5MP" on camera box = SAFE
            #    - Even if text contains specs/model numbers = SAFE
            #
            # 2. TEXT-ONLY PRODUCT DETECTION (OCR-based):
            #    - If text has NO price, phone, link, or e-commerce UI
            #    - AND no strong sale terms (buy now, discount, etc.)
            #    - Then it's likely just product branding = SAFE
            #    - Example: "Samsung Galaxy A54" without price = SAFE
            #
            # 3. PRODUCT TITLE MATCHING:
            #    - If product title provided and matches OCR text (>= 60% words match)
            #    - Text is the product name/description = NOT promotional
            #    - Example: Title "Dell Inspiron 15" matches "Dell Inspiron 15 3000" in OCR
            #
            # 4. PROMOTIONAL SIGNALS (Multi-signal fallback):
            #    - Price + phone = PROMOTIONAL
            #    - E-commerce UI buttons = PROMOTIONAL
            #    - Contact info = PROMOTIONAL
            #
            # Priority: Strong override > Visual detection > Text detection > Title match > Signal detection
            #
            # NOTE: "car/bike/real estate/livestock" categories are exempt entirely
            # (see exception_categories below) — phone numbers are legitimate contact
            # info in those listings and are never flagged.
            # ========================================================================
            
            # Promotional detection - RESPECT product title and photo flags
            # NEW LOGIC: Verify image body matches product FIRST, then check promotional signals
            # PRIORITY ORDER: product_photo > image_body_match > product_text_only > title_match > signals
            promo_risk = promo_confidence_ocr
            
            # Check for VERY STRONG promotional signals first (overrides everything)
            # These are clear promotional indicators that should be detected even on product photos.
            # A phone number or a link/website (www./.com/.net/.bd/.org/social handles) by itself is
            # treated as decisive: real product photos legitimately carry model numbers/specs, but a
            # BD mobile number (017/013/014/... or +88...) or a website/social link overlaid on an
            # image is always seller contact info — never legitimate product text.
            # strong_price_indicator requires a currency symbol (৳, $, ₹) or a
            # comma-formatted number (e.g. 24,999). This excludes bare model
            # numbers like "1500" on a UPS or "600D" on a camera.
            very_strong_promo = (
                has_phone_number or                                # Any BD phone number = clear promo (seller contact overlay)
                has_link or                                        # Any website/social link = clear promo (www./.com/.net/.bd/fb/whatsapp...)
                (has_ecommerce_ui and strong_price_indicator) or  # E-commerce UI + real price = clear promo
                has_promotional_sticker                           # Promotional sticker on product
            )

            # HIGHEST PRIORITY: very strong promotional signals (phone number, link, etc.)
            # override every other check below — including "this looks like a real
            # product photo", since a seller's phone number/website overlaid on an
            # otherwise genuine product photo is still promotional content.
            if very_strong_promo:
                promotional_detected = True
                promo_risk = 0.95
                print(f"⚠️  Promotional check: STRONG PROMO signals (phone/link/price+ui/sticker) → PROMOTIONAL")
            # SECOND PRIORITY: Product photo detection (CLIP-based)
            # If CLIP detects it's a product photo, text is part of product, NOT promotional
            elif is_product_photo and product_photo_confidence > 0.30:
                # Product photo = text on product is specs/branding, NOT promotional
                promotional_detected = False
                promo_risk = 0.0
                print(f"✅ Promotional check: PRODUCT PHOTO detected → NOT promotional")
            # THIRD PRIORITY: Image body verification with lower threshold
            # If image shows the actual product body (e.g., RAM module, phone, camera)
            elif image_body_match and body_match_confidence > 0.20:
                # Product body shown = text is definitely product specs, NOT promotional
                promotional_detected = False
                promo_risk = 0.0
                print(f"✅ Promotional check: BODY MATCH detected → NOT promotional")
            # FOURTH PRIORITY: Product text-only detection (OCR-based)
            # If text has absolutely NO promotional signals (no price, no phone, no UI)
            elif is_product_text_only:
                # No promotional signals = safe to assume it's product info
                promotional_detected = False
                promo_risk = 0.0
                print(f"✅ Promotional check: PRODUCT TEXT ONLY → NOT promotional")
            # FIFTH PRIORITY: Title/Description matching
            # If product title/description provided AND matches OCR text
            elif is_title_match and not title_description_mismatch:
                # Title matches = text is product name/specs, NOT promotional
                promotional_detected = False
                promo_risk = 0.0
                print(f"✅ Promotional check: TITLE MATCH → NOT promotional")
            # FALLBACK: Multi-signal promotional detection
            else:
                # Use multi-signal detection
                # Promotional if: (has_price AND has_phone) OR has_ecommerce_ui OR has_button_ui
                promotional_detected = (
                    (has_price and has_phone_number) or 
                    has_ecommerce_ui or 
                    has_button_ui
                ) or promotional_detected_ocr
                
                print(f"✅ Promotional check: MULTI-SIGNAL detection")
                print(f"   price={has_price}, phone={has_phone_number}, ecom_ui={has_ecommerce_ui}, button_ui={has_button_ui}")
                print(f"   promo_sticker={has_promotional_sticker}, ocr_promo={promotional_detected_ocr}")
                print(f"   Result: promotional_detected={promotional_detected}")
                
                # Boost risk using vocabulary-aware confidence score
                if promo_detection_confidence >= 50:
                    promo_risk = min(0.9, promo_risk + promo_detection_confidence / 100.0)
                elif has_price and has_phone_number:
                    promo_risk = min(0.9, promo_risk + 0.3)
                if has_ecommerce_ui or has_button_ui:
                    promo_risk = min(0.9, promo_risk + 0.2)
            
            # Set promotional_text to 0 for exception categories
            promotional_text = 0 if is_exception_category else (1 if promotional_detected else 0)
            
            print(f"\n📊 FINAL RESULT:")
            print(f"   blur: {5 if blur_detected else 0}, screenshot: {8 if screenshot_detected else 0}")
            print(f"   category_mismatch: 0, promotional: {3 if promotional_text else 0}")
            print(f"   watermark: {4 if watermark_detected else 0}")
            print(f"   risk_level: {max((5 if blur_detected else 0), (8 if screenshot_detected else 0), (3 if promotional_text else 0), (4 if watermark_detected else 0))}")
            print()
            
            # Build result
            result = {
                "blur_image": 5 if blur_detected else 0,
                "screen_short": 8 if screenshot_detected else 0,
                "category_mismatch":  0,
                "illegal": 0,
                "promotional_text": 3 if promotional_text else 0,
                "stock_photo": 0,
                "watermark": 4 if watermark_detected else 0,
                "risk_level": max(
                    (5 if blur_detected else 0),
                    (8 if screenshot_detected else 0),
                    (3 if promotional_text else 0),
                    (4 if watermark_detected else 0),
                )
            }
            
            # Add id and position_id if provided
            if image_id is not None:
                result["id"] = image_id
            if position_id is not None:
                result["position_id"] = position_id
            
            result.update({
                "_debug": {
                    "image_body_match": image_body_match,
                    "body_match_confidence": body_match_confidence,
                    "is_product_photo": is_product_photo,
                    "is_title_match": is_title_match,
                    "has_promotional_sticker": has_promotional_sticker,
                    "promotional_detected": promotional_detected,
                    "promo_detector_confidence": promo_detection_confidence,
                    "promo_detector_flags": [h["type"] for h in promo_detection.get("promotional_flags", [])],
                    "promo_detector_reason": promo_detection.get("reason", ""),
                    "promo_unmatched_tokens": promo_detection.get("unmatched_texts", [])[:10],
                    "watermark_keyword": keyword_watermark,
                    "watermark_visual_score": visual_wm["visual_watermark_score"],
                    "watermark_visual_signals": visual_wm["signal_scores"],
                    "watermark_visual_reasons": visual_wm["reasons"],
                }
            })

            # Apply OCR-based screenshot score (upgrades screen_short and risk_level
            # for web/app screenshots that slipped past the OpenCV mobile-UI check)
            result = apply_screenshot_decision(result, ocr_screenshot)

            return result
            
        except Exception as e:
            # Build error result with id and position_id first (if provided)
            print(f"❌ ERROR processing image: {str(e)}")
            import traceback as tb
            print(tb.format_exc())
            
            error_result = {}
            
            # Add id and position_id at the beginning if provided
            if image_id is not None:
                error_result["id"] = image_id
            if position_id is not None:
                error_result["position_id"] = position_id
            
            # Add the rest of the error fields
            error_result.update({
                "error": str(e),
                "blur_image": 0,
                "screen_short": 0,
                "category_mismatch": 0,
                "illegal": 0,
                "promotional_text": 0,
                "stock_photo": 0,
                "watermark": 0,
                "risk_level": 0
            })
            
            return error_result

    @staticmethod
    def _weight_lookup_provider():
        """
        (name, fn) for the product-weight lookup, or None when neither provider
        is configured. Gemini wins when its key is set — it returns a packaged
        weight alongside the net one, which is what the seller's declared
        shipping weight is actually comparable to.
        """
        if GEMINI_API_KEY:
            return "gemini", gemini_estimate_weight_kg
        if GROQ_API_KEY:
            return "groq", estimate_known_product_weight_kg
        return None

    async def _check_shipping_weight(
        self, shipping_weight, title, category, description
    ) -> Dict[str, Any]:
        """
        Two-layer check on a seller-submitted shipping_weight (kg):

        1. AI lookup of the *specific* product's known published weight (Gemini
           when GEMINI_API_KEY is set, else Groq; text-only). Precise: flags when
           the given weight exceeds the product's packaged weight — or its net
           weight, whichever the model knows and whichever is higher — plus a 10%
           tolerance. Only fires on a confident, named-model match.
        2. Fallback: when the AI doesn't recognize the specific model (generic/
           no-name listings — most of the catalog), fall back to a category-level
           plausibility ceiling so obviously wrong values (e.g. 350kg for a
           Bluetooth speaker) still get caught instead of silently passing.

        Both layers are fail-open: an unrecognized product AND an unrecognized
        category means no reference point exists, so nothing is flagged.
        """
        if shipping_weight is None:
            return {"weight_mismatch": 0}

        # Kept outside the block below so the category-ceiling layer can still
        # report an advisory estimate when the exact model wasn't recognized.
        typical_weight = None

        provider = self._weight_lookup_provider()
        if title and provider:
            provider_name, lookup_fn = provider
            loop = asyncio.get_event_loop()
            weight_info = await loop.run_in_executor(
                _executor, lookup_fn, title, category, description
            )
            known_weight    = _floor_weight_kg(weight_info.get("known_weight_kg"))
            packaged_weight = _floor_weight_kg(weight_info.get("packaged_weight_kg"))
            typical_weight  = _floor_weight_kg(weight_info.get("typical_weight_kg"))

            if weight_info.get("_lookup_ok") and known_weight is not None:
                # Sellers declare a *shipping* weight, so the ceiling should be the
                # packaged weight when the model knows it — measuring a boxed item
                # against its bare net weight is what produced false flags. max()
                # means this only ever widens the allowance: nothing gets flagged
                # here that the net-weight rule wouldn't have flagged too.
                reference   = max(known_weight, packaged_weight or 0)
                allowed_max = _allowed_max_weight_kg(reference)
                exceeded    = shipping_weight > allowed_max

                print(f"⚖️  Weight check (model-specific via {provider_name}): "
                      f"given={shipping_weight}kg, net≈{known_weight}kg, "
                      f"packaged≈{packaged_weight}kg "
                      f"(confidence={weight_info.get('confidence')}), "
                      f"allowed_max={allowed_max:.3f}kg, exceeded={exceeded}")

                # What we believe the listing actually weighs, for the seller to
                # correct towards. The packaged figure is the like-for-like
                # comparison to a declared shipping weight.
                estimated = packaged_weight or known_weight

                return {
                    "weight_mismatch": WEIGHT_MISMATCH_ERROR_ID if exceeded else 0,
                    "declared_weight_kg": shipping_weight,
                    "estimated_weight_kg": round(estimated, 3),
                    "narration": _weight_narration(shipping_weight, estimated) if exceeded else None,
                    "_debug": {
                        "weight_check_method": "ai_known_weight",
                        "weight_lookup_provider": provider_name,
                        "given_shipping_weight_kg": shipping_weight,
                        "known_product_weight_kg": known_weight,
                        "packaged_product_weight_kg": packaged_weight,
                        "allowed_max_weight_kg": round(allowed_max, 3),
                        "weight_confidence": weight_info.get("confidence"),
                    },
                }

        # Fallback: AI doesn't know this specific product — use a category-level
        # plausibility ceiling instead of skipping the check entirely.
        category_max = plausible_max_weight_kg(category)
        if category_max is not None and shipping_weight > category_max:
            print(f"⚖️  Weight check (category sanity): given={shipping_weight}kg exceeds "
                  f"plausible ceiling {category_max}kg for category='{category}'")
            return {
                "weight_mismatch": WEIGHT_MISMATCH_ERROR_ID,
                "declared_weight_kg": shipping_weight,
                # The exact model wasn't recognized, so this is a type-level
                # estimate — advisory, and not what triggered the flag.
                "estimated_weight_kg": round(typical_weight, 3) if typical_weight else None,
                "narration": _weight_narration(
                    shipping_weight,
                    estimated=typical_weight,
                    category=category,
                    category_max=category_max,
                ),
                "_debug": {
                    "weight_check_method": "category_sanity_range",
                    "given_shipping_weight_kg": shipping_weight,
                    "category_max_plausible_kg": category_max,
                    "typical_product_weight_kg": typical_weight,
                },
            }

        return {"weight_mismatch": 0, "declared_weight_kg": shipping_weight}

    @staticmethod
    def _apply_weight_check(results: List[Any], weight_check: Dict[str, Any]) -> None:
        """Merge the once-per-request weight check onto every per-image result dict."""
        error_id = weight_check.get("weight_mismatch", 0)
        debug_info = weight_check.get("_debug")
        for r in results:
            if not isinstance(r, dict):
                continue
            r["weight_mismatch"] = error_id
            if error_id:
                r["risk_level"] = max(r.get("risk_level", 0), error_id)
            if debug_info:
                r.setdefault("_debug", {}).update(debug_info)

    async def check_image(self, job_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main handler - processes multiple images in parallel.
        """
        try:
            pipeline_mode    = job_input.get("pipeline", "full")
            common_category  = job_input.get("category", "unknown")
            common_title     = job_input.get("title")
            common_description = job_input.get("description")
            shipping_weight  = job_input.get("shipping_weight")

            # Multiple images — process ALL concurrently
            if "images" in job_input:
                images_list = job_input.get("images", [])
                if not images_list:
                    return {"error": "No images provided"}

                # Product-level weight check runs in the same gather() as the
                # per-image tasks so it doesn't add sequential latency.
                tasks = [self._check_shipping_weight(
                    shipping_weight, common_title, common_category, common_description
                )]
                for img_data in images_list:
                    image_input = img_data.get("image")
                    category    = img_data.get("category", common_category)
                    title       = img_data.get("title", common_title)
                    description = img_data.get("description", common_description)
                    image_id    = img_data.get("id")
                    position_id = img_data.get("position_id")

                    if not image_input:
                        err = {}
                        if image_id   is not None: err["id"]          = image_id
                        if position_id is not None: err["position_id"] = position_id
                        err.update({"error": "No image URL provided", "risk_level": 0})
                        async def _err(e=err):
                            return e
                        tasks.append(_err())
                    else:
                        tasks.append(self.process_single_image(
                            image_input, category, pipeline_mode,
                            title, description, image_id, position_id
                        ))

                # All images (+ the weight check) run at the same time
                weight_check, *results = await asyncio.gather(*tasks, return_exceptions=False)
                self._apply_weight_check(results, weight_check)
                return results

            # Single image
            else:
                image_input = job_input.get("image")
                category    = job_input.get("category", "unknown")
                title       = job_input.get("title")
                description = job_input.get("description")
                image_id    = job_input.get("id")
                position_id = job_input.get("position_id")

                if not image_input:
                    return {"error": "No image provided"}

                weight_check, result = await asyncio.gather(
                    self._check_shipping_weight(
                        shipping_weight, common_title, common_category, common_description
                    ),
                    self.process_single_image(
                        image_input, category, pipeline_mode,
                        title, description, image_id, position_id
                    ),
                )
                self._apply_weight_check([result], weight_check)
                return result

        except Exception as e:
            return {"error": str(e), "traceback": traceback.format_exc()}

    # -----------------------------------------------------------------------
    # id-only contract — the service fetches the listing itself
    # -----------------------------------------------------------------------
    async def check_listing(self, listing_id: int) -> Dict[str, Any]:
        """
        Check one listing by id.

        Pulls title/category/description/images from BDStall's product_details,
        runs the image pipeline only on images that haven't been checked yet
        (ai_verified 0 or 1), and returns one {image_id, position_id, error_id}
        entry per error found. Clean images — and images already at
        ai_verified=2 — don't appear in `results`; `checked` lists every image
        that was actually evaluated, so the caller knows exactly which ones it
        may flip to ai_verified=2.

        Raises ProductDetailsError when the listing can't be fetched, so the
        caller gets an error instead of an empty "all clean" result.
        """
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_executor, fetch_product_details, listing_id)

        pending = listing_images_pending_check(data)
        total_images = len(data.get("images") or [])
        print(f"🖼️  image_checker: listing {listing_id} — {len(pending)} of {total_images} "
              f"image(s) need checking (ai_verified 0 or 1)")

        if not pending:
            return {"results": [], "checked": []}

        results = await self.check_image({
            "category": data.get("category") or "unknown",
            "title": data.get("title"),
            "description": data.get("description"),
            "pipeline": "full",
            "images": pending,
        })

        # check_image only returns a dict when the whole batch blew up.
        if isinstance(results, dict):
            return {
                "results": [],
                "checked": [],
                "error": results.get("error", "image check failed"),
            }

        return self._to_error_entries(results)

    @staticmethod
    def _to_error_entries(results: List[Any]) -> Dict[str, Any]:
        """
        Flatten per-image flag dicts into BDStall's {image_id, position_id, error_id}
        rows, alongside which images were actually evaluated.

        `checked` exists so the caller doesn't have to infer it: an image is
        absent from `results` both when it came back clean and when it was never
        looked at, and only the former may be flipped to ai_verified=2.
        """
        entries: List[Dict[str, Any]] = []
        checked: List[Any] = []
        skipped: List[Dict[str, Any]] = []

        for r in results:
            if not isinstance(r, dict):
                continue

            image_id    = r.get("id")
            position_id = r.get("position_id", 0)

            # An image we couldn't fetch/process isn't a clean image — report it
            # separately so it doesn't get silently marked verified.
            if r.get("error"):
                skipped.append({
                    "image_id": image_id,
                    "position_id": position_id,
                    "reason": str(r["error"]),
                })
                continue

            checked.append(image_id)

            for field, error_id in IMAGE_ERROR_IDS:
                if r.get(field):
                    entries.append({
                        "image_id": image_id,
                        "position_id": position_id,
                        "error_id": error_id,
                    })

        response: Dict[str, Any] = {"results": entries, "checked": checked}
        if skipped:
            response["skipped"] = skipped
        return response

    async def check_listing_weight(self, listing_id: int) -> Dict[str, Any]:
        """
        Weight-mismatch check for one listing by id — the half that used to ride
        along on every image_checker result.

        Fails open when product_details carries no numeric shipping weight:
        there's nothing to compare against, so flagging would be a guess.
        """
        loop = asyncio.get_event_loop()
        data = await loop.run_in_executor(_executor, fetch_product_details, listing_id)

        declared_kg = listing_shipping_weight_kg(data)
        if declared_kg is None:
            print(f"⚖️  weight_checker: listing {listing_id} — product_details carries no numeric "
                  f"shipping weight (no 'shipping_weight_kg' field), nothing to compare against")
            return {"weight_mismatch": False, "reason": "no_declared_shipping_weight"}

        weight_check = await self._check_shipping_weight(
            declared_kg,
            data.get("title"),
            data.get("category") or "unknown",
            data.get("description"),
        )

        error_id = weight_check.get("weight_mismatch", 0)
        response: Dict[str, Any] = {"weight_mismatch": bool(error_id)}

        if not error_id:
            return response

        # On a mismatch, hand back the numbers behind the verdict so the seller
        # sees how far off they are and what to correct towards, rather than a
        # bare "weight differs" with nothing to act on.
        response["error_id"] = error_id
        response["declared_weight_kg"] = weight_check.get("declared_weight_kg", declared_kg)

        estimated = weight_check.get("estimated_weight_kg")
        if estimated is not None:
            response["estimated_weight_kg"] = estimated

        narration = weight_check.get("narration")
        if narration:
            response["narration"] = narration

        return response


# Lightweight Gemini-only checker. It deliberately does not construct any of
# the local image/OCR/CLIP services owned by ImageChecker.
class GeminiWeightChecker:
    async def check_listing_weight(self, listing_id: int) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(_executor, fetch_product_details, listing_id)

        declared_kg = listing_shipping_weight_kg(data)
        if declared_kg is None:
            return {
                "weight_mismatch": False,
                "reason": "no_declared_shipping_weight",
            }

        if not GEMINI_API_KEY:
            # A missing provider is a service configuration problem, not proof
            # that a seller's weight is correct.
            raise HTTPException(status_code=503, detail="Gemini weight lookup is not configured")

        weight_info = await loop.run_in_executor(
            _executor,
            gemini_estimate_weight_kg,
            data.get("title"),
            data.get("category") or "unknown",
            data.get("description"),
        )

        known_weight = _floor_weight_kg(weight_info.get("known_weight_kg"))
        packaged_weight = _floor_weight_kg(weight_info.get("packaged_weight_kg"))
        if not weight_info.get("_lookup_ok"):
            raise HTTPException(status_code=502, detail="Gemini weight lookup failed")

        # Gemini did answer, but could not identify the exact product. Do not
        # substitute a local/category model: this endpoint is Gemini-only.
        if known_weight is None:
            return {"weight_mismatch": False, "reason": "product_weight_unknown"}

        reference = max(known_weight, packaged_weight or 0)
        allowed_max = _allowed_max_weight_kg(reference)
        exceeded = declared_kg > allowed_max
        response: Dict[str, Any] = {"weight_mismatch": exceeded}

        if exceeded:
            estimated = packaged_weight or known_weight
            response.update({
                "error_id": WEIGHT_MISMATCH_ERROR_ID,
                "declared_weight_kg": declared_kg,
                "estimated_weight_kg": round(estimated, 3),
                "narration": _weight_narration(declared_kg, estimated),
            })

        return response


class GeminiPriceChecker:
    """
    Flags a listing priced above the going rate for the same product.

    The market figure comes from a live Google Search run through Gemini. Only
    *overpricing* is a finding: undercutting the market is a seller's own call,
    not an error, so it reports clean like any correctly priced listing.

    Fail-open throughout — no listing price, or no comparable product found in
    Bangladesh, reports clean rather than accusing a seller on missing evidence.
    """

    async def check_listing_price(self, listing_id: int) -> Dict[str, Any]:
        loop = asyncio.get_running_loop()
        data = await loop.run_in_executor(_executor, fetch_product_details, listing_id)

        our_price = data.get("price")
        try:
            our_price = float(our_price) if our_price is not None else None
        except (TypeError, ValueError):
            our_price = None
        if not our_price or our_price <= 0:
            return {"price_mismatch": False, "reason": "no_listing_price"}

        if not GEMINI_API_KEY:
            # A missing provider is a configuration problem, not evidence about
            # the price — same stance as the weight endpoint.
            raise HTTPException(status_code=503, detail="Gemini price lookup is not configured")

        market = await loop.run_in_executor(
            _executor,
            gemini_estimate_market_price,
            data.get("title"),
            data.get("category"),
            data.get("brand"),
            data.get("condition"),
            data.get("description"),
        )

        if not market.get("_lookup_ok"):
            raise HTTPException(status_code=502, detail="Gemini price lookup failed")

        # The median of the shop prices actually found, so one outlier listing
        # cannot move it — see gemini_price_service.
        market_price = market.get("typical_bdt")
        if not market.get("found") or not market_price:
            # The search ran and found no comparable Bangladeshi listing. Nothing
            # to compare against, so nothing to report.
            return {"price_mismatch": False, "reason": "no_market_price_found"}

        allowed_max = market_price * (1 + PRICE_TOLERANCE_PCT)
        exceeded = our_price > allowed_max

        print(f"💰 Price check: listing {listing_id} at BDT {our_price:,.0f} vs market "
              f"BDT {market_price:,.0f}, allowed_max BDT {allowed_max:,.0f}, "
              f"exceeded={exceeded}")

        if not exceeded:
            return {"price_mismatch": False}

        response: Dict[str, Any] = {
            "price_mismatch": True,
            "our_price_bdt": round(our_price, 2),
            "market_price_bdt": market_price,
            "difference_pct": round((our_price - market_price) / market_price * 100, 1),
            "narration": _price_narration(our_price, market_price),
        }
        # BDStall's error catalog has no price entry yet, so the id is only
        # reported once one is configured — see PRICE_MISMATCH_ERROR_ID.
        if PRICE_MISMATCH_ERROR_ID is not None:
            response["error_id"] = PRICE_MISMATCH_ERROR_ID
        return response


weight_checker = GeminiWeightChecker()
price_checker = GeminiPriceChecker()


# FastAPI Startup Event
@app.on_event("startup")
async def startup_event():
    """Start without loading local models; image models are initialized lazily."""
    print("🚀 Starting up AI Image Checker server...")
    print("✅ API ready; image models will load on the first image_checker request")


# API Endpoints
async def _ready_checker() -> "ImageChecker":
    global image_checker, _image_checker_init_lock
    if image_checker is not None:
        return image_checker

    if _image_checker_init_lock is None:
        _image_checker_init_lock = asyncio.Lock()

    async with _image_checker_init_lock:
        if image_checker is None:
            loop = asyncio.get_running_loop()
            image_checker = await loop.run_in_executor(_executor, ImageChecker)
    return image_checker


async def _dispatch_check(data: CheckRequest):
    """Route a /image_checker body to the id-only or the legacy path."""
    checker = await _ready_checker()
    payload = data.model_dump(exclude_none=True)

    # Legacy payload — images were pushed to us, so `id` (if any) is an image id.
    if payload.get("images") or payload.get("image"):
        return await checker.check_image(payload)

    listing_id = payload.get("id")
    if listing_id is None:
        raise HTTPException(
            status_code=422,
            detail='Send {"id": <listing_id>}, or a legacy payload containing "images".',
        )

    try:
        return await checker.check_listing(listing_id)
    except ProductDetailsError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@app.post("/image_checker", summary="Check a listing's images for quality and content issues")
@app.post("/image_checker/", include_in_schema=False)
@app.post("/api/moderation_ai/image_checker", include_in_schema=False)
@app.post("/api/moderation_ai/image_checker/", include_in_schema=False)
async def process_image(data: CheckRequest):
    """
    Send `{"id": <listing_id>}`. The listing is fetched from BDStall's
    `product_details` API, only images with `ai_verified` 0 or 1 are analyzed,
    and the response lists just the errors found:

    ```json
    {"results": [{"image_id": 458504, "position_id": 0, "error_id": 5}]}
    ```

    `error_id` values are BDStall's own `error_list` ids — 2 category mismatch,
    3 promotional text, 4 watermark, 5 blur, 6 background, 8 screenshot,
    9 illegal, 10 stock photo. Images that are clean, or already at
    `ai_verified` 2, don't appear in `results`. `checked` lists every image that
    was actually evaluated — set `ai_verified = 2` on exactly those. Images that
    couldn't be fetched or processed are reported under `skipped` instead of
    being reported as clean, and should be left for the next run to retry.

    Weight mismatch is no longer part of this response — see `/weight_checker`.

    The legacy payload (`category` + `images: [...]`) still works and still
    returns one flag object per image.
    """
    return await _dispatch_check(data)


@app.post("/image_checker/check", summary="Alternative check endpoint", include_in_schema=False)
async def check_endpoint(data: CheckRequest):
    return await _dispatch_check(data)


@app.post("/weight_checker", summary="Check a listing's declared shipping weight")
@app.post("/weight_checker/", include_in_schema=False)
@app.post("/api/moderation_ai/weight_checker", include_in_schema=False)
@app.post("/api/moderation_ai/weight_checker/", include_in_schema=False)
async def process_weight(data: ListingRequest):
    """
    Send `{"id": <listing_id>}` — returns `{"weight_mismatch": false}`, plus
    `"error_id": 24` when the declared weight is implausible for the product.

    The declared weight is read from `product_details`; it is **not** parsed out
    of the free-text `specification` entries. Until `product_details` returns a
    numeric `shipping_weight_kg`, there's nothing to compare against and this
    fails open with `{"weight_mismatch": false, "reason":
    "no_declared_shipping_weight"}`.
    """
    try:
        return await weight_checker.check_listing_weight(data.id)
    except ProductDetailsError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@app.post("/price_checker", summary="Flag a listing priced above the market")
@app.post("/price_checker/", include_in_schema=False)
@app.post("/api/moderation_ai/price_checker", include_in_schema=False)
@app.post("/api/moderation_ai/price_checker/", include_in_schema=False)
async def process_price(data: ListingRequest):
    """
    Send `{"id": <listing_id>}` — returns `{"price_mismatch": false}` when the
    listing is not priced above the market, or `price_mismatch: true` with
    `our_price_bdt`, `market_price_bdt`, `difference_pct` and a `narration`
    when it is.

    The market figure comes from a live Google Search of Bangladeshi shops, run
    through Gemini. Only overpricing is reported: a listing cheaper than the
    market is the seller's own call, not an error.

    Slower than the other endpoints (a grounded search runs several queries and
    reads pages before answering), so it is a per-listing lookup, not something
    to call in a tight loop.
    """
    try:
        return await price_checker.check_listing_price(data.id)
    except ProductDetailsError as e:
        raise HTTPException(status_code=e.status_code, detail=str(e))


@app.get("/image_checker/health")
@app.get("/weight_checker/health", include_in_schema=False)
@app.get("/price_checker/health", include_in_schema=False)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AI Image Checker",
        "version": "1.0.0",
        "ready": True,
        "image_models_ready": image_checker is not None,
        "weight_checker_ready": bool(GEMINI_API_KEY),
        "price_checker_ready": bool(GEMINI_API_KEY),
    }


@app.get("/image_checker")
async def root():
    """Info endpoint - only accessible at /image_checker"""
    return {
        "name": "AI Image Checker",
        "version": "1.0.0",
        "endpoints": {
            "POST /image_checker/": "Check a listing's images by id",
            "POST /weight_checker/": "Check a listing's declared shipping weight by id",
            "POST /price_checker/": "Flag a listing priced above the Bangladeshi market by id",
            "POST /image_checker/check": "Alternative check endpoint",
            "GET /image_checker/health": "Health check"
        },
        "example": {"id": 141462},
        "legacy_example": {
            "category": "electronics",
            "title": "Product Name",
            "images": [
                {"id": 1, "position_id": 0, "image": "https://example.com/image.jpg"}
            ],
            "pipeline": "full"
        }
    }


def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AI Image Checker Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to bind to (default: 8000)")
    parser.add_argument("--workers", type=int, default=1, help="Number of worker processes (default: 1)")
    
    args = parser.parse_args()
    
    print("="*60)
    print("AI Image Checker - Vast AI Server")
    print("="*60)
    print(f"Starting server on {args.host}:{args.port}")
    print(f"Workers: {args.workers}")
    print("\nAPI Documentation:")
    print(f"  - POST http://{args.host}:{args.port}/image_checker/  - Check a listing's images by id")
    print(f"  - POST http://{args.host}:{args.port}/weight_checker/ - Check a listing's shipping weight by id")
    print(f"  - POST http://{args.host}:{args.port}/price_checker/ - Flag a listing priced above the market by id")
    print(f"  - GET  http://{args.host}:{args.port}/image_checker/health - Health check")
    print(f"  - GET  http://{args.host}:{args.port}/docs  - Swagger UI (interactive docs)")
    print(f"  - GET  http://{args.host}:{args.port}/redoc - ReDoc UI")
    print("="*60)
    
    uvicorn.run(
        "main:app",
        host=args.host,
        port=args.port,
        workers=args.workers,
        reload=False
    )


if __name__ == "__main__":
    main()
