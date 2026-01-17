"""
FastAPI Server for AI Image Checker - MINIMAL VERSION
No AI models - Just basic API endpoints for testing
"""

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from PIL import Image
import io
from typing import Optional
import uvicorn

app = FastAPI(
    title="AI Image Checker - Minimal API",
    description="Lightweight API without AI models (for testing)",
    version="3.0.0-minimal"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ImageURLRequest(BaseModel):
    image_url: str
    category: Optional[str] = None

@app.on_event("startup")
async def startup_event():
    print("=" * 70)
    print("AI IMAGE CHECKER - MINIMAL VERSION (NO AI MODELS)")
    print("=" * 70)
    print("✓ Basic API endpoints ready")
    print("✓ For full AI features, use a server with more disk space")
    print("=" * 70)

@app.get("/")
async def root():
    """Root endpoint - API Information"""
    return {
        "service": "AI Image Checker API (Minimal)",
        "status": "running",
        "version": "3.0.0-minimal",
        "note": "Running without AI models due to disk space constraints",
        "endpoints": {
            "docs": "/docs",
            "health": "/health",
            "check_image": "POST /check_image (mock response)",
            "check_image_url": "POST /check_image_url (mock response)"
        },
        "message": "Visit /docs for interactive API documentation"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "version": "3.0.0-minimal",
        "mode": "minimal (no AI models)",
        "models": {
            "Quality Check": "⚠️ Disabled",
            "OCR": "⚠️ Disabled",
            "CLIP": "⚠️ Disabled",
            "Qwen2B": "⚠️ Disabled"
        },
        "message": "API is running but AI models are not loaded. Use for testing only."
    }

@app.post("/check_image")
async def check_image(
    file: UploadFile = File(...),
    category: Optional[str] = Form(None)
):
    """Mock endpoint - returns sample response without processing"""
    try:
        # Just verify it's an image
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        width, height = image.size
        
        return JSONResponse(content={
            "success": True,
            "filename": file.filename,
            "mode": "minimal_mock",
            "image_info": {
                "width": width,
                "height": height,
                "format": image.format
            },
            "mock_result": {
                "decision": "APPROVE",
                "confidence": 0.95,
                "category": category or "unknown",
                "note": "This is a mock response. AI models not loaded due to disk space."
            },
            "message": "⚠️ Running in minimal mode. For real AI analysis, use a server with more space."
        })
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/check_image_url")
async def check_image_url(request: ImageURLRequest):
    """Mock endpoint - returns sample response"""
    return {
        "success": True,
        "image_url": request.image_url,
        "mode": "minimal_mock",
        "mock_result": {
            "decision": "APPROVE",
            "confidence": 0.92,
            "category": request.category or "unknown",
            "note": "This is a mock response. AI models not loaded due to disk space."
        },
        "message": "⚠️ Running in minimal mode. For real AI analysis, use a server with more space."
    }

@app.post("/quality")
async def quality_check(file: UploadFile = File(...)):
    """Basic image info without AI"""
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        width, height = image.size
        
        return {
            "success": True,
            "filename": file.filename,
            "dimensions": f"{width}x{height}",
            "format": image.format,
            "mode": image.mode,
            "note": "Basic image info only. Quality AI not loaded."
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    print("\n🚀 Starting Minimal API Server...")
    print("📍 Access at: http://0.0.0.0:8000")
    print("📚 Docs at: http://0.0.0.0:8000/docs\n")
    uvicorn.run("main_minimal:app", host="0.0.0.0", port=8000, reload=False)
