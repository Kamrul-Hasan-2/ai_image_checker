# AI Image Checker - Quick Start Guide

## 🚀 3-Step Pipeline Implementation

This system implements a **3-step sequential pipeline** for comprehensive image analysis:

```
Step 1: EasyOCR → Step 2: CLIP → Step 3: Qwen2-VL
```

### Pipeline Overview

| Step | Model | Purpose | Output |
|------|-------|---------|--------|
| **1** | **EasyOCR** | Text extraction from images | Extracted text, promotional keywords, brand indicators |
| **2** | **CLIP** | Fast visual analysis | Category scoring, risk assessment, brand similarity, promo detection |
| **3** | **Qwen2-VL** | Final moderation | Decision (APPROVE/REJECT), explanations, dispute resolution |

---

## 📦 Installation

```powershell
# Install dependencies
pip install easyocr opencv-python

# All other dependencies should already be installed
```

---

## 🏃 Running the Server

```powershell
python main.py
```

**Expected startup sequence:**
```
==================================================
Starting AI Image Checker Server
==================================================

[Step 1/3] Loading EasyOCR...
✓ EasyOCR model loaded successfully

[Step 2/3] Loading CLIP model...
✓ CLIP model loaded on cpu/cuda

[Step 3/3] Loading Qwen2-VL model...
✓ Qwen2-VL model loaded on cpu/cuda

==================================================
✓ All models loaded successfully!
Pipeline: EasyOCR → CLIP → Qwen2-VL
Server ready to accept requests
==================================================
```

---

## 🔍 API Endpoints

### 1. Complete Pipeline Analysis (Recommended)

**Endpoint:** `POST /analyze/pipeline`

Runs all 3 steps sequentially with full context passing.

```powershell
curl -X POST "http://localhost:8000/analyze/pipeline" -F "file=@image.jpg"
```

**Response Structure:**
```json
{
  "success": true,
  "filename": "image.jpg",
  "pipeline_results": {
    "step1_ocr": {
      "text_found": true,
      "text_count": 5,
      "full_text": "Sale 50% OFF Limited Time",
      "analysis": {
        "has_promotional_text": true,
        "has_brand_indicators": false,
        "has_prices": true
      }
    },
    "step2_clip": {
      "category": {
        "top_category": "promotional banner",
        "confidence": 0.89
      },
      "risk": {
        "risk_level": "low",
        "safe_content_score": 0.95
      },
      "promo": {
        "is_promotional": true,
        "confidence": 0.87
      }
    },
    "step3_qwen2vl": {
      "decision": "APPROVE",
      "confidence": 92,
      "explanation": "Image contains promotional content but is safe...",
      "violations": [],
      "recommended_action": "approve"
    }
  },
  "final_summary": {
    "text_extracted": "Sale 50% OFF Limited Time",
    "has_promotional_content": true,
    "category": "promotional banner",
    "risk_level": "low",
    "final_decision": "APPROVE",
    "decision_confidence": 92,
    "explanation": "..."
  }
}
```

---

### 2. Individual Step Endpoints

Run each step independently for testing:

#### Step 1: OCR Only
```powershell
curl -X POST "http://localhost:8000/step1/ocr" -F "file=@image.jpg"
```

#### Step 2: CLIP Only
```powershell
curl -X POST "http://localhost:8000/step2/clip" -F "file=@image.jpg"
```

#### Step 3: Qwen2-VL Only
```powershell
curl -X POST "http://localhost:8000/step3/qwen" -F "file=@image.jpg"
```

---

### 3. Brand/Logo Similarity (CLIP)
```powershell
curl -X POST "http://localhost:8000/compare/similarity" \
  -F "file1=@logo1.jpg" \
  -F "file2=@logo2.jpg"
```

---

### 4. Dispute Resolution (Full Pipeline)
```powershell
curl -X POST "http://localhost:8000/dispute" \
  -F "file=@image.jpg" \
  -F "initial_decision=REJECT" \
  -F "dispute_reason=This is a false positive"
```

---

## 🎯 Use Cases

### Use Case 1: E-commerce Product Images
```python
import requests

# Check if product image has promotional banners
with open('product.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/analyze/pipeline',
        files={'file': f}
    )
    result = response.json()
    
    # Check results
    has_promo = result['final_summary']['has_promotional_content']
    decision = result['final_summary']['final_decision']
    
    print(f"Promotional: {has_promo}")
    print(f"Decision: {decision}")
```

### Use Case 2: Brand Logo Detection
```python
# Extract text from logo
with open('logo.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/step1/ocr',
        files={'file': f}
    )
    ocr_result = response.json()
    print(f"Brand text found: {ocr_result['result']['full_text']}")

# Compare two logos
with open('logo1.jpg', 'rb') as f1, open('logo2.jpg', 'rb') as f2:
    response = requests.post(
        'http://localhost:8000/compare/similarity',
        files={'file1': f1, 'file2': f2}
    )
    similarity = response.json()['similarity']['similarity_score']
    print(f"Logos are {similarity:.1%} similar")
```

### Use Case 3: Content Moderation
```python
# Full moderation with all 3 steps
with open('user_upload.jpg', 'rb') as f:
    response = requests.post(
        'http://localhost:8000/analyze/pipeline',
        files={'file': f}
    )
    result = response.json()
    
    summary = result['final_summary']
    print(f"Risk Level: {summary['risk_level']}")
    print(f"Decision: {summary['final_decision']}")
    print(f"Confidence: {summary['decision_confidence']}%")
    print(f"Explanation: {summary['explanation']}")
```

---

## 🔄 Pipeline Flow

```
┌─────────────────────────────────────────────────┐
│              Image Upload                        │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  STEP 1: EasyOCR                                │
│  - Extract all text from image                  │
│  - Detect promotional keywords                  │
│  - Find brand indicators (®, ™, ©)              │
│  - Analyze text density                         │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  STEP 2: CLIP (OpenAI)                          │
│  ✓ Fast category scoring (10 categories)       │
│  ✓ Risk assessment (6 risk levels)             │
│  ✓ Brand/logo similarity analysis               │
│  ✓ Promotional banner detection                 │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│  STEP 3: Qwen2-VL                               │
│  ✓ Final APPROVE/REJECT decision                │
│  ✓ Detailed explanations                        │
│  ✓ Policy violation detection                   │
│  ✓ Dispute resolution                           │
│  (Uses context from Steps 1 & 2)               │
└────────────────┬────────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────────┐
│           Final Decision + Report                │
└─────────────────────────────────────────────────┘
```

---

## 📊 Performance

| Step | Model Size | Inference Time | GPU Memory |
|------|-----------|----------------|------------|
| EasyOCR | ~100MB | ~500ms | ~1GB |
| CLIP | ~600MB | ~50ms | ~1GB |
| Qwen2-VL-2B | ~4GB | ~1-3s | ~6GB |

**Total Pipeline:** ~2-4 seconds per image (GPU)

---

## 🐛 Troubleshooting

### Models not loading
```powershell
# Check Python version (3.8+ required)
python --version

# Reinstall dependencies
pip install -r requirements.txt --upgrade
```

### Out of memory
- Use CPU instead of GPU (slower but works)
- Process images one at a time
- Reduce image resolution before upload

### Text not detected
- Ensure image has clear, readable text
- Try different image formats (JPG, PNG)
- Check image isn't too small or low quality

---

## 📚 Documentation

Visit **http://localhost:8000/docs** for interactive API documentation (Swagger UI)

Visit **http://localhost:8000/redoc** for alternative documentation (ReDoc)

---

## 🎓 Example Workflow

1. **Upload image** → Server receives file
2. **Step 1 (EasyOCR)** → Extracts "50% OFF SALE"
3. **Step 2 (CLIP)** → Detects "promotional banner", risk=low
4. **Step 3 (Qwen2-VL)** → Final decision: APPROVE with 95% confidence
5. **Return results** → JSON with all analysis data

---

## 💡 Tips

- Use `/analyze/pipeline` for production (most comprehensive)
- Use individual step endpoints for debugging
- Monitor console logs to see pipeline progress
- First request will be slower (model warmup)
- Batch similar images together for efficiency

---

## 🔗 Health Check

```powershell
curl http://localhost:8000/
```

Should return:
```json
{
  "status": "healthy",
  "pipeline": "EasyOCR → CLIP → Qwen2-VL",
  "models": {
    "step1_ocr": "loaded",
    "step2_clip": "loaded",
    "step3_qwen2vl": "loaded"
  }
}
```
