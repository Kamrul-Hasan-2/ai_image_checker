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
        checks = result.get("checks", {})
        
        return {
            "step": "quality_check",
            "passed": result["passed"],
            "confidence": 1.0 if result["passed"] else 0.0,
            "details": {
                "blur_detection": "no" if checks.get("blur", {}).get("passed") else "yes",
                "blur_score": checks.get("blur", {}).get("details", {}).get("blur_score", 0),
                "screenshot_check": "no" if checks.get("screenshot_ui", {}).get("passed") else "yes",
                "corruption_check": "no" if checks.get("corrupted", {}).get("passed") else "yes",
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
    """Step 2: OCR check"""
    try:
        result = ocr_service.extract_text(image)
        full_text = result.get("full_text", "")
        
        return {
            "step": "ocr_check",
            "passed": len(full_text) > 0,
            "confidence": result.get("average_confidence", 0.5),
            "image_extract": full_text[:200] if full_text else "No text detected"
        }
    except Exception as e:
        return {
            "step": "ocr_check",
            "error": str(e),
            "passed": False,
            "confidence": 0.0,
            "image_extract": ""
        }


def check_with_clip(image: Image.Image, category: str) -> Dict[str, Any]:
    """Step 3: CLIP check"""
    try:
        result = clip_service.analyze_image(image)
        risk_analysis = result.get("risk_analysis", {})
        category_match = result.get("category_match", {})
        
        return {
            "step": "clip_check",
            "passed": risk_analysis.get("risk_level", 0) < 85,
            "confidence": category_match.get("score", 0.0),
            "details": {
                "has_brand_indicators": "yes" if risk_analysis.get("has_brand_indicators") else "no",
                "has_phone_number": "yes" if risk_analysis.get("has_phone_number") else "no",
                "has_prices": "yes" if risk_analysis.get("has_prices") else "no",
                "has_promotional_text": "yes" if risk_analysis.get("has_promotional_text") else "no",
                "has_website_link": "yes" if risk_analysis.get("has_website_link") else "no",
                "is_promotional": "yes" if risk_analysis.get("is_promotional") else "no",
                "stock_photo": "no",  # Add stock photo detection if available
                "illegal_photo": "no",  # Add illegal content detection if available
                "category": category_match.get("category", category),
                "category_match": "yes" if category_match.get("score", 0) > 0.5 else "no",
                "risk_level": risk_analysis.get("risk_level", 0)
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
    Process a single image through the pipeline
    """
    try:
        # Load image
        print(f"📸 Loading image for category: {category}")
        image = load_image(image_input)
        
        results = {
            "image": image_input[:100] + "..." if len(image_input) > 100 else image_input,
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
        
        # Step 3: CLIP Check (always run to get risk level)
        print("🎨 Step 3: CLIP Check")
        clip_result = check_with_clip(image, category)
        results["steps"].append(clip_result)
        
        risk_level = clip_result.get("details", {}).get("risk_level", 0)
        results["risk_level"] = risk_level
        
        # Only call Qwen2-VL if risk level >= 85
        if risk_level >= 85:
            print("🤖 Step 4: Qwen2-VL Check (High Risk)")
            image_url = image_input if image_input.startswith('http') else None
            qwen_result = check_with_qwen(image, category, image_url)
            results["steps"].append(qwen_result)
            
            results["final_decision"] = qwen_result["passed"]
            results["final_confidence"] = qwen_result["confidence"]
            results["matched_at"] = "qwen"
            results["reasoning"] = qwen_result.get("reasoning", "")
        else:
            # Low risk - auto approve based on CLIP
            results["final_decision"] = clip_result["passed"]
            results["final_confidence"] = clip_result["confidence"]
            results["matched_at"] = "clip"
            results["reasoning"] = f"Risk level {risk_level} is below threshold (85), auto-approved"
        
        return results
        
    except Exception as e:
        print(f"❌ Error processing image: {str(e)}")
        return {
            "image": image_input[:100] + "..." if len(image_input) > 100 else image_input,
            "category": category,
            "error": str(e),
            "final_decision": False,
            "final_confidence": 0.0
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
            
            results = {
                "mode": "batch",
                "total_images": len(images_list),
                "pipeline_mode": pipeline_mode,
                "results": []
            }
            
            # Process each image
            for idx, img_data in enumerate(images_list, 1):
                print(f"\n{'='*60}")
                print(f"Processing Image {idx}/{len(images_list)}")
                print(f"{'='*60}")
                
                image_input = img_data.get("image")
                category = img_data.get("category", "unknown")
                
                if not image_input:
                    results["results"].append({
                        "image_index": idx,
                        "error": "No image URL provided",
                        "final_decision": False
                    })
                    continue
                
                # Process single image
                result = process_single_image(image_input, category, pipeline_mode)
                result["image_index"] = idx
                results["results"].append(result)
            
            # Summary
            approved = sum(1 for r in results["results"] if r.get("final_decision", False))
            rejected = len(results["results"]) - approved
            
            results["summary"] = {
                "approved": approved,
                "rejected": rejected,
                "success_rate": f"{(approved/len(results['results'])*100):.1f}%" if results["results"] else "0%"
            }
            
            return results
        
        else:
            # Single image mode (backward compatible)
            image_input = job_input.get("image")
            category = job_input.get("category", "unknown")
            
            if not image_input:
                return {"error": "No image provided. Please provide 'image' field with URL or base64 data."}
            
            print(f"\n📸 Processing single image...")
            result = process_single_image(image_input, category, pipeline_mode)
            result["mode"] = "single"
            
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
