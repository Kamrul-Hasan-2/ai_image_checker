"""
Modal.com Serverless Handler for AI Image Checker - v2.0 OPTIMIZED
Hybrid voting system: OpenCV > OCR > Qwen2-VL > CLIP
"""

import modal
import base64
import io
import requests
from PIL import Image
from typing import Dict, Any, Optional, List
import traceback
import os
import sys

print("Starting Modal handler import... [v2.0 OPTIMIZED]", flush=True)

# Create Modal app
app = modal.App("ai-image-checker")

# Function to pre-download models during image build (GPU Snapshot)
def download_models():
    """Download all models during image build to create a GPU-ready snapshot"""
    import os
    os.environ["TRANSFORMERS_CACHE"] = "/root/.cache/huggingface"
    os.environ["HF_HOME"] = "/root/.cache/huggingface"
    os.environ["TORCH_HOME"] = "/root/.cache/torch"
    
    print("🔧 Pre-downloading models for GPU snapshot...")
    
    # Download Transformers models
    from transformers import CLIPModel, CLIPProcessor, Qwen2VLForConditionalGeneration, AutoProcessor
    print("⬇️ Downloading CLIP model...")
    CLIPModel.from_pretrained("openai/clip-vit-base-patch32")
    CLIPProcessor.from_pretrained("openai/clip-vit-base-patch32")
    
    print("⬇️ Downloading Qwen2-VL-2B model...")
    Qwen2VLForConditionalGeneration.from_pretrained(
        "Qwen/Qwen2-VL-2B-Instruct",
        trust_remote_code=True
    )
    AutoProcessor.from_pretrained("Qwen/Qwen2-VL-2B-Instruct", trust_remote_code=True)
    
    # Download EasyOCR models
    import easyocr
    print("⬇️ Downloading EasyOCR models...")
    os.makedirs('/root/.cache/easyocr', exist_ok=True)
    reader = easyocr.Reader(
        ['en'], 
        gpu=False,
        model_storage_directory='/root/.cache/easyocr',
        download_enabled=True
    )
    
    print("✅ All models downloaded to image snapshot!")

# Define the container image with all dependencies + pre-downloaded models
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
        "sentencepiece",
        "easyocr",
        "opencv-python-headless",
        "requests",
        "torch",
        "torchvision",
    )
    .run_function(download_models, gpu="A10G")  # GPU Snapshot: Pre-download models with A10G (same as runtime)
    .add_local_file("quality_service.py", "/root/quality_service.py")
    .add_local_file("ocr_service.py", "/root/ocr_service.py")
    .add_local_file("clip_service.py", "/root/clip_service.py")
    .add_local_file("qwen_service.py", "/root/qwen_service.py")
)


@app.cls(
    image=image,
    gpu="A10G",  # Nvidia A10G GPU
    cpu=8.0,
    memory=16384,
    timeout=30,  # 30 second timeout
    scaledown_window=15,  # 15 second cooldown before shutdown
    enable_memory_snapshot=True,  
    min_containers=0,  # SHUTS DOWN when not in use (Saves money)
    experimental_options={"enable_gpu_snapshot": True},
)
@modal.concurrent(max_inputs=10)  
class ImageChecker:
    """Modal class for AI Image Checker with GPU support"""
    
    @modal.enter(snap=True)  # ✨ ENABLE snapshot capture for ultra-fast cold starts
    def initialize_services(self):
        """Initialize and WARM UP all services for the GPU Snapshot"""
        import os
        import sys
        import torch
        
        # 1. Set cache directories (models will load from cache automatically)
        os.environ["TRANSFORMERS_CACHE"] = "/root/.cache/huggingface"
        os.environ["HF_HOME"] = "/root/.cache/huggingface"
        os.environ["TORCH_HOME"] = "/root/.cache/torch"
        os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
        os.environ["TRANSFORMERS_VERBOSITY"] = "error"
        
        sys.path.insert(0, "/root")
        
        # Import services AFTER setting env vars
        from quality_service import QualityCheckService
        from ocr_service import OCRService
        from clip_service import CLIPService
        from qwen_service import Qwen2VLService
        
        # 2. Load all services (silent mode)
        self.quality_service = QualityCheckService()
        self.ocr_service = OCRService(languages=['en'])
        self.clip_service = CLIPService(model_name="openai/clip-vit-base-patch32")
        self.qwen2b_service = Qwen2VLService(model_name="Qwen/Qwen2-VL-2B-Instruct")
    
    def load_image(self, image_input: str) -> Image.Image:
        """Load image from URL or base64 string"""
        try:
            # Check if it's a URL
            if image_input.startswith('http://') or image_input.startswith('https://'):
                # Add browser-like headers to avoid 403 Forbidden errors
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    'Accept': 'image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Connection': 'keep-alive',
                    'Referer': image_input.split('/')[0] + '//' + image_input.split('/')[2] + '/',
                }
                response = requests.get(image_input, headers=headers, timeout=2)
                response.raise_for_status()
                image = Image.open(io.BytesIO(response.content))
            # Check if it's base64
            elif image_input.startswith('data:image'):
                # Remove data:image/png;base64, prefix
                base64_str = image_input.split(',')[1]
                image_data = base64.b64decode(base64_str)
                image = Image.open(io.BytesIO(image_data))
            else:
                # Assume raw base64
                image_data = base64.b64decode(image_input)
                image = Image.open(io.BytesIO(image_data))
            
            return image.convert('RGB')
        except Exception as e:
            raise ValueError(f"Failed to load image: {str(e)}")
    
    def process_single_image(self, image_input: str, category: str, pipeline_mode: str) -> Dict[str, Any]:
        """
        HYBRID VOTING SYSTEM: OpenCV > OCR > Qwen2-VL > CLIP
        Priority order ensures hard rules override ML models
        """
        try:
            # Load image
            image = self.load_image(image_input)
            
            # Resize to 192px for speed and accuracy balance
            max_size = 192
            if max(image.size) > max_size:
                ratio = max_size / max(image.size)
                new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
                image = image.resize(new_size, Image.Resampling.LANCZOS)
            
            # ========== STEP 1: OpenCV (HARD FILTER) ==========
            quality_result = self.quality_service.check_image(image)
            opencv_risk = quality_result.get("opencv_risk", 0.0)
            screenshot_confidence = quality_result.get("screenshot_confidence", 0.0)
            blur_confidence = quality_result.get("blur_confidence", 0.0)
            opencv_screenshot_block = screenshot_confidence > 0.7
            
            # ========== STEP 2: OCR (HARD EVIDENCE LAYER) ==========
            ocr_result = self.ocr_service.extract_text(image)
            ocr_risk = ocr_result.get("ocr_risk", 0.0)
            watermark_confidence_ocr = ocr_result.get("watermark_confidence", 0.0)
            promo_confidence_ocr = ocr_result.get("promotional_confidence", 0.0)
            watermark_keywords = ocr_result.get("watermark_keywords_found", False)
            bd_marketplace = ocr_result.get("bd_marketplace_watermark", False)
            promo_keyword_count = ocr_result.get("promo_keyword_count", 0)
            seller_branding = ocr_result.get("seller_branding_detected", False)
            has_phone_number = ocr_result.get("has_phone_number", False)
            has_link = ocr_result.get("has_link", False)
            
            # SKIP CLIP ENTIRELY - only use OpenCV + OCR for maximum speed
            clip_risk = 0.0
            promo_confidence_clip = 0.0
            watermark_confidence_clip = 0.0
            illegal_confidence_clip = 0.0
            
            # ========== STEP 4: Qwen2-VL (ONLY FOR HIGH RISK) ==========
            qwen_risk = 0.0
            qwen_promo_score = 0.0
            qwen_watermark_score = 0.0
            qwen_illegal_score = 0.0
            
            # Make Qwen EXTREMELY rare to trigger (almost never)
            should_escalate = (
                opencv_risk > 0.9 or 
                ocr_risk > 0.9
            )
            
            if should_escalate:
                qwen_result = self.qwen2b_service.moderate_image(image)
                qwen_decision = qwen_result.get("decision", "APPROVE").upper()
                qwen_confidence = qwen_result.get("confidence", 0.0)
                
                if qwen_decision == "BLOCK":
                    qwen_risk = qwen_confidence
                elif qwen_decision == "MANUAL_REVIEW":
                    qwen_risk = 0.5
                
                reasoning = qwen_result.get("reasoning", "").lower()
                qwen_promo_score = 0.8 if "promotional" in reasoning or "advertisement" in reasoning else 0.0
                qwen_watermark_score = 0.8 if "watermark" in reasoning or "logo" in reasoning else 0.0
                qwen_illegal_score = 0.8 if "illegal" in reasoning or "weapon" in reasoning or "drug" in reasoning else 0.0
            
            # ========== HYBRID VOTING SYSTEM ==========
            screenshot_detected = opencv_screenshot_block
            blur_detected = blur_confidence > 0.5
            
            # Simplified scoring - no CLIP
            watermark_risk = ocr_risk * watermark_confidence_ocr + 0.2 * qwen_watermark_score
            watermark_detected = watermark_risk > 0.2 or watermark_keywords or bd_marketplace or watermark_confidence_ocr > 0.6
            
            promo_risk = promo_confidence_ocr + 0.2 * qwen_promo_score
            promotional_detected = promo_risk > 0.35 or promo_keyword_count >= 2 or seller_branding or has_phone_number or has_link
            
            illegal_risk = qwen_illegal_score
            illegal_detected = illegal_risk > 0.8
            
            stock_photo_detected = False
            category_mismatch = False
            
            # 70% OCR, 20% Qwen (rarely used), 10% OpenCV
            final_risk = 0.70 * ocr_risk + 0.20 * qwen_risk + 0.10 * opencv_risk
            risk_level = int(final_risk * 100)
            
            # Build minimal response
            return {
                "blur_image": 5 if blur_detected else 0,
                "screen_short": 8 if screenshot_detected else 0,
                "category_mismatch": 2 if category_mismatch else 0,
                "illegal": 9 if illegal_detected else 0,
                "promotional_text": 3 if promotional_detected else 0,
                "stock_photo": 10 if stock_photo_detected else 0,
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
        Main pipeline handler - supports single or multiple images
        """
        try:
            pipeline_mode = job_input.get("pipeline", "full")
            
            # Check if multiple images
            if "images" in job_input:
                images_list = job_input.get("images", [])
                
                if not images_list:
                    return {"error": "No images provided. Please provide 'images' array."}
                
                # PARALLEL PROCESSING for speed
                from concurrent.futures import ThreadPoolExecutor, as_completed
                
                def process_wrapper(img_data):
                    image_input = img_data.get("image")
                    category = img_data.get("category", "unknown")
                    
                    if not image_input:
                        return {
                            "error": "No image URL provided",
                            "blur_image": 0,
                            "screen_short": 0,
                            "category_mismatch": 0,
                            "illegal": 0,
                            "promotional_text": 0,
                            "stock_photo": 0,
                            "watermark": 0,
                            "risk_level": 0
                        }
                    
                    return self.process_single_image(image_input, category, pipeline_mode)
                
                # Process images in parallel (max 2 threads to avoid contention)
                with ThreadPoolExecutor(max_workers=2) as executor:
                    futures = [executor.submit(process_wrapper, img_data) for img_data in images_list]
                    results = [future.result() for future in futures]
                
                return results
            
            else:
                # Single image mode
                image_input = job_input.get("image")
                category = job_input.get("category", "unknown")
                
                if not image_input:
                    return {"error": "No image provided. Please provide 'image' field with URL or base64 data."}
                
                result = self.process_single_image(image_input, category, pipeline_mode)
                return result
            
        except Exception as e:
            return {
                "error": str(e),
                "traceback": traceback.format_exc()
            }


# Web endpoint for HTTP requests with GPU support
@app.function(
    image=image,
    gpu="A10G",  # GPU for web endpoint
    cpu=4.0,
    memory=16384,
    timeout=30,  # 30 second timeout
    scaledown_window=15,  # 15 second cooldown before shutdown
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
        """
        HTTP endpoint to check images
        POST with JSON body containing image data
        """
        checker = ImageChecker()
        return checker.check_image.local(data)  # Use .local() for same-container execution (sync method)
    
    return web_app


# Local entrypoint for testing
@app.local_entrypoint()
def main():
    """Test the image checker locally"""
    # Example test
    test_input = {
        "image": "https://example.com/test-image.jpg",
        "category": "laptop",
        "pipeline": "full"
    }
    
    checker = ImageChecker()
    result = checker.check_image.remote(test_input)
    print("Result:", result)

