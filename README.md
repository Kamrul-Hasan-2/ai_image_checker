# AI Image Checker

AI-powered image moderation service using OpenCV, OCR, CLIP, and Qwen2-VL models.

## Features

🔍 **Multi-layer Detection System**
- Screenshot detection (OpenCV)
- Blur detection
- OCR text analysis for watermarks and promotional content
- **Product title matching** - prevents false positives on product images
- **Visual product detection** - identifies actual product photos
- AI-powered content moderation (Qwen2-VL)

🚀 **Production-Ready**
- GPU-accelerated inference
- Auto-scaling serverless deployment
- Fast cold starts with GPU snapshots
- Batch processing support

## Quick Deploy to Modal

```bash
# Install Modal
pip install modal

# Authenticate
modal setup

# Deploy (first time takes 5-10 minutes to download models)
modal deploy modal_handler.py
```

You'll get an endpoint URL like:
```
https://YOUR_USERNAME--ai-image-checker-check-image-endpoint.modal.run
```

## Test Your Deployment

Update `test_modal.py` with your endpoint URL and run:

```bash
python test_modal.py
```

## API Usage

```python
import requests

# Single image with product title (NEW!)
response = requests.post(
    "YOUR_ENDPOINT_URL",
    json={
        "image": "https://example.com/laptop.jpg",
        "category": "laptop",
        "title": "Dell Inspiron 15 3000"  # Optional: prevents false positives
    }
)

# Single image without title
response = requests.post(
    "YOUR_ENDPOINT_URL",
    json={
        "image": "https://example.com/image.jpg",
        "category": "electronics"
    }
)

# Multiple images with titles
response = requests.post(
    "YOUR_ENDPOINT_URL",
    json={
        "images": [
            {
                "image": "https://cdn.bdstall.com/product-image/419709.webp",
                "category": "laptop",
                "title": "Dell Inspiron 15"
            },
            {
                "image": "https://example.com/camera.jpg",
                "category": "camera",
                "title": "Imou 3K 5MP Cruiser SC"
            }
        ],
        "pipeline": "full"
    }
)

result = response.json()
print(f"Risk Level: {result['risk_level']}")
```

## Product Title Matching (NEW Feature)

**Problem:** Product images show the product name/specs on packaging, which shouldn't be flagged as promotional.

**Solution:** Provide the product title in your request. If the title matches the OCR text (≥60% word overlap), the system recognizes it as legitimate product text.

**Example:**
```json
{
  "image": "https://example.com/camera.jpg",
  "title": "Imou 3K 5MP Cruiser SC Security Camera"
}
```

If OCR finds "Imou 3K 5MP Cruiser SC Remote viewing" on the image, it matches 5/7 words (71%) and sets `promotional_text: 0`.

**Learn more:** [PRODUCT_TITLE_MATCHING.md](PRODUCT_TITLE_MATCHING.md)
```

## Response Format

```json
{
  "blur_image": 0,          // 0 or 5 (if blurry)
  "screen_short": 0,        // 0 or 8 (if screenshot)
  "category_mismatch": 0,   // 0 or 2
  "illegal": 0,             // 0 or 9 (if illegal content)
  "promotional_text": 0,    // 0 or 3 (if promotional)
  "stock_photo": 0,         // 0 or 10
  "watermark": 0,           // 0 or 4 (if watermark detected)
  "risk_level": 15          // Overall risk score (0-100)
}
```

## Project Structure

```
ai_image_checker/
├── modal_handler.py       # Main Modal deployment file
├── quality_service.py     # OpenCV quality checks
├── ocr_service.py         # Text extraction and analysis
├── clip_service.py        # CLIP model service
├── qwen_service.py        # Qwen2-VL moderation
├── test_modal.py          # Test script
├── setup_modal.py         # Setup wizard
└── README_MODAL.md        # Detailed Modal guide
```

## Cost & Performance

- **GPU**: Nvidia A10G
- **Cold Start**: ~5 seconds (with GPU snapshot)
- **Warm Inference**: ~2-3 seconds per image
- **Scaling**: Auto-scales to 0 when idle (no idle costs)
- **Pricing**: ~$1.10/hour when active (first $30/month free)

## Documentation

See [README_MODAL.md](README_MODAL.md) for complete Modal deployment guide.

## Monitoring

```bash
# View logs
modal logs ai-image-checker

# Visit dashboard
open https://modal.com/apps
```

## License

MIT
