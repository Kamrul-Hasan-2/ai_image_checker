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
        watermark_check = result.get("watermark_check", {})
        
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
                "has_watermark": watermark_check.get("has_watermark", False),
                "watermark_type": watermark_check.get("watermark_type"),
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
    HYBRID VOTING SYSTEM: OpenCV > OCR > Qwen2-VL > CLIP
    Priority order ensures hard rules override ML models
    """
    try:
        # Load image
        print(f"📸 Loading image for category: {category}")
        image = load_image(image_input)
        
        # ========== STEP 1: OpenCV (HARD FILTER - HIGHEST PRIORITY) ==========
        print("🔍 Step 1: OpenCV Quality Check (HARD FILTER)")
        quality_result = quality_service.check_image(image)
        opencv_risk = quality_result.get("opencv_risk", 0.0)
        screenshot_confidence = quality_result.get("screenshot_confidence", 0.0)
        blur_confidence = quality_result.get("blur_confidence", 0.0)
        
        # HARD RULE: If OpenCV detects screenshot > 0.7, BLOCK immediately
        opencv_screenshot_block = screenshot_confidence > 0.7
        print(f"   OpenCV Risk: {opencv_risk:.2f} | Screenshot: {screenshot_confidence:.2f} | Blur: {blur_confidence:.2f}")
        if opencv_screenshot_block:
            print("   ⚠️ BLOCKED by OpenCV (screenshot detected)")
        
        # ========== STEP 2: OCR (HARD EVIDENCE LAYER) ==========
        print("📝 Step 2: OCR + Rule-Based Detection (HARD EVIDENCE)")
        ocr_result = ocr_service.extract_text(image)
        ocr_risk = ocr_result.get("ocr_risk", 0.0)
        watermark_confidence_ocr = ocr_result.get("watermark_confidence", 0.0)
        promo_confidence_ocr = ocr_result.get("promotional_confidence", 0.0)
        watermark_keywords = ocr_result.get("watermark_keywords_found", False)
        promo_keyword_count = ocr_result.get("promo_keyword_count", 0)
        seller_branding = ocr_result.get("seller_branding_detected", False)
        
        print(f"   OCR Risk: {ocr_risk:.2f} | Watermark: {watermark_confidence_ocr:.2f} | Promo: {promo_confidence_ocr:.2f}")
        print(f"   Watermark Keywords: {watermark_keywords} | Promo Keywords: {promo_keyword_count} | Seller Branding: {seller_branding}")
        
        # ========== STEP 3: CLIP (WEAK SIGNAL) ==========
        print("🎨 Step 3: CLIP Visual Analysis (WEAK SIGNAL)")
        clip_result = clip_service.analyze_image(image)
        
        risk_analysis = clip_result.get("risk_analysis", {})
        promo_analysis = clip_result.get("promo_analysis", {})
        illegal_check = clip_result.get("illegal_check", {})
        watermark_check = clip_result.get("watermark_check", {})
        
        clip_risk = risk_analysis.get("weighted_risk_level", 0) / 100.0
        promo_confidence_clip = promo_analysis.get("confidence", 0.0)
        watermark_confidence_clip = watermark_check.get("confidence", 0.0)
        illegal_confidence_clip = illegal_check.get("confidence", 0.0)
        
        print(f"   CLIP Risk: {clip_risk:.2f} | Promo: {promo_confidence_clip:.2f} | Watermark: {watermark_confidence_clip:.2f} | Illegal: {illegal_confidence_clip:.2f}")
        
        # ========== STEP 4: Qwen2-VL (REASONING MODEL) ==========
        qwen_risk = 0.0
        qwen_promo_score = 0.0
        qwen_watermark_score = 0.0
        qwen_illegal_score = 0.0
        
        # Only call Qwen if any model shows elevated risk
        should_escalate = (
            opencv_risk > 0.5 or 
            ocr_risk > 0.5 or 
            clip_risk > 0.55 or
            illegal_confidence_clip > 0.7
        )
        
        if should_escalate:
            print("🤖 Step 4: Qwen2-VL Reasoning (ESCALATED)")
            qwen_result = qwen2b_service.moderate_image(image)
            qwen_decision = qwen_result.get("decision", "APPROVE").upper()
            qwen_confidence = qwen_result.get("confidence", 0.0)
            
            # Convert Qwen decision to risk scores
            if qwen_decision == "BLOCK":
                qwen_risk = qwen_confidence
            elif qwen_decision == "MANUAL_REVIEW":
                qwen_risk = 0.5
            else:
                qwen_risk = 0.0
            
            # Parse reasoning for specific flags (simplified)
            reasoning = qwen_result.get("reasoning", "").lower()
            qwen_promo_score = 0.8 if "promotional" in reasoning or "advertisement" in reasoning else 0.0
            qwen_watermark_score = 0.8 if "watermark" in reasoning or "logo" in reasoning else 0.0
            qwen_illegal_score = 0.8 if "illegal" in reasoning or "weapon" in reasoning or "drug" in reasoning else 0.0
            
            print(f"   Qwen Decision: {qwen_decision} | Confidence: {qwen_confidence:.2f}")
        else:
            print("   Qwen2-VL SKIPPED (low risk)")
        
        # ========== HYBRID VOTING SYSTEM ==========
        print("🗳️  Hybrid Voting System (Priority: OpenCV > OCR > Qwen > CLIP)")
        
        # SCREENSHOT DETECTION (OpenCV is FINAL)
        screenshot_detected = opencv_screenshot_block
        
        # BLUR DETECTION (OpenCV only)
        blur_detected = blur_confidence > 0.5
        
        # WATERMARK DETECTION (Weighted voting)
        watermark_risk = (
            0.50 * ocr_risk * watermark_confidence_ocr +  # OCR keywords = strongest
            0.30 * qwen_watermark_score +                 # Qwen reasoning
            0.20 * watermark_confidence_clip              # CLIP weakest
        )
        watermark_detected = watermark_risk > 0.5 or watermark_keywords
        print(f"   Watermark Risk: {watermark_risk:.2f} (OCR: {watermark_confidence_ocr:.2f}, Qwen: {qwen_watermark_score:.2f}, CLIP: {watermark_confidence_clip:.2f})")
        
        # PROMOTIONAL DETECTION (Weighted voting)
        promo_risk = (
            0.50 * promo_confidence_ocr +      # OCR keywords = strongest
            0.30 * qwen_promo_score +          # Qwen reasoning
            0.20 * promo_confidence_clip       # CLIP weakest
        )
        # HARD RULE: Seller branding is promotional
        promotional_detected = promo_risk > 0.5 or promo_keyword_count >= 3 or seller_branding
        print(f"   Promo Risk: {promo_risk:.2f} (OCR: {promo_confidence_ocr:.2f}, Qwen: {qwen_promo_score:.2f}, CLIP: {promo_confidence_clip:.2f}, Seller: {seller_branding})")
        
        # ILLEGAL DETECTION (Very strict - requires high Qwen + CLIP agreement)
        illegal_risk = (
            0.60 * qwen_illegal_score +        # Qwen reasoning most important
            0.40 * illegal_confidence_clip     # CLIP backup
        )
        illegal_detected = illegal_risk > 0.8 or (qwen_illegal_score > 0.7 and illegal_confidence_clip > 0.9)
        print(f"   Illegal Risk: {illegal_risk:.2f} (Qwen: {qwen_illegal_score:.2f}, CLIP: {illegal_confidence_clip:.2f})")
        
        # STOCK PHOTO DETECTION (CLIP only for now)
        stock_photo_detected = False  # Disabled - needs specific implementation
        
        # CATEGORY MISMATCH (Disabled)
        category_mismatch = False
        
        # FINAL RISK CALCULATION (Weighted formula)
        final_risk = (
            0.40 * ocr_risk +
            0.35 * qwen_risk +
            0.15 * clip_risk +
            0.10 * opencv_risk
        )
        risk_level = int(final_risk * 100)
        
        print(f"📊 FINAL RISK: {risk_level}% (OCR: {ocr_risk:.2f}, Qwen: {qwen_risk:.2f}, CLIP: {clip_risk:.2f}, OpenCV: {opencv_risk:.2f})")
        print(f"📋 DETECTION SUMMARY:")
        print(f"   Screenshot: {screenshot_detected} | Blur: {blur_detected} | Watermark: {watermark_detected}")
        print(f"   Promotional: {promotional_detected} | Illegal: {illegal_detected} | Stock: {stock_photo_detected}")
        
        # Build minimal response with only severity scores (SAME FORMAT)
        response = {
            "blur_image": 5 if blur_detected else 0,
            "screen_short": 8 if screenshot_detected else 0,
            "category_mismatch": 2 if category_mismatch else 0,
            "illegal": 9 if illegal_detected else 0,
            "promotional_text": 3 if promotional_detected else 0,
            "stock_photo": 10 if stock_photo_detected else 0,
            "watermark": 4 if watermark_detected else 0,
            "risk_level": risk_level
        }
        
        return response
        
    except Exception as e:
        print(f"❌ Error processing image: {str(e)}")
        import traceback
        traceback.print_exc()
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
