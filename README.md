# AI Image Checker

A FastAPI-based image analysis service using **CLIP** and **Qwen2-VL** models for comprehensive image moderation, categorization, and analysis.

## Features

### CLIP Model (openai/clip-vit-base-patch32)
- ✅ **Fast category scoring** - Classify images into 10 categories
- ✅ **Risk assessment** - Detect potentially inappropriate content
- ✅ **Brand/logo similarity** - Compare images for visual similarity
- ✅ **Promo banner detection** - Identify promotional content

### Qwen2-VL Model (Qwen/Qwen2-VL-7B-Instruct)
- ✅ **Final moderation decision** - Comprehensive APPROVE/REJECT decisions
- ✅ **Detailed explanations** - Understand why decisions were made
- ✅ **Dispute resolution** - Review and overturn previous decisions

## Installation

1. **Clone or navigate to the project directory**
```bash
cd c:\Users\BLG\Desktop\ai_image_checker
```

2. **Create a virtual environment (recommended)**
```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

## Running the Server

```bash
python main.py
```

Or use uvicorn directly:
```bash
uvicorn main:app --host 0.0.0.0 --port 8000
```

The server will load both models on startup. This may take a few minutes. Once ready, the API will be available at `http://localhost:8000`

## API Documentation

Once running, visit:
- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## API Endpoints

### 1. Health Check
```bash
GET /
```

### 2. Quick Analysis (CLIP only)
Fast analysis for category, risk, and promo detection.

```bash
curl -X POST "http://localhost:8000/analyze/quick" \
  -F "file=@your_image.jpg"
```

**Response:**
```json
{
  "success": true,
  "filename": "your_image.jpg",
  "analysis": {
    "category_analysis": {
      "top_category": "product photo",
      "confidence": 0.85
    },
    "risk_analysis": {
      "risk_level": "low",
      "safe_content_score": 0.92
    },
    "promo_analysis": {
      "is_promotional": false,
      "confidence": 0.12
    }
  }
}
```

### 3. Full Analysis (CLIP + Qwen2-VL)
Comprehensive analysis with moderation decision.

```bash
curl -X POST "http://localhost:8000/analyze/full" \
  -F "file=@your_image.jpg"
```

**Response:**
```json
{
  "success": true,
  "filename": "your_image.jpg",
  "clip_analysis": { ... },
  "moderation": {
    "decision": "APPROVE",
    "confidence": 95,
    "explanation": "Image shows a safe product photo...",
    "violations": [],
    "recommended_action": "approve"
  },
  "final_decision": "APPROVE"
}
```

### 4. Moderation Only (Qwen2-VL)
Get detailed moderation decision.

```bash
curl -X POST "http://localhost:8000/moderate" \
  -F "file=@your_image.jpg"
```

### 5. Brand/Logo Similarity
Compare two images for visual similarity.

```bash
curl -X POST "http://localhost:8000/compare/similarity" \
  -F "file1=@logo1.jpg" \
  -F "file2=@logo2.jpg"
```

**Response:**
```json
{
  "success": true,
  "file1": "logo1.jpg",
  "file2": "logo2.jpg",
  "similarity": {
    "similarity_score": 0.92,
    "is_similar": true,
    "confidence": 0.92
  }
}
```

### 6. Text Matching
Compare image against text descriptions.

```bash
curl -X POST "http://localhost:8000/compare/text" \
  -F "file=@brand_logo.jpg" \
  -F "descriptions=Nike logo,Adidas logo,Puma logo,Reebok logo"
```

### 7. Explain Image
Get detailed explanation about the image.

```bash
curl -X POST "http://localhost:8000/explain" \
  -F "file=@your_image.jpg" \
  -F "question=Why might this image be flagged?"
```

### 8. Dispute Resolution
Review and resolve disputed decisions.

```bash
curl -X POST "http://localhost:8000/dispute" \
  -F "file=@disputed_image.jpg" \
  -F "initial_decision=REJECT" \
  -F "dispute_reason=This is a legitimate product photo"
```

**Response:**
```json
{
  "success": true,
  "filename": "disputed_image.jpg",
  "dispute_resolution": {
    "dispute_resolution": "OVERTURN",
    "final_decision": "APPROVE",
    "confidence": 88,
    "reasoning": "Upon review, the image is indeed...",
    "additional_recommendations": "Approve with monitoring"
  }
}
```

### 9. Specific Checks

**Promo Banner Detection:**
```bash
curl -X POST "http://localhost:8000/check/promo" \
  -F "file=@banner.jpg"
```

**Risk Assessment:**
```bash
curl -X POST "http://localhost:8000/check/risk" \
  -F "file=@content.jpg"
```

**Category Detection:**
```bash
curl -X POST "http://localhost:8000/check/category" \
  -F "file=@photo.jpg"
```

**Image Description:**
```bash
curl -X POST "http://localhost:8000/describe" \
  -F "file=@photo.jpg"
```

## Python Client Example

```python
import requests

# Quick analysis
with open('image.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/analyze/quick',
        files={'file': f}
    )
    print(response.json())

# Full analysis
with open('image.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/analyze/full',
        files={'file': f}
    )
    result = response.json()
    print(f"Decision: {result['final_decision']}")
    print(f"Explanation: {result['moderation']['explanation']}")

# Compare similarity
with open('logo1.jpg', 'rb') as f1, open('logo2.jpg', 'rb') as f2:
    response = requests.post(
        'http://localhost:8000/compare/similarity',
        files={'file1': f1, 'file2': f2}
    )
    similarity = response.json()['similarity']['similarity_score']
    print(f"Similarity: {similarity:.2%}")
```

## Architecture

```
┌─────────────┐
│   Client    │
└──────┬──────┘
       │
       ▼
┌─────────────────────────┐
│   FastAPI Server        │
│   (main.py)            │
└────────┬────────────────┘
         │
    ┌────┴────┐
    │         │
    ▼         ▼
┌─────────┐ ┌──────────────┐
│  CLIP   │ │  Qwen2-VL    │
│ Service │ │   Service    │
└─────────┘ └──────────────┘
```

### Workflow
1. **Server Startup**: Both models load into memory
2. **Request**: Client sends image to endpoint
3. **CLIP Analysis** (fast): Category, risk, promo detection
4. **Qwen2-VL Analysis** (detailed): Moderation decision with explanation
5. **Response**: Combined results returned to client

## System Requirements

- **RAM**: 16GB minimum (32GB recommended for Qwen2-VL-7B)
- **GPU**: NVIDIA GPU with 8GB+ VRAM recommended (works on CPU but slower)
- **Storage**: ~15GB for model weights
- **Python**: 3.8 or higher

## Performance Notes

- **CLIP inference**: ~50-100ms per image (GPU)
- **Qwen2-VL inference**: ~1-3 seconds per image (GPU)
- **Quick analysis** (`/analyze/quick`): Uses CLIP only for speed
- **Full analysis** (`/analyze/full`): Uses both models for comprehensive results

## Troubleshooting

### Out of Memory
If you encounter OOM errors:
1. Use CPU instead of GPU (slower but uses less memory)
2. Reduce batch size
3. Consider using smaller model variants

### Slow Loading
Model loading can take 2-5 minutes. This is normal and only happens once at startup.

### CUDA Errors
If you don't have a GPU or CUDA installed, the models will automatically fall back to CPU.

## License

This project uses:
- CLIP: MIT License (OpenAI)
- Qwen2-VL: Apache 2.0 License (Alibaba Cloud)

## Support

For issues or questions, check the API documentation at `/docs` when the server is running.
