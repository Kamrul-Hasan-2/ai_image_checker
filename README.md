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

## BDStall API (id-only)

Both moderation endpoints take just a listing id and fetch the listing themselves
from BDStall's `product_details` API — nothing has to be pushed in the request body.

### `POST /image_checker/`

```json
{ "id": 141462 }
```

The service fetches
`https://www.bdstall.com/api/item_ai/product_details/?key=123_456&id=141462`,
checks **only** images whose `ai_verified` is `0` or `1` (`2` means already checked),
and returns one entry per error actually found:

```json
{
  "results": [
    { "image_id": 458504, "position_id": 0, "error_id": 5 },
    { "image_id": 458504, "position_id": 0, "error_id": 4 }
  ]
}
```

Clean images, and images already at `ai_verified: 2`, don't appear at all.
`error_id` values are BDStall's own `error_list` ids:

| `error_id` | Check |
|---|---|
| 2 | Category mismatch |
| 3 | Promotional text |
| 4 | Watermark |
| 5 | Blur image |
| 6 | Background error |
| 8 | Screenshot |
| 9 | Illegal |
| 10 | Stock photo |

An image that couldn't be downloaded or processed is reported under a `skipped`
array (present only when non-empty) rather than being silently reported as clean:

```json
{ "results": [], "skipped": [{ "image_id": 458507, "position_id": 3, "reason": "..." }] }
```

An unknown listing returns HTTP 404; an unreachable `product_details` returns HTTP 502 —
never an empty "all clean" result.

The legacy payload (`{category, title, description, images: [...]}`) still works and
still returns one flag object per image, so callers can switch over on their own
schedule.

### `POST /weight_checker/`

Weight mismatch used to ride along on every `image_checker` result; it's now its own
endpoint.

```json
{ "id": 141462 }
```

```json
{ "weight_mismatch": false }
```

When the declared weight is implausible for the product, `error_id: 24`
("Weight differs from recorded product weight") is included alongside
`"weight_mismatch": true`.

> **Open gap:** `product_details` does not currently return a numeric
> `shipping_weight_kg`. Only a free-text `specification` entry like
> `"Package Weight: Approximately 0.70 kg"` exists, and only for categories that
> happen to have a Weight spec field — that text is deliberately **not** parsed,
> since it isn't guaranteed to be present, numeric, or in kg. Until BDStall adds a
> real `shipping_weight_kg` field, this endpoint fails open with
> `{"weight_mismatch": false, "reason": "no_declared_shipping_weight"}`.
> The comparison logic itself is implemented and runs as soon as the field appears.

### Configuration

| Env var | Default |
|---|---|
| `BDSTALL_PRODUCT_DETAILS_URL` | `https://www.bdstall.com/api/item_ai/product_details/` |
| `BDSTALL_API_KEY` | `123_456` |
| `BDSTALL_PRODUCT_DETAILS_TIMEOUT` | `15` (seconds) |
| `BDSTALL_PRODUCT_DETAILS_TTL_SECONDS` | `60` — response cache, so `image_checker` and `weight_checker` for the same listing only fetch once |

Every endpoint is also registered under the `/api/moderation_ai/` prefix
(`POST /api/moderation_ai/image_checker/`, `POST /api/moderation_ai/weight_checker/`).

---


## API Usage (legacy direct-image contract)

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
├── main.py                # FastAPI app (the ai.bdstall.com deployment)
├── bdstall_api.py         # product_details client (id-only contract)
├── modal_handler.py       # Modal deployment file
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
