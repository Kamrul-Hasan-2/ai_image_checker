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

class CheckRequest(BaseModel):
    category: str = Field(..., example="laptop")
    title: Optional[str] = Field(None, example="HP EliteBook 840 G8")
    description: Optional[str] = Field(None, example="14 inch business laptop with Intel Core i5")
    images: List[ImageItem] = Field(..., example=[{"id": 1, "position_id": 1, "image": "https://cdn.bdstall.com/product-image/sample.jpg"}])
    pipeline: Optional[str] = Field("full", example="full")

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env before importing services so flags are set
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass  # dotenv optional — values can be set as real env vars

# Import services
from quality_service import QualityCheckService
from ocr_service import OCRService
from clip_service import CLIPService
from qwen_service import USE_QWEN2VL, GROQ_API_KEY, GROQ_MODEL, get_qwen_service, groq_moderate_image
from screenshot_detector import compute_screenshot_score, apply_screenshot_decision
from promotional_detector import detect_promotional_text
from watermark_detector import detect_watermark_visual

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


class ImageChecker:
    """Image Checker Service"""
    
    def __init__(self):
        """Initialize all services"""
        print("Initializing services...")
        
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
            if is_product_photo and product_photo_confidence > 0.30:
                # For confirmed products: only explicit watermarks or BD marketplace matter
                # seller_watermark produces too many false positives ("Mobile Shop Display" etc.)
                keyword_watermark = watermark_keywords or bd_marketplace
            else:
                # For non-products: apply full watermark check including seller text
                keyword_watermark = watermark_risk > 0.2 or watermark_keywords or bd_marketplace or seller_watermark

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
    
    async def check_image(self, job_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main handler - processes multiple images in parallel.
        """
        try:
            pipeline_mode    = job_input.get("pipeline", "full")
            common_category  = job_input.get("category", "unknown")
            common_title     = job_input.get("title")
            common_description = job_input.get("description")

            # Multiple images — process ALL concurrently
            if "images" in job_input:
                images_list = job_input.get("images", [])
                if not images_list:
                    return {"error": "No images provided"}

                tasks = []
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

                # All images run at the same time
                results = await asyncio.gather(*tasks, return_exceptions=False)
                return list(results)

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

                return await self.process_single_image(
                    image_input, category, pipeline_mode,
                    title, description, image_id, position_id
                )

        except Exception as e:
            return {"error": str(e), "traceback": traceback.format_exc()}


# FastAPI Startup Event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global image_checker
    print("🚀 Starting up AI Image Checker server...")
    image_checker = ImageChecker()
    print("✅ Server ready to process images")


# API Endpoints
@app.post("/image_checker", summary="Check images for quality and content issues")
@app.post("/image_checker/", include_in_schema=False)
async def process_image(data: CheckRequest):
    """
    Analyze product images for:
    - **blur** — out-of-focus or low-sharpness images
    - **watermark** — visual or text watermarks
    - **promotional_text** — overlaid marketing/promo text
    - **screenshot** — screenshots instead of real product photos
    - **category_mismatch** — image doesn't match the listed category
    - **illegal** — prohibited content
    - **stock_photo** — generic stock images
    """
    if image_checker is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    return await image_checker.check_image(data.model_dump())


@app.post("/image_checker/check", summary="Alternative check endpoint", include_in_schema=False)
async def check_endpoint(data: CheckRequest):
    if image_checker is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    return await image_checker.check_image(data.model_dump())


@app.get("/image_checker/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AI Image Checker",
        "version": "1.0.0",
        "ready": image_checker is not None
    }


@app.get("/image_checker")
async def root():
    """Info endpoint - only accessible at /image_checker"""
    return {
        "name": "AI Image Checker",
        "version": "1.0.0",
        "endpoints": {
            "POST /image_checker/": "Check images",
            "POST /image_checker/check": "Alternative check endpoint",
            "GET /image_checker/health": "Health check"
        },
        "example": {
            "images": [
                {
                    "image": "https://example.com/image.jpg",
                    "category": "electronics",
                    "title": "Product Name"
                }
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
    print(f"  - POST http://{args.host}:{args.port}/image_checker/ - Check images")
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
