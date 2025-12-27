"""
FastAPI Server for AI Image Checker
3-Step Pipeline: EasyOCR → CLIP → Qwen2-VL
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
import io
from typing import Optional, List
import uvicorn

from clip_service import CLIPService
from qwen_service import Qwen2VLService
from ocr_service import OCRService


# Initialize FastAPI app
app = FastAPI(
    title="AI Image Checker",
    description="3-Step Pipeline: EasyOCR → CLIP → Qwen2-VL",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global model instances (loaded on startup)
ocr_service: Optional[OCRService] = None
clip_service: Optional[CLIPService] = None
qwen_service: Optional[Qwen2VLService] = None


@app.on_event("startup")
async def startup_event():
    """Load all models in sequence"""
    global ocr_service, clip_service, qwen_service
    
    print("=" * 60)
    print("Starting AI Image Checker Server")
    print("=" * 60)
    
    # Step 1: Load EasyOCR model
    print("\n[Step 1/3] Loading EasyOCR...")
    ocr_service = OCRService(languages=['en'])
    
    # Step 2: Load CLIP model
    print("\n[Step 2/3] Loading CLIP model...")
    clip_service = CLIPService(model_name="openai/clip-vit-base-patch32")
    
    # Step 3: Load Qwen2-VL model
    print("\n[Step 3/3] Loading Qwen2-VL model...")
    qwen_service = Qwen2VLService(model_name="Qwen/Qwen2-VL-2B-Instruct")
    
    print("\n" + "=" * 60)
    print("✓ All models loaded successfully!")
    print("Pipeline: EasyOCR → CLIP → Qwen2-VL")
    print("Server ready to accept requests")
    print("=" * 60)


@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "AI Image Checker",
        "version": "2.0.0",
        "pipeline": "EasyOCR → CLIP → Qwen2-VL",
        "models": {
            "step1_ocr": "loaded" if ocr_service else "not loaded",
            "step2_clip": "loaded" if clip_service else "not loaded",
            "step3_qwen2vl": "loaded" if qwen_service else "not loaded"
        }
    }


@app.post("/analyze/pipeline")
async def full_pipeline_analysis(file: UploadFile = File(...)):
    """
    COMPLETE 3-STEP PIPELINE:
    ✓ Step 1: EasyOCR - Extract text from image
    ✓ Step 2: CLIP - Fast category, risk scoring, brand/logo similarity, promo detection
    ✓ Step 3: Qwen2-VL - Final moderation decision with explanations
    """
    try:
        # Read and process image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        print(f"\n{'='*60}")
        print(f"Processing: {file.filename}")
        print(f"{'='*60}")
        
        # ===== STEP 1: EasyOCR - Text Extraction =====
        print("\n[Step 1/3] Running EasyOCR text extraction...")
        ocr_result = ocr_service.extract_text(image)
        print(f"✓ Text regions found: {ocr_result['text_count']}")
        if ocr_result['full_text']:
            print(f"✓ Sample text: {ocr_result['full_text'][:80]}...")
        print(f"✓ Has promotional text: {ocr_result['analysis']['has_promotional_text']}")
        print(f"✓ Has brand indicators: {ocr_result['analysis']['has_brand_indicators']}")
        
        # ===== STEP 2: CLIP - Fast Analysis =====
        print("\n[Step 2/3] Running CLIP analysis...")
        clip_result = clip_service.analyze_image(image)
        print(f"✓ Category: {clip_result['category_analysis']['top_category']}")
        print(f"✓ Risk level: {clip_result['risk_analysis']['risk_level']}")
        print(f"✓ Promo detected: {clip_result['promo_analysis']['is_promotional']}")
        print(f"✓ Safe content score: {clip_result['risk_analysis']['safe_content_score']:.2f}")
        
        # ===== STEP 3: Qwen2-VL - Final Decision =====
        print("\n[Step 3/3] Running Qwen2-VL final moderation...")
        # Combine OCR and CLIP results for context
        combined_context = {
            "ocr_analysis": ocr_result,
            "clip_analysis": clip_result
        }
        moderation_result = qwen_service.moderate_image(image, combined_context)
        print(f"✓ Final decision: {moderation_result.get('decision', 'UNKNOWN')}")
        print(f"✓ Confidence: {moderation_result.get('confidence', 0)}%")
        print(f"{'='*60}\n")
        
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "pipeline_results": {
                "step1_ocr": {
                    "text_found": ocr_result['text_found'],
                    "text_count": ocr_result['text_count'],
                    "full_text": ocr_result['full_text'],
                    "analysis": ocr_result['analysis']
                },
                "step2_clip": {
                    "category": clip_result['category_analysis'],
                    "risk": clip_result['risk_analysis'],
                    "promo": clip_result['promo_analysis']
                },
                "step3_qwen2vl": moderation_result
            },
            "final_summary": {
                "text_extracted": ocr_result['full_text'][:200] if ocr_result['full_text'] else "No text found",
                "has_promotional_content": ocr_result['analysis']['has_promotional_text'] or clip_result['promo_analysis']['is_promotional'],
                "category": clip_result['category_analysis']['top_category'],
                "risk_level": clip_result['risk_analysis']['risk_level'],
                "final_decision": moderation_result.get('decision', 'UNKNOWN'),
                "decision_confidence": moderation_result.get('confidence', 0),
                "explanation": moderation_result.get('explanation', '')
            }
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/step1/ocr")
async def step1_ocr_only(file: UploadFile = File(...)):
    """
    Step 1 Only: EasyOCR text extraction
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        ocr_result = ocr_service.extract_text(image)
        
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "step": 1,
            "service": "EasyOCR",
            "result": ocr_result
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/step2/clip")
async def step2_clip_only(file: UploadFile = File(...)):
    """
    Step 2 Only: CLIP analysis
    - Fast category scoring
    - Risk assessment  
    - Brand/logo similarity
    - Promo banner detection
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        clip_result = clip_service.analyze_image(image)
        
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "step": 2,
            "service": "CLIP",
            "result": clip_result
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/step3/qwen")
async def step3_qwen_only(file: UploadFile = File(...)):
    """
    Step 3 Only: Qwen2-VL moderation
    - Final moderation decision
    - Detailed explanations
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        moderation_result = qwen_service.moderate_image(image)
        
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "step": 3,
            "service": "Qwen2-VL",
            "result": moderation_result
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compare/similarity")
async def compare_similarity(
    file1: UploadFile = File(...),
    file2: UploadFile = File(...)
):
    """
    Compare two images for brand/logo similarity using CLIP
    """
    try:
        contents1 = await file1.read()
        contents2 = await file2.read()
        
        image1 = Image.open(io.BytesIO(contents1)).convert("RGB")
        image2 = Image.open(io.BytesIO(contents2)).convert("RGB")
        
        result = clip_service.compare_brand_similarity(image1, image2)
        
        return JSONResponse(content={
            "success": True,
            "file1": file1.filename,
            "file2": file2.filename,
            "similarity": result
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/compare/text")
async def compare_with_text(
    file: UploadFile = File(...),
    descriptions: str = Form(...)
):
    """
    Compare image with text descriptions using CLIP (for brand matching)
    descriptions: comma-separated text descriptions
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # Split descriptions
        text_list = [desc.strip() for desc in descriptions.split(",")]
        
        result = clip_service.compare_with_text(image, text_list)
        
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "text_matching": result
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/dispute")
async def resolve_dispute(
    file: UploadFile = File(...),
    initial_decision: str = Form(...),
    dispute_reason: str = Form(...)
):
    """
    Dispute resolution using complete pipeline
    initial_decision: APPROVE or REJECT
    dispute_reason: User's reason for disputing
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        # Run OCR and CLIP for context
        ocr_result = ocr_service.extract_text(image)
        clip_result = clip_service.analyze_image(image)
        
        combined_context = {
            "ocr_analysis": ocr_result,
            "clip_analysis": clip_result
        }
        
        # Resolve dispute with Qwen2-VL
        result = qwen_service.resolve_dispute(
            image,
            initial_decision,
            dispute_reason,
            combined_context
        )
        
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "dispute_resolution": result
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/explain")
async def explain_image(
    file: UploadFile = File(...),
    question: str = Form(...)
):
    """
    Get detailed explanation using Qwen2-VL
    """
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents)).convert("RGB")
        
        result = qwen_service.explain_decision(image, question)
        
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "explanation": result
        })
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=False  # Set to True for development
    )
