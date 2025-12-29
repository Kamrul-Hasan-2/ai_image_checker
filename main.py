"""
FastAPI Server for AI Image Checker
5-Step Smart Pipeline with Escalation Logic
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
import io
from typing import Optional
import uvicorn
import requests

from quality_service import QualityCheckService
from ocr_service import OCRService
from clip_service import CLIPService
from qwen_service import Qwen2VLService


app = FastAPI(
    title="AI Image Checker - Smart Pipeline",
    description="5-Step Escalation: Quality → OCR → CLIP → Qwen2B → Qwen7B",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global services
quality_service: Optional[QualityCheckService] = None
ocr_service: Optional[OCRService] = None
clip_service: Optional[CLIPService] = None
qwen2b_service: Optional[Qwen2VLService] = None
qwen7b_service: Optional[Qwen2VLService] = None


class ImageURLRequest(BaseModel):
    image_url: str


@app.on_event("startup")
async def startup_event():
    """Load all models"""
    global quality_service, ocr_service, clip_service, qwen2b_service, qwen7b_service
    
    print("=" * 70)
    print("AI IMAGE CHECKER - SMART PIPELINE v3.0")
    print("=" * 70)
    
    print("\n[1/5] OpenCV Quality Check...")
    quality_service = QualityCheckService()
    
    print("\n[2/5] EasyOCR (CPU)...")
    ocr_service = OCRService(languages=['en'])
    
    print("\n[3/5] CLIP (CPU)...")
    clip_service = CLIPService(model_name="openai/clip-vit-base-patch32")
    
    print("\n[4/5] Qwen2-VL-2B (GPU)...")
    qwen2b_service = Qwen2VLService(model_name="Qwen/Qwen2-VL-2B-Instruct")
    
    # print("\n[5/5] Qwen2-VL-7B (GPU)...")
    # qwen7b_service = Qwen2VLService(model_name="Qwen/Qwen2-VL-7B-Instruct")
    
    print("\n" + "=" * 70)
    print("✓ MODELS LOADED (4-Step Pipeline: Quality→OCR→CLIP→Qwen2B)")
    print("Note: Qwen7B disabled to reduce memory usage")
    print("=" * 70)


@app.get("/")
async def root():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "pipeline": "Quality → OCR → CLIP → Qwen2B (7B disabled)",
        "thresholds": {"clip": 0.70, "qwen2b": 0.85}
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "3.0.0",
        "pipeline": "Quality → OCR → CLIP → Qwen2B (7B disabled)",
        "models": {
            "Step 1: Quality": "✓ Loaded",
            "Step 2: OCR": "✓ Loaded",
            "Step 3: CLIP": "✓ Loaded",
            "Step 4: Qwen2B": "✓ Loaded"
        }
    }


@app.post("/analyze")
async def smart_analysis(file: UploadFile = File(...)):
    """
    SMART 4-STEP PIPELINE:
    1. Quality Check → STOP if fails
    2. OCR → Check text availability
    3. CLIP → Detect promotional content & category
    4. Qwen2B → Final moderation decision
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        log = []
        print(f"\n{'='*70}\nPROCESSING: {file.filename}\n{'='*70}")
        
        # STEP 1: Quality
        print("\n[1/4] Quality Check...")
        quality = quality_service.check_image(image, len(contents))
        log.append({"step": 1, "service": "Quality", "passed": quality["passed"], "checks": quality["checks"]})
        
        if not quality["passed"]:
            print(f"✗ STOPPED: Quality check failed - {quality['reason']}")
            return JSONResponse(content={
                "success": True,
                "filename": file.filename,
                "final_decision": "REJECT",
                "reason": f"Quality check failed: {quality['reason']}",
                "stopped_at": 1,
                "quality_check": quality,
                "log": log
            })
        print("✓ Quality: Passed")
        
        # STEP 2: OCR
        print("\n[2/4] OCR - Text Detection...")
        ocr = ocr_service.extract_text(image)
        text_available = ocr["text_found"]
        text_count = ocr.get("text_count", 0)
        
        log.append({
            "step": 2, 
            "service": "OCR", 
            "text_available": text_available,
            "text_count": text_count
        })
        
        if text_available:
            print(f"✓ OCR: Text available ({text_count} regions)")
        else:
            print("✓ OCR: No text available")
        
        # STEP 3: CLIP - Category & Promotional Detection
        print("\n[3/4] CLIP - Category & Promotional Detection...")
        clip_full = clip_service.analyze_image(image)
        
        # Get category
        category = clip_full.get("category_analysis", {})
        top_category = category.get("top_category", "Unknown")
        
        # Check promotional content
        promo = clip_full.get("promo_analysis", {})
        has_promotional = promo.get("is_promotional", False)
        
        # Risk analysis
        risk = clip_full["risk_analysis"]
        
        log.append({
            "step": 3, 
            "service": "CLIP",
            "category": top_category,
            "has_promotional": has_promotional,
            "risk_score": risk["max_risk"],
            "risk_category": risk["max_risk_category"]
        })
        
        print(f"✓ CLIP: Category: {top_category}")
        print(f"✓ CLIP: Promotional: {'Yes' if has_promotional else 'No'}")
        print(f"✓ CLIP: Risk: {risk['max_risk']:.2f} ({risk['max_risk_category']})")
        
        # STEP 4: Qwen2B - Final Decision
        print("\n[4/4] Qwen2-VL-2B - Final Moderation...")
        ctx2b = {"ocr_analysis": ocr, "clip_analysis": clip_full}
        qwen2b = qwen2b_service.moderate_image(image, ctx2b)
        
        decision = qwen2b.get("decision", "UNKNOWN")
        confidence = qwen2b.get("confidence", 0)
        
        log.append({
            "step": 4, 
            "service": "Qwen2B", 
            "decision": decision,
            "confidence": confidence
        })
        
        print(f"✓ FINAL DECISION: {decision} (Confidence: {confidence}%)")
        
        # Return only Qwen2B result
        return JSONResponse(content=qwen2b)
        
        # # STEP 5: Qwen7B (DISABLED - Model not loaded)
        # print("\n[5/5] Qwen2-VL-7B...")
        # ctx7b = {**ctx2b, "qwen2b_decision": qwen2b}
        # qwen7b = qwen7b_service.moderate_image(image, ctx7b)
        # log.append({"step": 5, "service": "Qwen7B", "decision": qwen7b.get("decision")})
        # print(f"✓ FINAL: {qwen7b.get('decision')}")
        # 
        # return JSONResponse(content={
        #     "success": True,
        #     "filename": file.filename,
        #     "final_decision": qwen7b.get("decision"),
        #     "reason": qwen7b.get("explanation"),
        #     "confidence": qwen7b.get("confidence"),
        #     "stopped_at": 5,
        #     "escalation": "Full pipeline",
        #     "log": log
        # })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/ai_check_detectction")
async def check_image_from_url(request: ImageURLRequest):
    """
    POST endpoint - Send image URL in JSON body: {"image_url": "https://..."}
    Returns AI moderation result
    """
    try:
        img_url = request.image_url
        
        # Download image from URL
        print(f"\n{'='*70}\nDOWNLOADING: {img_url}\n{'='*70}")
        response = requests.get(img_url, timeout=10)
        if response.status_code != 200:
            raise HTTPException(status_code=400, detail=f"Failed to download image: {response.status_code}")
        
        contents = response.content
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        print(f"\n{'='*70}\nPROCESSING IMAGE\n{'='*70}")
        
        # STEP 1: OpenCV Quality Check
        print("\n[1/3] Quality Check...")
        quality = quality_service.check_image(image, len(contents))
        
        checks = quality.get("checks", {})
        opencv_result = {
            "blur_detection": "no" if checks.get("blur", False) else "yes",
            "screenshot_check": "yes" if not checks.get("screenshot", True) else "no",
            "corruption_check": "no" if checks.get("corruption", False) else "yes",
            "watermark_check": "no" if checks.get("watermark", False) else "yes"
        }
        
        if not quality["passed"]:
            print(f"✗ Quality check failed - {quality['reason']}")
            return JSONResponse(content={
                "opencv": opencv_result,
                "ocr": {"image_extract": ""},
                "clip": {
                    "promo_text": "unknown",
                    "stock_photo": "unknown",
                    "illegal_photo": "unknown",
                    "category": "Quality Check Failed"
                },
                "risk_level": 0,
                "qwen2b_called": False
            })
        print("✓ Quality: Passed")
        
        # STEP 2: OCR - Text Detection
        print("\n[2/3] OCR - Text Detection...")
        ocr = ocr_service.extract_text(image)
        text_available = ocr["text_found"]
        extracted_text = ocr.get("full_text", "")
        
        ocr_result = {
            "image_extract": extracted_text if extracted_text else "No text found"
        }
        
        if text_available:
            print(f"✓ OCR: Text extracted")
        else:
            print("✓ OCR: No text available")
        
        # STEP 3: CLIP - Category & Risk Detection
        print("\n[3/3] CLIP - Category & Risk Detection...")
        clip_full = clip_service.analyze_image(image)
        
        # Get category
        category = clip_full.get("category_analysis", {})
        top_category = category.get("top_category", "Unknown")
        
        # Check promotional content
        promo = clip_full.get("promo_analysis", {})
        has_promotional = promo.get("is_promotional", False)
        
        # Risk analysis
        risk = clip_full["risk_analysis"]
        max_risk = risk["max_risk"]
        risk_category = risk["max_risk_category"]
        risk_level_percent = int(max_risk * 100)
        
        # Determine illegal photo status
        is_illegal = "no"
        if "weapon" in risk_category.lower() or "violent" in risk_category.lower():
            is_illegal = "yes"
        elif "medical" in risk_category.lower() and max_risk > 0.60:
            is_illegal = "suspected"
        
        # Determine stock photo status (generic product images)
        is_stock_photo = "no"
        if not has_promotional and max_risk < 0.20:
            is_stock_photo = "yes"
        
        clip_result = {
            "promo_text": "yes" if has_promotional else "no",
            "stock_photo": is_stock_photo,
            "illegal_photo": is_illegal,
            "category": top_category
        }
        
        print(f"✓ CLIP: Category: {top_category}")
        print(f"✓ CLIP: Promotional: {'Yes' if has_promotional else 'No'}")
        print(f"✓ CLIP: Risk Level: {risk_level_percent}%")
        
        # Check if Qwen2B is needed (risk level >= 85)
        qwen2b_result = None
        qwen2b_called = False
        
        if risk_level_percent >= 85:
            print(f"\n[4/4] ⚠ Risk Level {risk_level_percent}% - Calling Qwen2-VL-2B...")
            ctx2b = {"ocr_analysis": ocr, "clip_analysis": clip_full}
            qwen2b_result = qwen2b_service.moderate_image(image, ctx2b)
            qwen2b_called = True
            
            decision = qwen2b_result.get("decision", "UNKNOWN")
            confidence = qwen2b_result.get("confidence", 0)
            
            print(f"✓ QWEN2B DECISION: {decision} (Confidence: {confidence}%)")
        else:
            print(f"✓ Risk Level {risk_level_percent}% - No Qwen2B needed")
        
        # Build final response
        final_response = {
            "opencv": opencv_result,
            "ocr": ocr_result,
            "clip": clip_result,
            "risk_level": risk_level_percent,
            "qwen2b_called": qwen2b_called
        }
        
        # Add Qwen2B result if called
        if qwen2b_called and qwen2b_result:
            final_response["qwen2b"] = {
                "decision": qwen2b_result.get("decision", "UNKNOWN"),
                "confidence": qwen2b_result.get("confidence", 0),
                "explanation": qwen2b_result.get("explanation", ""),
                "violations": qwen2b_result.get("violations", []),
                "recommended_action": qwen2b_result.get("recommended_action", "")
            }
        
        return JSONResponse(content=final_response)
    
    except requests.exceptions.RequestException as e:
        raise HTTPException(status_code=400, detail=f"Failed to download image: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/dispute")
async def dispute(file: UploadFile = File(...), decision: str = Form(...), reason: str = Form(...)):
    """Dispute resolution using Qwen2B (7B not loaded)"""
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        ocr = ocr_service.extract_text(image)
        clip_full = clip_service.analyze_image(image)
        ctx = {"ocr_analysis": ocr, "clip_analysis": clip_full}
        
        result = qwen2b_service.resolve_dispute(image, decision, reason, ctx)
        
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "dispute_resolution": result,
            "model": "Qwen2B",
            "note": "Using Qwen2B (7B not loaded)"
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
