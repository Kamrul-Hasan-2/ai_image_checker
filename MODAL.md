# Modal.com Deployment Guide

This guide explains how to deploy your AI Image Checker on Modal.com.

## What Changed from RunPod

- **Before (RunPod)**: `handler.py` with `runpod.serverless.start()`
- **After (Modal)**: `modal_handler.py` with `modal.App()` and decorators

The core logic remains the same - only the deployment platform changed!

## Setup Instructions

### 1. Install Modal CLI

```bash
pip install modal
```

### 2. Authenticate with Modal

```bash
python -m modal setup
```

This will open your browser to authenticate. Close the tab when done.

### 3. Test Locally

Test your function locally before deploying:

```bash
modal run modal_handler.py
```

### 4. Deploy to Modal

Deploy your app to Modal's cloud:

```bash
modal deploy modal_handler.py
```

After deployment, Modal will give you an endpoint URL like:
```
https://YOUR_USERNAME--ai-image-checker-check-image-endpoint.modal.run
```

**Save this URL!** You'll use it to make API calls.

## How to Use

### Single Image Request

```bash
curl -X POST https://YOUR_ENDPOINT_URL \
  -H "Content-Type: application/json" \
  -d '{
    "image": "https://example.com/image.jpg",
    "category": "electronics",
    "pipeline": "full"
  }'
```

### Multiple Images Request

```bash
curl -X POST https://YOUR_ENDPOINT_URL \
  -H "Content-Type: application/json" \
  -d '{
    "images": [
      {"image": "https://example.com/img1.jpg", "category": "laptop"},
      {"image": "https://example.com/img2.jpg", "category": "phone"}
    ],
    "pipeline": "full"
  }'
```

### Python Client Example

```python
import requests

endpoint = "YOUR_ENDPOINT_URL"

# Single image
response = requests.post(endpoint, json={
    "image": "https://example.com/image.jpg",
    "category": "electronics",
    "pipeline": "full"
})

print(response.json())
```

## Testing

Use the included test script:

```bash
# First, update MODAL_ENDPOINT in test_modal.py with your endpoint URL
python test_modal.py
```

## Response Format

Same as RunPod version:

```json
{
  "blur_image": 0,
  "screen_short": 0,
  "category_mismatch": 0,
  "illegal": 0,
  "promotional_text": 3,
  "stock_photo": 0,
  "watermark": 4,
  "risk_level": 45
}
```

## Configuration Options

### GPU Types

In `modal_handler.py`, you can change GPU:

```python
@app.cls(
    image=image,
    gpu="A10G",  # Options: "T4", "A10G", "A100"
    timeout=600,
)
```

### Timeout Settings

- `timeout`: Max execution time (seconds)
- `container_idle_timeout`: How long to keep container warm

### Pipeline Modes

- `full`: All steps (OpenCV → OCR → CLIP → Qwen)
- `fast`: Skip heavy models
- `quality_only`: Only OpenCV checks

## Monitoring

View logs and metrics:

```bash
modal logs ai-image-checker
```

Or visit Modal dashboard: https://modal.com/apps

## Cost Optimization

1. **Container Idle Timeout**: Set to 300s (5 min) to balance cost vs warmup time
2. **GPU Selection**: 
   - T4: Cheapest, good for light workloads
   - A10G: Balanced (recommended)
   - A100: Most expensive, fastest
3. **Batch Processing**: Process multiple images in one request

## File Structure

```
ai_image_checker/
├── modal_handler.py        # Modal deployment (NEW)
├── handler.py              # RunPod deployment (OLD - keep for reference)
├── quality_service.py      # OpenCV quality checks
├── ocr_service.py          # EasyOCR text extraction
├── clip_service.py         # CLIP visual analysis
├── qwen_service.py         # Qwen2-VL reasoning
├── test_modal.py           # Test script for Modal (NEW)
└── requirements.txt        # Python dependencies
```

## Troubleshooting

### Import Errors

If services can't be imported, make sure all files are in the same directory:
- `quality_service.py`
- `ocr_service.py`
- `clip_service.py`
- `qwen_service.py`

### GPU Memory Issues

If you run out of GPU memory:
1. Use smaller GPU (T4 instead of A10G)
2. Reduce image size in preprocessing
3. Use Qwen2-VL-2B instead of 7B (already done)

### Timeout Errors

Increase timeout in decorator:
```python
@app.cls(
    timeout=900,  # 15 minutes instead of 10
)
```

## Next Steps

1. ✅ Deploy with `modal deploy modal_handler.py`
2. ✅ Get your endpoint URL
3. ✅ Update `test_modal.py` with endpoint URL
4. ✅ Run tests with `python test_modal.py`
5. ✅ Integrate endpoint into your application

## Support

- Modal Docs: https://modal.com/docs
- Modal Discord: https://modal.com/discord
- Modal GitHub: https://github.com/modal-labs/modal-examples
