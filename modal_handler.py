"""
Modal.com Serverless Handler for AI Image Checker
Clean implementation with GPU snapshot optimization
"""

import modal
import base64
import io
import requests
from PIL import Image
from typing import Dict, Any
import traceback

# Create Modal app
app = modal.App("ai-image-checker")

# Function to pre-download models during image build
def download_models():
    """Download all models during image build for GPU snapshot"""
    import os
    os.environ["TRANSFORMERS_CACHE"] = "/root/.cache/huggingface"
    os.environ["HF_HOME"] = "/root/.cache/huggingface"
    
    print("Downloading models...")
    
    from transformers import CLIPModel, CLIPProcessor, Qwen2VLForConditionalGeneration, AutoProcessor
    
    CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    
    Qwen2VLForConditionalGeneration.from_pretrained(
        "Qwen/Qwen2-VL-2B-Instruct",
        trust_remote_code=True
    )
    AutoProcessor.from_pretrained("Qwen/Qwen2-VL-2B-Instruct", trust_remote_code=True)
    
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
        from qwen_service import Qwen2VLService
        
        self.quality_service = QualityCheckService()
        self.ocr_service = OCRService(languages=['en'])
        self.clip_service = CLIPService(model_name="openai/clip-vit-base-patch32")
        self.qwen2b_service = Qwen2VLService(model_name="Qwen/Qwen2-VL-2B-Instruct")
    
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
    
    def process_single_image(self, image_input: str, category: str, pipeline_mode: str, title: str = None) -> Dict[str, Any]:
        """
        Process a single image through the AI pipeline
        
        Args:
            image_input: Image URL or base64 string
            category: Product category
            pipeline_mode: Processing mode (full/fast)
            title: Optional product title to match against OCR text
        """
        # Exception categories where promotional_text is always 0
        exception_categories = [
            "car", "car accessories",
            "bike", "bike accessories",
            "three wheeler", "bicycle", "bicycle accessories",
            "commercial vehicle", "rental", "vehicle equipment"
        ]
        
        is_exception_category = category.lower().strip() in exception_categories
        
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
            promotional_detected_ocr = ocr_result.get("promotional_detected", False)
            
            # NEW: Visual promo indicators
            visual_promo_score = ocr_result.get("visual_promo_score", 0.0)
            strong_price_indicator = ocr_result.get("strong_price_indicator", False)
            has_button_ui = ocr_result.get("has_button_ui", False)
            digit_count = ocr_result.get("digit_count", 0)
            
            # CRITICAL: Check if image shows actual product (using CLIP)
            # If it's a product photo, text on it is part of the product, NOT promotional
            product_check = self.clip_service.detect_product_photo(image)
            is_product_photo = product_check.get("is_product_photo", False)
            product_photo_confidence = product_check.get("product_score", 0.0)
            
            # NEW: Check if product title matches OCR text
            # If title matches, text is the product name, NOT promotional
            is_title_match = False
            if title:
                full_text = ocr_result.get("full_text", "").lower()
                title_lower = title.lower().strip()
                # Check if title words appear in OCR text (fuzzy match)
                title_words = [w for w in title_lower.split() if len(w) > 1]  # Filter short words (>1 char)
                # Consider match if >= 60% of significant title words found in OCR text
                if len(title_words) > 0:
                    matched_words = sum(1 for word in title_words if word in full_text)
                    match_ratio = matched_words / len(title_words)
                    is_title_match = match_ratio >= 0.6
            
            # CLIP analysis (skipped for speed - can be enabled if needed)
            clip_risk = 0.0
            
            # SKIP Qwen2-VL for speed - rely only on fast OCR detection
            qwen_risk = 0.0
            qwen_promo_score = 0.0
            qwen_watermark_score = 0.0
            qwen_illegal_score = 0.0
            
            # Calculate final scores
            screenshot_detected = screenshot_confidence > 0.7
            # FIX: Check if blur check FAILED (not passed) instead of using confidence threshold
            blur_detected = not quality_result['checks']['blur']['passed']
            
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
            promo_risk = promo_confidence_ocr
            if is_title_match:
                # Product title matches OCR text = text is product name, NOT promotional
                promotional_detected = False
                promo_risk = 0.0
            elif is_product_photo:
                # Product photo detected visually = text is part of product, NOT promotional
                promotional_detected = False
                promo_risk = 0.0
            elif is_product_text_only:
                # Product branding/logos = NOT promotional
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
            promo_score = 0
            if promotional_detected:
                # High severity combinations
                if has_price and has_phone_number:
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
            
            return {
                "blur_image": 5 if blur_detected else 0,
                "screen_short": 8 if screenshot_detected else 0,
                "category_mismatch": 0,
                "illegal": 0,  # Always 0 - hardcoded
                "promotional_text": 0 if is_exception_category else promo_score,
                "stock_photo": 0,
                "watermark": 4 if watermark_detected else 0,
                "risk_level": risk_level
            }
            
        except Exception as e:
            return {
                "error": str(e),
                "blur_image": 0,
                "screen_short": 0,
                "category_mismatch": 0,
                "illegal": 0,
                "promotional_text": 0,
                "stock_photo": 0,
                "watermark": 0,
                "risk_level": 0
            }
    
    @modal.method()
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
                
                results = []
                for img_data in images_list:
                    image_input = img_data.get("image")
                    category = img_data.get("category", "unknown")
                    title = img_data.get("title")  # Optional product title
                    
                    if not image_input:
                        results.append({"error": "No image URL provided", "risk_level": 0})
                    else:
                        result = self.process_single_image(image_input, category, pipeline_mode, title)
                        results.append(result)
                
                return results
            
            # Single image
            else:
                image_input = job_input.get("image")
                category = job_input.get("category", "unknown")
                title = job_input.get("title")  # Optional product title
                
                if not image_input:
                    return {"error": "No image provided"}
                
                return self.process_single_image(image_input, category, pipeline_mode, title)
            
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

