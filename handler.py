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
    try:
        result = quality_service.check_image(image)
        return {
            "step": "quality_check",
            "passed": result["passed"],
            "confidence": 1.0 if result["passed"] else 0.0,
            "details": result
        }
    except Exception as e:
        return {
            "step": "quality_check",
            "error": str(e),
            "passed": False,
            "confidence": 0.0
        }


def check_with_ocr(image: Image.Image, category: str) -> Dict[str, Any]:
    """Step 2: OCR check"""
    try:
        result = ocr_service.check_category(image, category)
        return {
            "step": "ocr_check",
            "passed": result["match"],
            "confidence": result.get("confidence", 0.0),
            "detected_text": result.get("detected_text", []),
            "details": result
        }
    except Exception as e:
        return {
            "step": "ocr_check",
            "error": str(e),
            "passed": False,
            "confidence": 0.0
        }


def check_with_clip(image: Image.Image, category: str) -> Dict[str, Any]:
    """Step 3: CLIP check"""
    try:
        result = clip_service.check_category(image, category)
        return {
            "step": "clip_check",
            "passed": result["match"],
            "confidence": result.get("similarity", 0.0),
            "details": result
        }
    except Exception as e:
        return {
            "step": "clip_check",
            "error": str(e),
            "passed": False,
            "confidence": 0.0
        }


def check_with_qwen(image: Image.Image, category: str, image_url: Optional[str] = None) -> Dict[str, Any]:
    """Step 4: Qwen2-VL check"""
    try:
        result = qwen2b_service.check_category(image, category, image_url)
        return {
            "step": "qwen_check",
            "passed": result["match"],
            "confidence": result.get("confidence", 0.0),
            "reasoning": result.get("reasoning", ""),
            "details": result
        }
    except Exception as e:
        return {
            "step": "qwen_check",
            "error": str(e),
            "passed": False,
            "confidence": 0.0
        }


def run_pipeline(job: Dict[str, Any]) -> Dict[str, Any]:
    """
    Main pipeline handler
    
    Input format:
    {
        "input": {
            "image": "url or base64",
            "category": "product category to match",
            "pipeline": "full" (default) or "fast" or "quality_only"
        }
    }
    """
    try:
        # Initialize services if needed
        initialize_services()
        
        # Extract input
        job_input = job.get("input", {})
        image_input = job_input.get("image")
        category = job_input.get("category", "unknown")
        pipeline_mode = job_input.get("pipeline", "full")
        
        if not image_input:
            return {"error": "No image provided. Please provide 'image' field with URL or base64 data."}
        
        # Load image
        print(f"📸 Loading image for category: {category}")
        image = load_image(image_input)
        
        results = {
            "category": category,
            "pipeline_mode": pipeline_mode,
            "steps": []
        }
        
        # Step 1: Quality Check
        print("🔍 Step 1: Quality Check")
        quality_result = check_image_quality(image)
        results["steps"].append(quality_result)
        
        if pipeline_mode == "quality_only":
            results["final_decision"] = quality_result["passed"]
            results["final_confidence"] = quality_result["confidence"]
            return results
        
        if not quality_result["passed"]:
            results["final_decision"] = False
            results["final_confidence"] = quality_result["confidence"]
            results["reason"] = "Failed quality check"
            return results
        
        # Step 2: OCR Check
        print("📝 Step 2: OCR Check")
        ocr_result = check_with_ocr(image, category)
        results["steps"].append(ocr_result)
        
        if ocr_result["passed"]:
            results["final_decision"] = True
            results["final_confidence"] = ocr_result["confidence"]
            results["matched_at"] = "ocr"
            return results
        
        if pipeline_mode == "fast":
            results["final_decision"] = False
            results["final_confidence"] = ocr_result["confidence"]
            results["reason"] = "Failed OCR check (fast mode)"
            return results
        
        # Step 3: CLIP Check
        print("🎨 Step 3: CLIP Check")
        clip_result = check_with_clip(image, category)
        results["steps"].append(clip_result)
        
        if clip_result["passed"]:
            results["final_decision"] = True
            results["final_confidence"] = clip_result["confidence"]
            results["matched_at"] = "clip"
            return results
        
        # Step 4: Qwen2-VL Check
        print("🤖 Step 4: Qwen2-VL Check")
        image_url = image_input if image_input.startswith('http') else None
        qwen_result = check_with_qwen(image, category, image_url)
        results["steps"].append(qwen_result)
        
        results["final_decision"] = qwen_result["passed"]
        results["final_confidence"] = qwen_result["confidence"]
        results["matched_at"] = "qwen" if qwen_result["passed"] else "none"
        results["reasoning"] = qwen_result.get("reasoning", "")
        
        return results
        
    except Exception as e:
        print(f"❌ Error in pipeline: {str(e)}")
        print(traceback.format_exc())
        return {
            "error": str(e),
            "traceback": traceback.format_exc()
        }


# RunPod handler
runpod.serverless.start({"handler": run_pipeline})
