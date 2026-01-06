"""
RunPod Serverless Handler for AI Image Checker
Integrates with quality, OCR, CLIP, and Qwen2-VL services
"""

import runpod
import base64
import io
import requests
from PIL import Image
from typing import Dict, Any, Optional
import traceback
import sys

print("Starting handler import...", flush=True)

try:
    from quality_service import QualityCheckService
    print("✓ QualityCheckService imported", flush=True)
except Exception as e:
    print(f"✗ Failed to import QualityCheckService: {e}", flush=True)
    traceback.print_exc()
    
try:
    from ocr_service import OCRService
    print("✓ OCRService imported", flush=True)
except Exception as e:
    print(f"✗ Failed to import OCRService: {e}", flush=True)
    traceback.print_exc()
    
try:
    from clip_service import CLIPService
    print("✓ CLIPService imported", flush=True)
except Exception as e:
    print(f"✗ Failed to import CLIPService: {e}", flush=True)
    traceback.print_exc()
    
try:
    from qwen_service import Qwen2VLService
    print("✓ Qwen2VLService imported", flush=True)
except Exception as e:
    print(f"✗ Failed to import Qwen2VLService: {e}", flush=True)
    traceback.print_exc()


# Global services - initialized once per worker
quality_service: Optional[QualityCheckService] = None
ocr_service: Optional[OCRService] = None
clip_service: Optional[CLIPService] = None
qwen2b_service: Optional[Qwen2VLService] = None


def initialize_services():
    """Initialize all AI services once at worker startup"""
    global quality_service, ocr_service, clip_service, qwen2b_service
    
    if quality_service is None:
        print("🔧 Initializing AI Services...")
        
        print("[1/4] Loading Quality Check Service...")
        quality_service = QualityCheckService()
        
        print("[2/4] Loading OCR Service...")
        ocr_service = OCRService(languages=['en'])
        
        print("[3/4] Loading CLIP Service...")
        clip_service = CLIPService(model_name="openai/clip-vit-base-patch32")
        
        print("[4/4] Loading Qwen2-VL-2B Service...")
        qwen2b_service = Qwen2VLService(model_name="Qwen/Qwen2-VL-2B-Instruct")
        
        print("✅ All services initialized!")


def load_image(image_input: str) -> Image.Image:
    """Load image from URL or base64 string"""
    try:
        # Check if it's a URL
        if image_input.startswith('http://') or image_input.startswith('https://'):
            response = requests.get(image_input, timeout=10)
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


def check_image_quality(image: Image.Image) -> Dict[str, Any]:
    """Step 1: Quality check"""
    global quality_service
    try:
        result = quality_service.check_image(image)
        checks = result.get("checks", {})
        
        # Get blur details from new multi-algorithm detection
        blur_check = checks.get("blur", {})
        blur_details = blur_check.get("details", {})
        
        return {
            "step": "quality_check",
            "passed": result["passed"],
            "confidence": 1.0 if result["passed"] else 0.0,
            "details": {
                "blur_detection": "yes" if not blur_check.get("passed") else "no",
                "blur_score": blur_details.get("combined_score", blur_details.get("laplacian_var", 0)),
                "quality_grade": blur_details.get("quality_grade", "unknown"),
                "screenshot_check": "yes" if not checks.get("screenshot_ui", {}).get("passed") else "no",
                "corruption_check": "yes" if not checks.get("corrupted", {}).get("passed") else "no",
                "resolution": f"{image.width}x{image.height}"
            }
        }
    except Exception as e:
        return {
            "step": "quality_check",
            "error": str(e),
            "passed": False,
            "confidence": 0.0
        }


def check_with_ocr(image: Image.Image, category: str) -> Dict[str, Any]:
    """Step 2: OCR check - only extract text"""
    global ocr_service
    try:
        result = ocr_service.extract_text(image)
        full_text = result.get("full_text", "")
        
        return {
            "step": "ocr_check",
            "passed": len(full_text) > 0,
            "confidence": 0.5,
            "extracted_text": full_text
        }
    except Exception as e:
        return {
            "step": "ocr_check",
            "error": str(e),
            "passed": False,
            "confidence": 0.0,
            "extracted_text": ""
        }


def check_with_clip(image: Image.Image, category: str) -> Dict[str, Any]:
    """Step 3: CLIP check"""
    global clip_service
    try:
        result = clip_service.analyze_image(image)
        risk_analysis = result.get("risk_analysis", {})
        promo_analysis = result.get("promo_analysis", {})
        category_analysis = result.get("category_analysis", {})
        illegal_check = result.get("illegal_check", {})
        
        # Calculate risk level from weighted risk scoring
        risk_level = int(risk_analysis.get("weighted_risk_level", 0))
        
        return {
            "step": "clip_check",
            "passed": risk_level < 85,
            "confidence": 1.0 - (risk_level / 100.0),
            "details": {
                "category": category,
                "category_match": "no",  # Can add category matching if needed
                "has_brand_indicators": "no",
                "has_phone_number": "no",
                "has_prices": "no",
                "has_promotional_text": "yes" if promo_analysis.get("is_promotional", False) else "no",
                "has_website_link": "no",
                "is_promotional": "yes" if promo_analysis.get("is_promotional", False) else "no",
                "promotional_score": promo_analysis.get("promo_score", 0),
                "stock_photo": "no",
                "illegal_photo": "yes" if illegal_check.get("is_illegal", False) else "no",
                "illegal_confidence": illegal_check.get("confidence", 0),
                "risk_level": risk_level,
                "max_risk_category": risk_analysis.get("max_risk_category", "unknown")
            }
        }
    except Exception as e:
        return {
            "step": "clip_check",
            "error": str(e),
            "passed": False,
            "confidence": 0.0,
            "details": {"risk_level": 0}
        }


def check_with_qwen(image: Image.Image, category: str, image_url: Optional[str] = None) -> Dict[str, Any]:
    """Step 4: Qwen2-VL check (only if risk >= 85)"""
    global qwen2b_service
    try:
        result = qwen2b_service.moderate_image(image)
        decision = result.get("decision", "BLOCK").upper()
        
        return {
            "step": "qwen_check",
            "passed": decision == "APPROVE",
            "confidence": result.get("confidence", 0.0),
            "reasoning": result.get("reasoning", ""),
            "decision": decision
        }
    except Exception as e:
        return {
            "step": "qwen_check",
            "error": str(e),
            "passed": False,
            "confidence": 0.0
        }


def process_single_image(image_input: str, category: str, pipeline_mode: str) -> Dict[str, Any]:
    """
    Process a single image through the pipeline - Returns plain JSON format with severity scores
    """
    try:
        # Load image
        print(f"📸 Loading image for category: {category}")
        image = load_image(image_input)
        
        # Step 1: Quality Check
        print("🔍 Step 1: Quality Check")
        quality_result = check_image_quality(image)
        quality_details = quality_result.get("details", {})
        
        # Step 2: OCR Check
        print("📝 Step 2: OCR Check")
        ocr_result = check_with_ocr(image, category)
        
        # Step 3: CLIP Check
        print("🎨 Step 3: CLIP Check")
        clip_result = check_with_clip(image, category)
        clip_details = clip_result.get("details", {})
        
        # Convert yes/no to severity scores
        blur_detected = quality_details.get("blur_detection", "no") == "yes"
        screenshot_detected = quality_details.get("screenshot_check", "no") == "yes"
        promotional_detected = clip_details.get("has_promotional_text", "no") == "yes"
        illegal_detected = clip_details.get("illegal_photo", "no") == "yes"
        stock_photo_detected = clip_details.get("stock_photo", "no") == "yes"
        watermark_detected = False  # Add watermark detection if available
        category_mismatch = False  # Disabled for now - needs proper category matching
        
        # Build minimal response with only severity scores
        response = {
            "blur_image": 5 if blur_detected else 0,
            "screen_short": 8 if screenshot_detected else 0,
            "category_mismatch": 2 if category_mismatch else 0,
            "illegal": 9 if illegal_detected else 0,
            "promotional_text": 3 if promotional_detected else 0,
            "stock_photo": 10 if stock_photo_detected else 0,
            "watermark": 4 if watermark_detected else 0,
            "risk_level": clip_details.get("risk_level", 0)
        }
        
        # Step 4: Qwen2-VL if risk >= 85
        risk_level = clip_details.get("risk_level", 0)
        if risk_level >= 85:
            print("🤖 Step 4: Qwen2-VL Check (High Risk)")
            qwen_result = check_with_qwen(image, category, image_input if image_input.startswith('http') else None)
            response["qwen_needs_moderation"] = not qwen_result.get("passed", False)
        
        return response
        
    except Exception as e:
        print(f"❌ Error processing image: {str(e)}")
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


def run_pipeline(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main pipeline handler - supports single or multiple images
    
    Input format (single image):
    {
        "input": {
            "image": "url or base64",
            "category": "product category to match",
            "pipeline": "full" (default) or "fast" or "quality_only"
        }
    }
    
    Input format (multiple images):
    {
        "input": {
            "images": [
                {"image": "url1", "category": "laptop"},
                {"image": "url2", "category": "phone"}
            ],
            "pipeline": "full" (default) or "fast" or "quality_only"
        }
    }
    """
    try:
        # Initialize services if needed
        initialize_services()
        
        # Extract input
        job_input = job.get("input", {})
        pipeline_mode = job_input.get("pipeline", "full")
        
        # Check if multiple images
        if "images" in job_input:
            # Multiple images mode
            images_list = job_input.get("images", [])
            
            if not images_list:
                return {"error": "No images provided. Please provide 'images' array."}
            
            print(f"\n🔄 Processing {len(images_list)} images...")
            
            results = []
            
            # Process each image
            for idx, img_data in enumerate(images_list, 1):
                print(f"\n{'='*60}")
                print(f"Processing Image {idx}/{len(images_list)}")
                print(f"{'='*60}")
                
                image_input = img_data.get("image")
                category = img_data.get("category", "unknown")
                
                if not image_input:
                    results.append({
                        "error": "No image URL provided",
                        "blur_image": 0,
                        "screen_short": 0,
                        "category_mismatch": 0,
                        "illegal": 0,
                        "promotional_text": 0,
                        "stock_photo": 0,
                        "watermark": 0,
                        "risk_level": 0
                    })
                    continue
                
                # Process single image
                result = process_single_image(image_input, category, pipeline_mode)
                results.append(result)
            
            return results
        
        else:
            # Single image mode (backward compatible)
            image_input = job_input.get("image")
            category = job_input.get("category", "unknown")
            
            if not image_input:
                return {"error": "No image provided. Please provide 'image' field with URL or base64 data."}
            
            print(f"\n📸 Processing single image...")
            result = process_single_image(image_input, category, pipeline_mode)
            return result
        
    except Exception as e:
        print(f"❌ Error in pipeline: {str(e)}")
        print(traceback.format_exc())
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# RunPod handler
runpod.serverless.start({"handler": run_pipeline})
