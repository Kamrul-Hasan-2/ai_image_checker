# RunPod vs Modal.com - Migration Guide

## Quick Comparison

| Feature | RunPod | Modal.com |
|---------|--------|-----------|
| **File** | `handler.py` | `modal_handler.py` |
| **Setup** | RunPod CLI | `pip install modal` + `modal setup` |
| **Deploy** | Docker build + push | `modal deploy modal_handler.py` |
| **API Style** | RunPod serverless handler | Modal web endpoint |
| **GPU Access** | Configured in pod | Decorator `gpu="A10G"` |
| **Cold Start** | ~30s | ~10-15s (with container reuse) |
| **Pricing** | Per-second GPU | Per-second compute + storage |

## Code Changes Overview

### RunPod Version (`handler.py`)
```python
import runpod

def run_pipeline(job):
    # Your code here
    return result

runpod.serverless.start({"handler": run_pipeline})
```

### Modal Version (`modal_handler.py`)
```python
import modal

app = modal.App("ai-image-checker")

@app.cls(gpu="A10G")
class ImageChecker:
    @modal.method()
    def check_image(self, job_input):
        # Your code here (same logic)
        return result

@app.web_endpoint(method="POST")
def check_image_endpoint(data):
    checker = ImageChecker()
    return checker.check_image.remote(data)
```

## What Stayed The Same ✅

1. **Core Logic**: All processing logic is identical
2. **Services**: Same `quality_service.py`, `ocr_service.py`, `clip_service.py`, `qwen_service.py`
3. **Input/Output Format**: Same JSON request and response
4. **Dependencies**: Same `requirements.txt` packages

## What Changed 🔄

### 1. Initialization

**RunPod:**
```python
def initialize_services():
    global quality_service, ocr_service, clip_service, qwen2b_service
    # Initialize...

# Called in run_pipeline
initialize_services()
```

**Modal:**
```python
@app.cls(gpu="A10G")
class ImageChecker:
    @modal.enter()
    def initialize_services(self):
        # Initialize services as instance variables
        self.quality_service = QualityCheckService()
        # ...
```

### 2. Entry Point

**RunPod:**
```python
def run_pipeline(job):
    job_input = job.get("input", {})
    # Process...
    return result

runpod.serverless.start({"handler": run_pipeline})
```

**Modal:**
```python
@app.method()
def check_image(self, job_input):
    # Process... (same logic)
    return result

@app.web_endpoint(method="POST")
def check_image_endpoint(data):
    checker = ImageChecker()
    return checker.check_image.remote(data)
```

### 3. Dependencies

**RunPod:**
```dockerfile
# Dockerfile with RunPod base image
FROM runpod/pytorch:2.1.0-py3.10-cuda11.8.0-devel-ubuntu22.04
```

**Modal:**
```python
# In code - Modal builds container automatically
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("transformers", "torch", ...)
)
```

## API Request Format (SAME)

Both use the same input format:

### Single Image
```json
{
  "image": "https://example.com/image.jpg",
  "category": "electronics",
  "pipeline": "full"
}
```

### Multiple Images
```json
{
  "images": [
    {"image": "url1", "category": "laptop"},
    {"image": "url2", "category": "phone"}
  ],
  "pipeline": "full"
}
```

## Response Format (SAME)

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

## Deployment Comparison

### RunPod Deployment
```bash
# Build Docker image
docker build -t my-image -f Dockerfile .

# Push to registry
docker push my-image

# Create endpoint in RunPod UI
# Configure GPU, scaling, etc.
```

### Modal Deployment
```bash
# One command!
modal deploy modal_handler.py

# Get endpoint URL immediately
# https://USERNAME--ai-image-checker-check-image-endpoint.modal.run
```

## Testing

### RunPod
```python
import requests

url = "https://api.runpod.ai/v2/YOUR_ENDPOINT_ID/runsync"
headers = {"Authorization": f"Bearer {RUNPOD_API_KEY}"}

response = requests.post(url, headers=headers, json={
    "input": {
        "image": "https://example.com/image.jpg",
        "category": "electronics"
    }
})
```

### Modal
```python
import requests

url = "https://USERNAME--ai-image-checker-check-image-endpoint.modal.run"

response = requests.post(url, json={
    "image": "https://example.com/image.jpg",
    "category": "electronics"
})
```

Notice: Modal is simpler - no API key header, no nested "input" field.

## Monitoring & Logs

### RunPod
- View logs in RunPod dashboard
- Metrics in RunPod UI
- Set up custom monitoring

### Modal
```bash
# View live logs
modal logs ai-image-checker

# Or visit dashboard
# https://modal.com/apps
```

## Cost Considerations

### RunPod
- Pay per GPU-second
- Minimum charge per invocation
- Cold start time counts
- Storage costs separate

### Modal
- Pay per compute-second
- Container reuse reduces costs
- Automatic scaling
- Includes storage in pricing

## Migration Checklist

- [x] ✅ Created `modal_handler.py` with Modal integration
- [x] ✅ Kept all service files unchanged
- [x] ✅ Maintained same input/output format
- [x] ✅ Created deployment script (`deploy_modal.py`)
- [x] ✅ Created test script (`test_modal.py`)
- [x] ✅ Created documentation (`MODAL.md`)
- [ ] 🚀 Install Modal: `pip install modal`
- [ ] 🚀 Authenticate: `python -m modal setup`
- [ ] 🚀 Deploy: `modal deploy modal_handler.py`
- [ ] 🚀 Test: Update and run `test_modal.py`

## Advantages of Modal

1. **Simpler Deployment**: One command vs Docker build/push
2. **Faster Cold Starts**: ~10-15s vs ~30s
3. **Better DX**: Python-native, no Dockerfiles
4. **Auto Scaling**: Built-in, no configuration
5. **Integrated Monitoring**: Built-in logs and metrics
6. **Model Caching**: Automatic model caching between runs
7. **Easy Rollbacks**: Version management built-in

## When to Use Each

### Use RunPod When:
- You need specific Docker customization
- You prefer UI-based configuration
- You're already using RunPod infrastructure

### Use Modal When:
- You want faster deployment
- You prefer code-based configuration
- You want better cold start performance
- You want integrated monitoring

## Need Help?

- **Modal Docs**: https://modal.com/docs
- **Modal Examples**: https://modal.com/docs/examples
- **Modal Discord**: https://discord.gg/modal
- **Your Code**: All logic in `modal_handler.py` is the same as `handler.py`!
