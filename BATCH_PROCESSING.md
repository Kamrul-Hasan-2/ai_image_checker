# Batch Processing - Multiple Images Support

## Overview
The AI Image Checker now supports processing multiple images in a single request using array format.

## Features
✅ **Single Image Mode** - Process one image at a time (backward compatible)  
✅ **Batch Mode** - Process multiple images in one request  
✅ **Enhanced Response** - Better formatted results with detailed status  
✅ **Summary Statistics** - Get approval/rejection counts and success rates  

---

## 📋 API Format

### Single Image (Original)
```json
{
  "input": {
    "image": "https://example.com/image.jpg",
    "category": "laptop",
    "pipeline": "full"
  }
}
```

### Multiple Images (NEW!)
```json
{
  "input": {
    "images": [
      {
        "image": "https://example.com/image1.jpg",
        "category": "smartphone"
      },
      {
        "image": "https://example.com/image2.jpg",
        "category": "headphones"
      },
      {
        "image": "https://example.com/image3.jpg",
        "category": "laptop"
      }
    ],
    "pipeline": "full"
  }
}
```

---

## 📊 Response Format

### Single Image Response
```json
{
  "mode": "single",
  "category": "smartphone",
  "pipeline_mode": "full",
  "final_decision": true,
  "final_confidence": 0.92,
  "matched_at": "clip",
  "risk_level": 45,
  "reasoning": "Risk level 45 is below threshold (85), auto-approved",
  "steps": [...]
}
```

### Batch Mode Response
```json
{
  "mode": "batch",
  "total_images": 3,
  "pipeline_mode": "full",
  "summary": {
    "approved": 2,
    "rejected": 1,
    "success_rate": "66.7%"
  },
  "results": [
    {
      "image_index": 1,
      "category": "smartphone",
      "final_decision": true,
      "final_confidence": 0.92,
      "matched_at": "clip",
      "risk_level": 45,
      "steps": [...]
    },
    {
      "image_index": 2,
      "category": "headphones",
      "final_decision": true,
      "final_confidence": 0.88,
      "matched_at": "clip",
      "risk_level": 32,
      "steps": [...]
    },
    {
      "image_index": 3,
      "category": "laptop",
      "final_decision": false,
      "final_confidence": 0.95,
      "matched_at": "qwen",
      "risk_level": 91,
      "reasoning": "Image contains promotional watermark",
      "steps": [...]
    }
  ]
}
```

---

## 🚀 Usage Examples

### Python - Single Image
```python
import requests

ENDPOINT_URL = "https://api.runpod.ai/v2/{ENDPOINT_ID}/run"
API_KEY = "your_api_key"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

data = {
    "input": {
        "image": "https://example.com/image.jpg",
        "category": "laptop",
        "pipeline": "full"
    }
}

response = requests.post(ENDPOINT_URL, headers=headers, json=data)
result = response.json()
print(f"Job ID: {result['id']}")
```

### Python - Multiple Images
```python
import requests

data = {
    "input": {
        "images": [
            {"image": "https://example.com/img1.jpg", "category": "smartphone"},
            {"image": "https://example.com/img2.jpg", "category": "headphones"},
            {"image": "https://example.com/img3.jpg", "category": "laptop"}
        ],
        "pipeline": "full"
    }
}

response = requests.post(ENDPOINT_URL, headers=headers, json=data)
result = response.json()
print(f"Job ID: {result['id']}")

# Check status
status_url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/status/{result['id']}"
status_response = requests.get(status_url, headers=headers)
status_result = status_response.json()

if status_result['status'] == 'COMPLETED':
    output = status_result['output']
    print(f"Total Images: {output['total_images']}")
    print(f"Approved: {output['summary']['approved']}")
    print(f"Rejected: {output['summary']['rejected']}")
```

### cURL - Batch Request
```bash
curl -X POST "https://api.runpod.ai/v2/{ENDPOINT_ID}/run" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -d '{
    "input": {
      "images": [
        {"image": "https://example.com/img1.jpg", "category": "smartphone"},
        {"image": "https://example.com/img2.jpg", "category": "laptop"}
      ],
      "pipeline": "full"
    }
  }'
```

---

## ⚙️ Pipeline Modes

- **`full`** (default) - Complete analysis: Quality → OCR → CLIP → Qwen (if risk ≥ 85)
- **`fast`** - Quick check: Quality → CLIP only
- **`quality_only`** - Quality check only (blur, corruption, screenshot detection)

---

## 📈 Benefits

### Batch Processing
- **Efficiency**: Process multiple images in one request
- **Cost Effective**: Reduced API calls
- **Better Tracking**: Get summary statistics
- **Scalability**: Handle bulk image verification

### Enhanced Response
- **Clear Status**: Each image gets detailed status
- **Summary Stats**: Quick overview of batch results
- **Better Formatting**: Easier to parse and display
- **Index Tracking**: Know which image in the batch failed/passed

---

## 🧪 Testing

Run the test script to see both modes in action:

```bash
python test_serverless.py
```

This will test:
1. ✅ Single image processing
2. ✅ Multiple images (batch mode)
3. ✅ Quality-only mode

---

## 💡 Tips

1. **Batch Size**: Keep batch size reasonable (3-10 images per request)
2. **Timeouts**: Larger batches take longer to process
3. **Error Handling**: Individual image errors won't stop the entire batch
4. **Categories**: Each image can have different categories
5. **Mixed Pipelines**: All images in a batch use the same pipeline mode

---

## 🐛 Error Handling

If an individual image fails in batch mode:
```json
{
  "image_index": 2,
  "category": "laptop",
  "error": "Failed to load image: Connection timeout",
  "final_decision": false,
  "final_confidence": 0.0
}
```

The batch continues processing remaining images.

---

## 📞 Support

For questions or issues, please check the main [README.md](README.md) or [SERVERLESS.md](SERVERLESS.md) documentation.
