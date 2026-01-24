# AI Image Checker - Modal Deployment

Clean and optimized Modal.com deployment for AI-powered image moderation.

## Quick Start

### 1. Install Modal
```bash
pip install modal
```

### 2. Authenticate with Modal
```bash
modal setup
```

### 3. Deploy to Modal
```bash
modal deploy modal_handler.py
```

This will:
- Build the container image with all dependencies
- Pre-download AI models (CLIP, Qwen2-VL, EasyOCR)
- Deploy your serverless endpoint
- Provide you with the endpoint URL

### 4. Test Your Deployment
Update the endpoint URL in `test_modal.py` and run:
```bash
python test_modal.py
```

## Features

- ✅ **GPU-accelerated** inference with A10G GPUs
- ✅ **Auto-scaling** from 0 to handle traffic
- ✅ **GPU snapshots** for fast cold starts (~5 seconds)
- ✅ **Multi-image batch** processing support
- ✅ **Hybrid AI pipeline**: OpenCV → OCR → Qwen2-VL

## API Usage

### Single Image
```python
import requests

response = requests.post(
    "YOUR_MODAL_ENDPOINT_URL",
    json={
        "image": "https://example.com/image.jpg",
        "category": "electronics"
    }
)
print(response.json())
```

### Multiple Images
```python
response = requests.post(
    "YOUR_MODAL_ENDPOINT_URL",
    json={
        "images": [
            {"image": "https://example.com/image1.jpg", "category": "electronics"},
            {"image": "https://example.com/image2.jpg", "category": "clothing"}
        ]
    }
)
print(response.json())
```

## Response Format

```json
{
  "blur_image": 0,
  "screen_short": 0,
  "category_mismatch": 0,
  "illegal": 0,
  "promotional_text": 0,
  "stock_photo": 0,
  "watermark": 0,
  "risk_level": 15
}
```

## Cost Optimization

- **Scales to zero** when not in use (no idle costs)
- **GPU snapshots** reduce cold start time and costs
- **Efficient model caching** in container image
- **Only charges for actual inference time**

## Monitoring

View logs and metrics:
```bash
modal logs ai-image-checker
```

Visit dashboard: https://modal.com/apps

## Support

For issues or questions, check the Modal documentation at https://modal.com/docs
