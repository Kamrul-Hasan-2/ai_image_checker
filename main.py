"""
Vast AI Server - AI Image Checker
Replace Modal with FastAPI for Vast AI deployment
All services remain unchanged
"""

import os
import sys
import uvicorn
from fastapi import FastAPI, HTTPException
from typing import Dict, Any
import base64
import io
import requests
from PIL import Image
import traceback

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import services
from quality_service import QualityCheckService
from ocr_service import OCRService
from clip_service import CLIPService
from qwen_service import Qwen2VLService

# Create FastAPI app
app = FastAPI(
    title="AI Image Checker", 
    version="1.0.0"
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
            self.qwen2b_service = Qwen2VLService(model_name="Qwen/Qwen2-VL-2B-Instruct")
            print("✅ All services initialized successfully")
        except Exception as e:
            print(f"❌ Error initializing services: {e}")
            raise
    
    def load_image(self, image_input: str) -> Image.Image:
        """Load image from URL or base64"""
        try:
            if image_input.startswith('http://') or image_input.startswith('https://'):
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                }
                response = requests.get(image_input, headers=headers, timeout=10)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content))
            elif image_input.startswith('data:image'):
                base64_str = image_input.split(',')[1]
                image_data = base64.b64decode(base64_str)
                image = Image.open(io.BytesIO(image_data))
            else:
                image_data = base64.b64decode(image_input)
                image = Image.open(io.BytesIO(image_data))
            
            return image.convert('RGB')
        except Exception as e:
            raise ValueError(f"Failed to load image: {str(e)}")
    
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
            "commercial vehicle", "rental", "vehicle equipment"
        ]
        
        is_exception_category = category.lower().strip() in exception_categories
        
        debug_info = {}
        
        try:
            print(f"\n🔍 Processing image (ID: {image_id}, Position: {position_id})")
            print(f"   Category: {category}, Title: {title}, Description: {description}")
            
            image = self.load_image(image_input)
            print(f"✅ Image loaded: {image.size}")
            
            # CRITICAL: Quality check BEFORE resizing - blur detection needs full resolution
            quality_result = self.quality_service.check_image(image)
            opencv_risk = quality_result.get("opencv_risk", 0.0)
            screenshot_confidence = quality_result.get("screenshot_confidence", 0.0)
            blur_confidence = quality_result.get("blur_confidence", 0.0)
            print(f"✅ Quality check done - blur: {blur_confidence:.2f}, screenshot: {screenshot_confidence:.2f}")
            
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
            promotional_detected_ocr = ocr_result.get("promotional_detected", False)
            
            print(f"✅ OCR done - text: {ocr_result.get('full_text', '')[:50]}..., promo conf: {promo_confidence_ocr:.2f}")
            
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
            print(f"✅ CLIP product check: is_product_photo={is_product_photo}, conf={product_photo_confidence:.2f}")
            
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
                print(f"✅ Body verification: matches={image_body_match}, conf={body_match_confidence:.2f}")
            
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
            
            # SKIP Qwen2-VL for speed - rely only on fast OCR detection
            qwen_risk = 0.0
            qwen_promo_score = 0.0
            qwen_watermark_score = 0.0
            qwen_illegal_score = 0.0
            
            # Calculate final scores - only flag clear mobile UI screenshots
            screenshot_detected = screenshot_confidence > 0.90
            # FIX: Check if blur check FAILED (not passed) instead of using confidence threshold
            blur_detected = not quality_result['checks']['blur']['passed']
            
            # Watermark detection is INDEPENDENT of promotional detection
            # Even product photos can have watermarks (bikroy, daraz, website logos)
            watermark_risk = ocr_risk * watermark_confidence_ocr
            watermark_detected = watermark_risk > 0.2 or watermark_keywords or bd_marketplace
            
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
            
            # Check for VERY STRONG promotional signals first (overrides everything)
            # These are clear promotional indicators that should be detected even on product photos
            very_strong_promo = (
                (has_phone_number and has_price) or  # Phone + price = clear promo
                (has_phone_number and has_link) or   # Phone + website = clear promo  
                (has_ecommerce_ui and has_price) or  # E-commerce UI + price = clear promo
                (has_button_ui and has_phone_number) or  # Buttons + phone = clear promo
                (has_price and has_link and len(ocr_result.get('full_text', '')) > 20) or  # Price + link + substantial text
                has_promotional_sticker  # Promotional sticker detected on product
            )
            
            # HIGHEST PRIORITY: Product photo detection (CLIP-based)
            # If CLIP detects it's a product photo, text is part of product, NOT promotional
            # EXCEPTION: Still flag if very strong promotional signals detected
            if is_product_photo and product_photo_confidence > 0.30 and not very_strong_promo:
                # Product photo = text on product is specs/branding, NOT promotional
                promotional_detected = False
                promo_risk = 0.0
                print(f"✅ Promotional check: PRODUCT PHOTO detected → NOT promotional")
            elif is_product_photo and product_photo_confidence > 0.30 and very_strong_promo:
                # Product photo BUT has very strong promo signals (e.g., sticker on product)
                promotional_detected = True
                promo_risk = 0.95  # High confidence - sticker/overlay on product
                print(f"⚠️  Promotional check: PRODUCT PHOTO but STRONG PROMO signals → PROMOTIONAL")
            # SECOND PRIORITY: Image body verification with lower threshold
            # If image shows the actual product body (e.g., RAM module, phone, camera)
            elif image_body_match and body_match_confidence > 0.20:
                # Product body shown = text is definitely product specs, NOT promotional
                promotional_detected = False
                promo_risk = 0.0
                print(f"✅ Promotional check: BODY MATCH detected → NOT promotional")
            # THIRD PRIORITY: Product text-only detection (OCR-based)
            # If text has absolutely NO promotional signals (no price, no phone, no UI)
            elif is_product_text_only:
                # No promotional signals = safe to assume it's product info
                promotional_detected = False
                promo_risk = 0.0
                print(f"✅ Promotional check: PRODUCT TEXT ONLY → NOT promotional")
            # FOURTH PRIORITY: Title/Description matching
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
                
                # Higher risk if multiple signals
                if has_price and has_phone_number:
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
                    "promotional_detected": promotional_detected
                }
            })
            
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
    
    def check_image(self, job_input: Dict[str, Any]) -> Dict[str, Any]:
        """
        Main handler - supports single or multiple images
        """
        try:
            pipeline_mode = job_input.get("pipeline", "full")
            
            # Multiple images
            if "images" in job_input:
                images_list = job_input.get("images", [])
                
                if not images_list:
                    return {"error": "No images provided"}
                
                # Get common fields (shared across all images)
                common_category = job_input.get("category", "unknown")
                common_title = job_input.get("title")  # Optional product title
                common_description = job_input.get("description")  # Optional product description
                
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
                
                return self.process_single_image(image_input, category, pipeline_mode, title, description, image_id, position_id)
            
        except Exception as e:
            return {
                "error": str(e),
                "traceback": traceback.format_exc()
            }


# FastAPI Startup Event
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    global image_checker
    print("🚀 Starting up AI Image Checker server...")
    image_checker = ImageChecker()
    print("✅ Server ready to process images")


# API Endpoints
@app.post("/image_checker")
@app.post("/image_checker/")
async def process_image(data: Dict[str, Any]):
    """HTTP endpoint to check images"""
    if image_checker is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    return image_checker.check_image(data)


@app.post("/image_checker/check")
async def check_endpoint(data: Dict[str, Any]):
    """Alternative /check endpoint"""
    if image_checker is None:
        raise HTTPException(status_code=503, detail="Services not initialized")
    
    return image_checker.check_image(data)


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
