"""
Modal.com Serverless Handler for AI Image Checker
Clean implementation with GPU snapshot optimization
"""

import modal
import base64
import io
import os
import requests
from PIL import Image
from typing import Dict, Any
import traceback

# Load .env flags early
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
except ImportError:
    pass

from qwen_service import USE_QWEN2VL, GROQ_API_KEY, get_qwen_service, groq_moderate_image, estimate_known_product_weight_kg
from weight_reference import plausible_max_weight_kg
from image_loader import load_image_safe

# Weight sanity check: seller-submitted shipping_weight vs the product's known
# published weight. Error catalog entry (https://www.bdstall.com/api/item_ai/ai_error_list/):
# error_id 24 = "Weight differs from recorded product weight".
WEIGHT_MISMATCH_ERROR_ID = 24
WEIGHT_TOLERANCE_FACTOR  = 1.10  # allow up to 10% over the known product weight
# Shipping is never billed below 0.1 kg, so a looked-up weight under that is
# treated as 0.1 kg — otherwise a seller declaring the 0.1 kg minimum on a
# 0.03 kg item gets flagged for a weight they could not declare any lower.
MIN_SHIPPING_WEIGHT_KG = 0.1
# See main.py: 10% of a light product is a few grams, tighter than any real
# parcel, so the declared weight must clear the percentage AND a flat slack.
WEIGHT_ABSOLUTE_SLACK_KG = 0.2

# Create Modal app
app = modal.App("ai-image-checker")

# Function to pre-download models during image build
def download_models():
    """Download all models during image build for GPU snapshot"""
    import os
    os.environ["TRANSFORMERS_CACHE"] = "/root/.cache/huggingface"
    os.environ["HF_HOME"] = "/root/.cache/huggingface"
    
    print("Downloading models...")
    
    from transformers import CLIPModel, CLIPProcessor

    CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")

    if USE_QWEN2VL:
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
        Qwen2VLForConditionalGeneration.from_pretrained(
            "Qwen/Qwen2-VL-2B-Instruct", trust_remote_code=True
        )
        AutoProcessor.from_pretrained("Qwen/Qwen2-VL-2B-Instruct", trust_remote_code=True)
        print("✅ Qwen2-VL model downloaded")
    else:
        print("⏭️  Qwen2-VL download skipped (USE_QWEN2VL=False)")
    
    import easyocr
    os.makedirs('/root/.cache/easyocr', exist_ok=True)
    easyocr.Reader(['en'], gpu=False, model_storage_directory='/root/.cache/easyocr')
    
    print("Models downloaded successfully!")

# Define the container image
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi",
        "uvicorn[standard]",
        "python-multipart",
        "transformers",
        "Pillow",
        "qwen-vl-utils",
        "accelerate",
        "easyocr",
        "opencv-python-headless",
        "requests",
        "torch",
        "torchvision",
    )
    .run_function(download_models, gpu="A10G")
    .add_local_file("quality_service.py", "/root/quality_service.py")
    .add_local_file("ocr_service.py", "/root/ocr_service.py")
    .add_local_file("clip_service.py", "/root/clip_service.py")
    .add_local_file("qwen_service.py", "/root/qwen_service.py")
    .add_local_file("image_loader.py", "/root/image_loader.py")
)


@app.cls(
    image=image,
    gpu="A10G",
    cpu=8.0,
    memory=16384,
    timeout=60,
    scaledown_window=15,
    enable_memory_snapshot=True,
    min_containers=0,
    experimental_options={"enable_gpu_snapshot": True},
)
@modal.concurrent(max_inputs=10)
class ImageChecker:
    """Modal class for AI Image Checker"""
    
    @modal.enter(snap=True)
    def initialize_services(self):
        """Initialize services with GPU snapshot"""
        import os
        import sys
        
        os.environ["TRANSFORMERS_CACHE"] = "/root/.cache/huggingface"
        os.environ["HF_HOME"] = "/root/.cache/huggingface"
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        
        sys.path.insert(0, "/root")
        
        from quality_service import QualityCheckService
        from ocr_service import OCRService
        from clip_service import CLIPService
        self.quality_service = QualityCheckService()
        self.ocr_service = OCRService(languages=['en'])
        self.clip_service = CLIPService(model_name="openai/clip-vit-base-patch32")

        self.qwen2b_service = get_qwen_service()
        if self.qwen2b_service:
            print("✅ Qwen2-VL local model loaded")
        else:
            print("⏭️  Qwen2-VL disabled (USE_QWEN2VL=False)")

        if GROQ_API_KEY:
            print(f"✅ Groq API configured (model: qwen/qwen3-32b)")
    
    def load_image(self, image_input: str) -> Image.Image:
        """Load image from URL or base64 (SSRF-guarded, size-capped, data-URL safe)."""
        return load_image_safe(image_input)
    
    def process_single_image(self, image_input: str, category: str, pipeline_mode: str, title: str = None, description: str = None, image_id: int = None, position_id: int = None) -> Dict[str, Any]:
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
        # Exception categories where promotional_text is always 0
        exception_categories = [
            "car", "car accessories",
            "bike", "bike accessories",
            "three wheeler", "bicycle", "bicycle accessories",
            "commercial vehicle", "rental", "vehicle equipment",
            "cow", "cattle", "livestock", "poultry", "goat", "sheep",
            "buffalo", "animal", "pet", "bird", "fish",
        ]
        _livestock_keywords = ("cow", "cattle", "livestock", "poultry", "goat", "sheep",
                               "buffalo", "animal", "pet", "bird", "fish")
        _cat_lower = category.lower().strip()
        is_exception_category = (
            _cat_lower in exception_categories
            or any(kw in _cat_lower for kw in _livestock_keywords)
        )
        
        try:
            image = self.load_image(image_input)
            
            # CRITICAL: Quality check BEFORE resizing - blur detection needs full resolution
            quality_result = self.quality_service.check_image(image)
            opencv_risk = quality_result.get("opencv_risk", 0.0)
            screenshot_confidence = quality_result.get("screenshot_confidence", 0.0)
            blur_confidence = quality_result.get("blur_confidence", 0.0)
            
            # Resize for optimal OCR/CLIP processing (balance speed vs accuracy)
            # Note: Quality check done BEFORE resize to preserve blur detection accuracy
            max_size = 800  # Resize to 800x800 for AI processing
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # OCR analysis
            ocr_result = self.ocr_service.extract_text(image)
            ocr_risk = ocr_result.get("ocr_risk", 0.0)
            watermark_confidence_ocr = ocr_result.get("watermark_confidence", 0.0)
            promo_confidence_ocr = ocr_result.get("promotional_confidence", 0.0)
            watermark_keywords = ocr_result.get("watermark_keywords_found", False)
            bd_marketplace = ocr_result.get("bd_marketplace_watermark", False)
            has_price = ocr_result.get("has_price", False)
            has_phone_number = ocr_result.get("has_phone_number", False)
            has_ecommerce_ui = ocr_result.get("has_ecommerce_ui", False)
            has_link = ocr_result.get("has_link", False)
            promotional_detected_ocr = ocr_result.get("promotional_detected", False)
            
            # NEW: Visual promo indicators
            visual_promo_score = ocr_result.get("visual_promo_score", 0.0)
            strong_price_indicator = ocr_result.get("strong_price_indicator", False)
            has_button_ui = ocr_result.get("has_button_ui", False)
            has_promotional_sticker = ocr_result.get("has_promotional_sticker", False)
            digit_count = ocr_result.get("digit_count", 0)
            
            # CRITICAL: Check if image shows actual product (using CLIP)
            # If it's a product photo, text on it is part of the product, NOT promotional
            product_check = self.clip_service.detect_product_photo(image)
            is_product_photo = product_check.get("is_product_photo", False)
            product_photo_confidence = product_check.get("product_score", 0.0)
            
            # NEW STEP 1: Verify image body content matches expected product
            # Check if the image actually shows what it's supposed to (e.g., RAM, phone, camera)
            # This prevents promotional images from being misclassified
            image_body_match = False
            body_match_confidence = 0.0
            
            if has_title_or_description := bool(title or description):
                # Use CLIP to verify image content matches product title/description
                body_verification = self.clip_service.verify_image_body_content(
                    image, 
                    title or "", 
                    description or ""
                )
                image_body_match = body_verification.get("body_matches", False)
                body_match_confidence = body_verification.get("confidence", 0.0)
            
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
                    
                    # If title/description provided but doesn't match OCR = MISMATCH
                    if not is_title_match and len(full_text) > 10:  # Only if OCR has meaningful text
                        title_description_mismatch = True
            
            # CLIP analysis (skipped for speed - can be enabled if needed)
            clip_risk = 0.0
            
            # Qwen2-VL / Groq moderation — controlled by .env flags
            qwen_risk = 0.0
            qwen_promo_score = 0.0
            qwen_watermark_score = 0.0
            qwen_illegal_score = 0.0
            qwen_result = None  # None = vision model didn't run / call failed — never treat as a verdict

            if self.qwen2b_service:
                try:
                    qwen_result = self.qwen2b_service.moderate_image(image)
                    qwen_risk            = 1.0 if qwen_result.get("decision") == "BLOCK" else 0.0
                    qwen_promo_score     = 1.0 if qwen_result.get("is_promotional") else 0.0
                    qwen_watermark_score = 1.0 if qwen_result.get("has_watermark") else 0.0
                    qwen_illegal_score   = 1.0 if "illegal_content" in qwen_result.get("violations", []) else 0.0
                except Exception as qe:
                    print(f"⚠️  Qwen2-VL error: {qe}")
                    qwen_result = None
            elif GROQ_API_KEY:
                try:
                    qwen_result = groq_moderate_image(image)
                    qwen_risk            = 1.0 if qwen_result.get("decision") == "BLOCK" else 0.0
                    qwen_promo_score     = 1.0 if qwen_result.get("is_promotional") else 0.0
                    qwen_watermark_score = 1.0 if qwen_result.get("has_watermark") else 0.0
                    qwen_illegal_score   = 1.0 if "illegal_content" in qwen_result.get("violations", []) else 0.0
                except Exception as ge:
                    print(f"⚠️  Groq error: {ge}")
                    qwen_result = None
            
            # Calculate final scores - only flag clear mobile UI screenshots
            screenshot_detected = screenshot_confidence > 0.90
            # FIX: Check if blur check FAILED (not passed) instead of using confidence threshold
            blur_detected = not quality_result['checks']['blur']['passed']
            
            # Watermark detection is INDEPENDENT of promotional detection
            # Even product photos can have watermarks (bikroy, daraz, website logos)
            watermark_risk = ocr_risk * watermark_confidence_ocr
            # watermark_keywords / bd_marketplace are precise string matches (stock-photo
            # service name, BD marketplace domain) — trusted unconditionally. watermark_risk
            # is a fuzzy text-coverage heuristic (can fire on any image with lots of printed
            # text) — vetoed when the vision model actually looked and saw no watermark.
            strong_watermark_match = watermark_keywords or bd_marketplace
            weak_watermark_signal = watermark_risk > 0.2
            if (
                qwen_result is not None
                and qwen_result.get("_moderation_ok", True)
                and not qwen_result.get("has_watermark", False)
            ):
                weak_watermark_signal = False
            watermark_detected = strong_watermark_match or weak_watermark_signal
            
            # Check if product text only (from OCR)
            is_product_text_only = ocr_result.get("is_product_text_only", False)
            
            # ========================================================================
            # PROMOTIONAL DETECTION LOGIC - CRITICAL FOR PRODUCT IMAGES
            # ========================================================================
            # Four-tier detection system:
            # 
            # 1. PRODUCT TITLE MATCHING (HIGHEST PRIORITY):
            #    - If product title provided and matches OCR text (>= 60% words match)
            #    - Text is the product name/description = NOT promotional
            #    - Example: Title "Dell Inspiron 15" matches "Dell Inspiron 15 3000" in OCR
            #
            # 2. VISUAL PRODUCT DETECTION (CLIP-based):
            #    - If image shows actual product (e.g., camera in box, phone on table)
            #    - Text on product/packaging is NOT promotional
            #    - Example: "Imou 3K 5MP" on camera box = SAFE
            #    - Even if text contains specs/model numbers = SAFE
            #
            # 3. TEXT-ONLY PRODUCT DETECTION (OCR-based):
            #    - If text has NO price, phone, link, or e-commerce UI
            #    - AND no strong sale terms (buy now, discount, etc.)
            #    - Then it's likely just product branding = SAFE
            #    - Example: "Samsung Galaxy A54" without price = SAFE
            #
            # 4. PROMOTIONAL SIGNALS (Multi-signal):
            #    - Price + phone = PROMOTIONAL
            #    - E-commerce UI buttons = PROMOTIONAL
            #    - Contact info = PROMOTIONAL
            #
            # Priority: Title match > Visual detection > Text detection > Signal detection
            # ========================================================================
            
            # Promotional detection - RESPECT product title and photo flags
            # NEW LOGIC: Verify image body matches product FIRST, then check promotional signals
            # PRIORITY ORDER: product_photo > image_body_match > product_text_only > title_match > signals
            promo_risk = promo_confidence_ocr

            # Check for VERY STRONG promotional signals first (overrides everything).
            # Kept in sync with main.py: a phone number or a website/social link by
            # itself is decisive — a seller's contact info overlaid on an otherwise
            # genuine product photo is still promotional, even without a price.
            very_strong_promo = (
                has_phone_number or                                # Any BD phone number = clear promo
                has_link or                                        # Any website/social link = clear promo
                (has_ecommerce_ui and strong_price_indicator) or  # E-commerce UI + real price
                has_promotional_sticker                           # Promotional sticker on product
            )

            # HIGHEST PRIORITY: very strong promotional signals (phone/link/etc.)
            # override every other check below — including "looks like a product
            # photo", since a seller's contact info overlaid on a genuine product
            # photo is still promotional content.
            if very_strong_promo:
                promotional_detected = True
                promo_risk = 0.95
            # SECOND PRIORITY: Product photo detection (CLIP-based)
            # If CLIP detects it's a product photo, text is part of product, NOT promotional
            elif is_product_photo and product_photo_confidence > 0.30:
                # Product photo = text on product is specs/branding, NOT promotional
                promotional_detected = False
                promo_risk = 0.0
            # THIRD PRIORITY: Image body verification with lower threshold
            # If image shows the actual product body (e.g., RAM module, phone, camera)
            # Then text on the image is product labeling, NOT promotional
            elif image_body_match and body_match_confidence > 0.1:
                # Image content matches what it should show = product labels, NOT promotional
                promotional_detected = False
                promo_risk = 0.0
            # FOURTH PRIORITY: Product text only (text physically on product body)
            elif is_product_text_only:
                # Text is PART OF THE PRODUCT (like "INSULATING" on tool, "Canon" on camera)
                # This is NOT promotional - it's product branding/labeling
                promotional_detected = False
                promo_risk = 0.0
            elif title_description_mismatch:
                # Title/description provided but OCR text doesn't match = PROMOTIONAL
                promotional_detected = True
                promo_risk = 0.95  # High confidence it's promotional
            elif is_title_match:
                # Product title matches OCR text = text is product name, NOT promotional
                promotional_detected = False
                promo_risk = 0.0
            elif is_product_photo:
                # Product photo detected visually = text is part of product, NOT promotional
                promotional_detected = False
                promo_risk = 0.0
            else:
                # Multi-signal detection for actual promotional content
                promotional_detected = (
                    promotional_detected_ocr or 
                    has_price or 
                    has_phone_number or 
                    has_ecommerce_ui
                )
            
            # Hardcoded: illegal always 0 (only sell legitimate products)
            illegal_detected = False
            
            # Final risk calculation (fast mode)
            # Weight promotional content higher if detected
            promo_weight = 0.3 if promotional_detected else 0.0
            final_risk = 0.80 * ocr_risk + 0.20 * opencv_risk + promo_weight
            risk_level = min(int(final_risk * 100), 100)
            
            # Calculate promotional text severity (0-10 scale) with visual features
            # CRITICAL: If product photo detected, promo_score MUST be 0
            promo_score = 0
            
            # Skip promotional scoring if it's a product photo/body
            is_confirmed_product = (
                (is_product_photo and product_photo_confidence > 0.30) or
                (image_body_match and body_match_confidence > 0.1) or
                is_product_text_only or
                is_title_match
            )
            
            if promotional_detected and not is_confirmed_product:
                # HIGHEST PRIORITY: Title/description mismatch
                if title_description_mismatch:
                    promo_score = 10  # Maximum score - text doesn't match product info
                # High severity combinations
                elif has_price and has_phone_number:
                    promo_score = 9  # Price + contact = definite promo
                elif (has_price or strong_price_indicator) and has_button_ui:
                    promo_score = 8  # Price + UI buttons = e-commerce
                elif has_price or strong_price_indicator:
                    promo_score = 7  # Price alone is strong indicator
                elif has_ecommerce_ui and visual_promo_score > 0.5:
                    promo_score = 7  # E-commerce UI + visual cues
                elif has_button_ui and digit_count >= 6:
                    promo_score = 6  # UI buttons + many digits
                elif has_phone_number:
                    promo_score = 5  # Contact info
                elif visual_promo_score >= 0.6:
                    promo_score = 6  # Strong visual indicators
                elif promo_confidence_ocr > 0.75:
                    promo_score = 7  # High OCR confidence
                elif promo_confidence_ocr > 0.5:
                    promo_score = 4  # Medium confidence
                else:
                    promo_score = 3  # Low but detected
            
            # Build result with id and position_id first (if provided)
            result = {}
            
            # Add id and position_id at the beginning if provided
            if image_id is not None:
                result["id"] = image_id
            if position_id is not None:
                result["position_id"] = position_id
            
            # Add the rest of the fields
            result.update({
                "blur_image": 5 if blur_detected else 0,
                "screen_short": 8 if screenshot_detected else 0,
                "category_mismatch": 0,
                "illegal": 0,  # Always 0 - hardcoded
                # Binary 0/3 scale, kept consistent with main.py and README.md.
                # (promo_score is retained in _debug for severity insight.)
                "promotional_text": 0 if is_exception_category else (3 if promotional_detected else 0),
                "stock_photo": 0,
                "watermark": 4 if watermark_detected else 0,
                "risk_level": risk_level,
                # Debug fields
                "_debug": {
                    "image_body_match": image_body_match,
                    "body_match_confidence": body_match_confidence,
                    "is_product_photo": is_product_photo,
                    "is_title_match": is_title_match,
                    "promotional_detected": promotional_detected,
                    "promo_score": promo_score,
                    "very_strong_promo": very_strong_promo
                }
            })
            
            return result
            
        except Exception as e:
            # Build error result with id and position_id first (if provided)
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

    def _check_shipping_weight(self, shipping_weight, title, category, description) -> Dict[str, Any]:
        """
        Two-layer check on a seller-submitted shipping_weight (kg):

        1. AI lookup of the *specific* product's known published weight (via Groq,
           text-only). Precise: flags when given weight exceeds known weight + 10%
           tolerance (packaging etc.). Only fires on a confident, named-model match.
        2. Fallback: when the AI doesn't recognize the specific model (generic/
           no-name listings — most of the catalog), fall back to a category-level
           plausibility ceiling so obviously wrong values (e.g. 350kg for a
           Bluetooth speaker) still get caught instead of silently passing.

        Both layers are fail-open: an unrecognized product AND an unrecognized
        category means no reference point exists, so nothing is flagged.
        """
        if shipping_weight is None:
            return {"weight_mismatch": 0}

        if title and GROQ_API_KEY:
            weight_info = estimate_known_product_weight_kg(title, category, description)
            known_weight = weight_info.get("known_weight_kg")
            if known_weight is not None:
                known_weight = max(float(known_weight), MIN_SHIPPING_WEIGHT_KG)
            if weight_info.get("_lookup_ok") and known_weight is not None:
                allowed_max = max(known_weight * WEIGHT_TOLERANCE_FACTOR,
                                  known_weight + WEIGHT_ABSOLUTE_SLACK_KG)
                exceeded = shipping_weight > allowed_max
                print(f"⚖️  Weight check (model-specific): given={shipping_weight}kg, "
                      f"known≈{known_weight}kg (confidence={weight_info.get('confidence')}), "
                      f"allowed_max={allowed_max:.3f}kg, exceeded={exceeded}")
                return {
                    "weight_mismatch": WEIGHT_MISMATCH_ERROR_ID if exceeded else 0,
                    "_debug": {
                        "weight_check_method": "ai_known_weight",
                        "given_shipping_weight_kg": shipping_weight,
                        "known_product_weight_kg": known_weight,
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
                "_debug": {
                    "weight_check_method": "category_sanity_range",
                    "given_shipping_weight_kg": shipping_weight,
                    "category_max_plausible_kg": category_max,
                },
            }

        return {"weight_mismatch": 0}

    @staticmethod
    def _apply_weight_check(results, weight_check: Dict[str, Any]) -> None:
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

    @modal.method()
    def check_image(self, job_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main handler - supports single or multiple images
        """
        try:
            pipeline_mode = job_input.get("pipeline", "full")
            shipping_weight = job_input.get("shipping_weight")

            # Multiple images
            if "images" in job_input:
                images_list = job_input.get("images", [])

                if not images_list:
                    return {"error": "No images provided"}

                # Get common fields (shared across all images)
                common_category = job_input.get("category", "unknown")
                common_title = job_input.get("title")  # Optional product title
                common_description = job_input.get("description")  # Optional product description

                # Product-level check (not per-image) — one lookup, applied to every image below.
                weight_check = self._check_shipping_weight(
                    shipping_weight, common_title, common_category, common_description
                )

                results = []
                for img_data in images_list:
                    image_input = img_data.get("image")
                    # Allow per-image override, but use common values by default
                    category = img_data.get("category", common_category)
                    title = img_data.get("title", common_title)
                    description = img_data.get("description", common_description)
                    # Extract id and position_id if provided
                    image_id = img_data.get("id")
                    position_id = img_data.get("position_id")
                    
                    if not image_input:
                        # Build error result with id and position_id first (if provided)
                        error_result = {}
                        if image_id is not None:
                            error_result["id"] = image_id
                        if position_id is not None:
                            error_result["position_id"] = position_id
                        error_result.update({
                            "error": "No image URL provided",
                            "risk_level": 0
                        })
                        results.append(error_result)
                    else:
                        result = self.process_single_image(image_input, category, pipeline_mode, title, description, image_id, position_id)
                        results.append(result)

                self._apply_weight_check(results, weight_check)
                return results

            # Single image
            else:
                image_input = job_input.get("image")
                category = job_input.get("category", "unknown")
                title = job_input.get("title")  # Optional product title
                description = job_input.get("description")  # Optional product description
                image_id = job_input.get("id")  # Optional image ID
                position_id = job_input.get("position_id")  # Optional position ID

                if not image_input:
                    return {"error": "No image provided"}

                weight_check = self._check_shipping_weight(shipping_weight, title, category, description)
                result = self.process_single_image(image_input, category, pipeline_mode, title, description, image_id, position_id)
                self._apply_weight_check([result], weight_check)
                return result
            
        except Exception as e:
            return {
                "error": str(e),
                "traceback": traceback.format_exc()
            }


# Web endpoint
@app.function(
    image=image,
    gpu="A10G",
    cpu=4.0,
    memory=16384,
    timeout=60,
    scaledown_window=15,
    enable_memory_snapshot=True,
    min_containers=0,
    experimental_options={"enable_gpu_snapshot": True},
)
@modal.asgi_app()
def check_image_endpoint():
    from fastapi import FastAPI
    
    web_app = FastAPI()
    
    @web_app.post("/")
    async def process_image(data: Dict[str, Any]):
        """HTTP endpoint to check images"""
        checker = ImageChecker()
        return checker.check_image.local(data)
    
    return web_app


# Local entrypoint for testing
@app.local_entrypoint()
def main():
    """Test locally"""
    test_input = {
        "image": "https://picsum.photos/800/600",
        "category": "electronics"
    }
    
    checker = ImageChecker()
    result = checker.check_image.remote(test_input)
    print("Result:", result)

