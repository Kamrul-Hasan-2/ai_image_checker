# AI Image Checker - RunPod Serverless Deployment

## Overview
This handler.py implements a 4-step AI pipeline for image verification on RunPod Serverless:
1. Quality Check (OpenCV)
2. OCR Check (EasyOCR)
3. CLIP Check (Vision-Language)
4. Qwen2-VL Check (Advanced Vision LLM)

## Build & Deploy

### 1. Build Docker Image
```bash
docker build -f Dockerfile.serverless -t kamrulhasan00/ai_image_checker_bdstall:latest .
```

### 2. Push to Docker Hub
```bash
docker push kamrulhasan00/ai_image_checker_bdstall:latest
```

### 3. Deploy on RunPod
1. Go to RunPod Serverless
2. Create new endpoint
3. Use Docker image: `kamrulhasan00/ai_image_checker_bdstall:latest`
4. Set GPU type (recommended: RTX 4090 or A100)
5. Configure:
   - Container Disk: 20GB minimum
   - Volume Size: 50GB (for model cache)

## API Usage

### Input Format
```python
{
    "input": {
        "image": "https://example.com/image.jpg",  # URL or base64
        "category": "smartphone",                   # Product category
        "pipeline": "full"                          # full, fast, or quality_only
    }
}
```

### Pipeline Modes
- **full**: Run all 4 steps (Quality → OCR → CLIP → Qwen2-VL)
- **fast**: Stop after CLIP check
- **quality_only**: Only check image quality

### Example Request
```python
import requests

endpoint_url = "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/run"
api_key = "YOUR_API_KEY"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

data = {
    "input": {
        "image": "https://example.com/product.jpg",
        "category": "laptop",
        "pipeline": "full"
    }
}

response = requests.post(endpoint_url, headers=headers, json=data)
print(response.json())
```

### Output Format
```json
{
    "category": "laptop",
    "pipeline_mode": "full",
    "steps": [
        {
            "step": "quality_check",
            "passed": true,
            "confidence": 0.95,
            "details": {...}
        },
        {
            "step": "ocr_check",
            "passed": false,
            "confidence": 0.3,
            "detected_text": ["some text"]
        },
        {
            "step": "clip_check",
            "passed": true,
            "confidence": 0.87,
            "details": {...}
        }
    ],
    "final_decision": true,
    "final_confidence": 0.87,
    "matched_at": "clip"
}
```

## Features
- ✅ Smart escalation pipeline
- ✅ Cold start optimization
- ✅ GPU acceleration for Qwen2-VL
- ✅ Supports URL and base64 images
- ✅ Detailed step-by-step results
- ✅ Flexible pipeline modes

## Environment Variables
- `TRANSFORMERS_CACHE`: Model cache directory
- `TORCH_HOME`: PyTorch cache directory

## Performance
- Cold start: ~30-60 seconds (first request)
- Warm inference: ~2-5 seconds per image
- GPU recommended: RTX 4090 or A100
