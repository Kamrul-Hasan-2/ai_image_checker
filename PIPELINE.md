# 🚀 AI Image Checker - Smart Pipeline v3.0

## Pipeline Architecture

```
Step 1: OpenCV Quality Check (CPU, local)
  ├─ Blur, low-res, aspect ratio, screenshot/UI, corrupted
  ├─ ✗ Fail → BLOCK immediately
  └─ ✓ Pass → Step 2

Step 2: OCR Text Detection (CPU, local - EasyOCR)
  ├─ Detect text existence only
  ├─ ✗ No text → APPROVE (+ CLIP category check, STOP)
  └─ ✓ Text exists → Step 3

Step 3: CLIP Risk Scoring (CPU, local)
  ├─ Model: openai/clip-vit-base-patch32
  ├─ Compute scores: promo/weapon/medical/stock/violent
  ├─ risk = max(scores)
  ├─ ✓ risk < 0.70 → APPROVE
  └─ ✗ risk ≥ 0.70 → Step 4

Step 4: Qwen2-VL-2B Moderation (GPU)
  ├─ Final decision + detailed reasoning
  ├─ ✓ confidence ≥ 0.85 AND risk < 0.85 → ACCEPT decision
  └─ ✗ confidence < 0.85 OR risk ≥ 0.85 → Step 5

Step 5: Qwen2-VL-7B Final Review (GPU, rare)
  ├─ High-risk cases, disputes, electronics/medical
  ├─ Conflicts between models
  └─ FINAL decision (cannot be overridden)
```

## Thresholds (Locked)

| Threshold | Value | Purpose |
|-----------|-------|---------|
| **CLIP Escalation** | ≥ 0.70 | Escalate to Qwen2-VL-2B |
| **Qwen2B Confidence** | ≥ 0.85 | Accept 2B decision |
| **Qwen2B Risk** | < 0.85 | Accept 2B decision (with high conf) |
| **Qwen7B Trigger** | Always if above thresholds not met | Final review |

## Processing Notes

- **CLIP runs on CPU** (fast, ~50-100ms)
- **GPU used only for Qwen models** (2B: ~1-3s, 7B: ~3-5s)
- **OCR text required** before escalating to Qwen models
- **Expected accuracy**: 88-92%
- **Most images stop at Step 2 or 3** (fast approval)
- **Only ~10-20% reach Qwen2B** (Step 4)
- **Only ~2-5% reach Qwen7B** (Step 5)

## Risk Categories (CLIP)

1. **Safe general content** (baseline)
2. **Promotional advertisement**
3. **Weapons or firearms**
4. **Medical drugs or substances**
5. **Financial stock trading**
6. **Violent or graphic content**

## Running the Server

```powershell
python main.py
```

Expected startup:
```
==================================================
AI IMAGE CHECKER - SMART PIPELINE v3.0
==================================================

[1/5] OpenCV Quality Check...
✓ Quality Check Service initialized

[2/5] EasyOCR (CPU)...
✓ EasyOCR model loaded successfully

[3/5] CLIP (CPU)...
✓ CLIP model loaded on cpu

[4/5] Qwen2-VL-2B (GPU)...
✓ Qwen2-VL model loaded

[5/5] Qwen2-VL-7B (GPU)...
✓ Qwen2-VL model loaded

==================================================
✓ ALL MODELS LOADED - Expected Accuracy: 88-92%
==================================================
```

## API Endpoints

### Main Analysis Endpoint

**POST /analyze**

Uploads an image and runs it through the smart pipeline.

```powershell
curl -X POST "http://localhost:8000/analyze" -F "file=@image.jpg"
```

**Response Structure:**
```json
{
  "success": true,
  "filename": "image.jpg",
  "final_decision": "APPROVE",
  "reason": "Low risk score: 0.45",
  "stopped_at": 3,
  "risk": 0.45,
  "category": "product photo",
  "log": [
    {"step": 1, "service": "Quality", "result": {"passed": true}},
    {"step": 2, "service": "OCR", "text_found": true},
    {"step": 3, "service": "CLIP", "risk": 0.45}
  ]
}
```

### Dispute Resolution

**POST /dispute**

Uses Qwen7B for final review of disputed decisions.

```powershell
curl -X POST "http://localhost:8000/dispute" \
  -F "file=@image.jpg" \
  -F "decision=REJECT" \
  -F "reason=This is a false positive"
```

## Test Example

```powershell
# Test with the provided image
python test_image.py
```

This will:
1. Download the image from the URL
2. Run through the complete pipeline
3. Show which step made the final decision
4. Display full results

## Pipeline Decision Flow

```
Image Upload
    ↓
[Quality Check]
    ├─ FAIL → ❌ REJECT (BLOCKED)
    └─ PASS → Continue
         ↓
    [OCR Check]
    ├─ NO TEXT → ✅ APPROVE (Fast path)
    └─ TEXT FOUND → Continue
         ↓
    [CLIP Risk]
    ├─ RISK < 0.70 → ✅ APPROVE (Most common)
    └─ RISK ≥ 0.70 → Continue
         ↓
    [Qwen 2B]
    ├─ CONF ≥ 0.85 & RISK < 0.85 → ✅/❌ ACCEPT DECISION
    └─ Otherwise → Continue
         ↓
    [Qwen 7B]
    └─ FINAL DECISION ✅/❌ (Cannot appeal)
```

## Performance Expectations

| Step | Avg Time | % of Images | Outcome |
|------|----------|-------------|---------|
| Step 1 | ~10ms | ~2-5% | BLOCK (quality) |
| Step 2 | ~500ms | ~30-40% | APPROVE (no text) |
| Step 3 | ~100ms | ~40-50% | APPROVE (low risk) |
| Step 4 | ~2s | ~8-15% | APPROVE/REJECT (2B) |
| Step 5 | ~4s | ~2-5% | FINAL (7B) |

**Total processing time:**
- Fast path (Steps 1-3): ~600ms
- Medium (Step 4): ~2.6s
- Full pipeline (Step 5): ~6.6s

## File Structure

```
ai_image_checker/
├── main.py                 # Smart pipeline server
├── quality_service.py      # Step 1: OpenCV quality checks
├── ocr_service.py          # Step 2: EasyOCR text detection
├── clip_service.py         # Step 3: CLIP risk scoring
├── qwen_service.py         # Steps 4&5: Qwen2B & Qwen7B
├── test_image.py           # Test script
├── requirements.txt        # Dependencies
└── PIPELINE.md            # This file
```

## Notes

- **Early stopping** saves compute (most images approved at Step 2-3)
- **Text detection is mandatory** for Qwen escalation
- **GPU only used when necessary** (Steps 4-5)
- **7B model is rare** (~2-5% of images)
- **No appeals from 7B** decision is final
- **Disputes always use 7B** for highest accuracy
