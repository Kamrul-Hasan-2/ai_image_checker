# 🚀 Quick Start - Modal.com Deployment

## One-Command Setup

Run the automated deployment script:

```bash
python deploy_modal.py
```

This will:
1. ✅ Install Modal CLI
2. ✅ Authenticate with Modal (opens browser)
3. ✅ Deploy your application

## Or Manual Setup

```bash
# 1. Install Modal
pip install modal

# 2. Authenticate
python -m modal setup

# 3. Deploy
modal deploy modal_handler.py
```

## Get Your Endpoint URL

After deployment, you'll see:
```
✓ Created web function check_image_endpoint => https://YOUR_USERNAME--ai-image-checker-check-image-endpoint.modal.run
```

**Copy this URL!**

## Test Your Deployment

1. Update `test_modal.py` with your endpoint URL
2. Run tests:
```bash
python test_modal.py
```

## Make API Calls

### Python
```python
import requests

response = requests.post(
    "YOUR_ENDPOINT_URL",
    json={
        "image": "https://example.com/image.jpg",
        "category": "electronics",
        "pipeline": "full"
    }
)

print(response.json())
```

### cURL
```bash
curl -X POST YOUR_ENDPOINT_URL \
  -H "Content-Type: application/json" \
  -d '{"image": "https://example.com/image.jpg", "category": "electronics"}'
```

## Response Format

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

## View Logs

```bash
modal logs ai-image-checker
```

## Documentation

- 📖 [MODAL.md](MODAL.md) - Complete Modal deployment guide
- 🔄 [RUNPOD_VS_MODAL.md](RUNPOD_VS_MODAL.md) - Comparison with RunPod
- 📝 [README.md](README.md) - Original project documentation

## Files Structure

```
✅ New Files (Modal):
├── modal_handler.py          # Modal deployment code
├── deploy_modal.py            # Automated deployment script
├── test_modal.py              # Test script
├── MODAL.md                   # Modal documentation
├── RUNPOD_VS_MODAL.md         # Comparison guide
└── QUICKSTART_MODAL.md        # This file

📦 Unchanged (Your Services):
├── quality_service.py         # OpenCV quality checks
├── ocr_service.py            # EasyOCR text extraction
├── clip_service.py           # CLIP visual analysis
├── qwen_service.py           # Qwen2-VL reasoning
└── requirements.txt          # Dependencies

📚 Old Files (Reference):
├── handler.py                # RunPod version (keep for reference)
└── RUNPOD_REFRESH.md         # RunPod documentation
```

## Key Differences from RunPod

| Aspect | RunPod | Modal |
|--------|--------|-------|
| Setup | Docker + RunPod CLI | `pip install modal` |
| Deploy | `docker push` + UI config | `modal deploy` |
| API | Needs API key | Direct HTTP endpoint |
| Input | `{"input": {...}}` | `{...}` (direct) |

## Troubleshooting

### "modal: command not found"
```bash
pip install modal
```

### "Not authenticated"
```bash
python -m modal setup
```

### Import errors
Make sure all service files are in the same directory:
- `quality_service.py`
- `ocr_service.py`
- `clip_service.py`
- `qwen_service.py`

## Support

- Modal Docs: https://modal.com/docs
- Modal Discord: https://discord.gg/modal
- Modal Examples: https://modal.com/docs/examples

---

**Ready to deploy?** Run: `python deploy_modal.py` 🚀
