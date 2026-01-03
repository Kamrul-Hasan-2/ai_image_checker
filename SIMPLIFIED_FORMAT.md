# ✅ Simplified JSON Response Format

## What Changed

**BEFORE:** Verbose response with "steps" array and many unnecessary fields  
**AFTER:** Clean, simple JSON with only essential information

---

## New Response Format

```json
{
  "OpenCV": {
    "blur_image": "yes",           // Image is blurry
    "screen_short": "no",           // Not a screenshot
    "too_small": "no"               // Resolution is OK
  },
  "ocr": {
    "image_extract": "Valh"         // Text found in image
  },
  "clip": {
    "promotional_text": "yes",      // Promotional content detected
    "watermark": "no",              // No watermark
    "illegal": "no",                // Not illegal content
    "has_phone_number": "yes",      // Phone number detected
    "promotional_score": 0.45,      // Promo confidence (0-1)
    "CATEGORY_MATCH": "no",         // Category doesn't match
    "stock_photo": "no"             // Not a stock photo
  },
  "risk_level": 96,                 // Risk score (0-100)
  
  // ⚠️ Only appears if risk_level >= 85
  "qwen_vl_2b": {
    "is_promotional_text": "yes",
    "image_description": "Product image with promotional banner and contact info",
    "is_ai_generated": "no",
    "needs_manual_moderation": "yes"
  },
  
  "final_decision": "rejected"      // approved or rejected
}
```

---

## Field Explanations

### OpenCV Section
| Field | Values | Description |
|-------|--------|-------------|
| `blur_image` | yes/no | Image is blurry (multi-algorithm detection) |
| `screen_short` | yes/no | Image is a screenshot or UI element |
| `too_small` | yes/no | Image resolution too small |

### OCR Section
| Field | Values | Description |
|-------|--------|-------------|
| `image_extract` | string | Text extracted from image |

### CLIP Section
| Field | Values | Description |
|-------|--------|-------------|
| `promotional_text` | yes/no | Promotional content detected |
| `watermark` | yes/no | Watermark detected |
| `illegal` | yes/no | Illegal content detected |
| `has_phone_number` | yes/no | Phone number found |
| `promotional_score` | 0.0-1.0 | Promotional confidence score |
| `CATEGORY_MATCH` | yes/no | Category matches input |
| `stock_photo` | yes/no | Stock photo detected |

### Risk Level
| Value | Meaning |
|-------|---------|
| 0-40 | Low risk (safe) |
| 41-70 | Medium risk |
| 71-84 | High risk (monitored) |
| 85-100 | Very high risk (escalates to Qwen) |

### Qwen VL 2B Section (Only if risk_level >= 85)
| Field | Values | Description |
|-------|--------|-------------|
| `is_promotional_text` | yes/no | AI confirms promotional content |
| `image_description` | string | Detailed description from AI |
| `is_ai_generated` | yes/no | Image is AI-generated |
| `needs_manual_moderation` | yes/no | Requires human review |

### Final Decision
| Value | Meaning |
|-------|---------|
| `approved` | Image passed all checks |
| `rejected` | Image failed one or more checks |

---

## Example Responses

### ✅ Good Product Image (Approved)
```json
{
  "OpenCV": {
    "blur_image": "no",
    "screen_short": "no",
    "too_small": "no"
  },
  "ocr": {
    "image_extract": "MacBook Pro"
  },
  "clip": {
    "promotional_text": "no",
    "watermark": "no",
    "illegal": "no",
    "has_phone_number": "no",
    "promotional_score": 0.12,
    "CATEGORY_MATCH": "yes",
    "stock_photo": "no"
  },
  "risk_level": 15,
  "final_decision": "approved"
}
```

### ❌ Blurry Image (Rejected)
```json
{
  "OpenCV": {
    "blur_image": "yes",
    "screen_short": "no",
    "too_small": "no"
  },
  "ocr": {
    "image_extract": "No text detected"
  },
  "clip": {
    "promotional_text": "no",
    "watermark": "no",
    "illegal": "no",
    "has_phone_number": "no",
    "promotional_score": 0.05,
    "CATEGORY_MATCH": "yes",
    "stock_photo": "no"
  },
  "risk_level": 8,
  "final_decision": "rejected"
}
```

### ⚠️ Promotional Image with Phone Number (High Risk)
```json
{
  "OpenCV": {
    "blur_image": "no",
    "screen_short": "no",
    "too_small": "no"
  },
  "ocr": {
    "image_extract": "Call Now: 01712345678 Special Offer!"
  },
  "clip": {
    "promotional_text": "yes",
    "watermark": "no",
    "illegal": "no",
    "has_phone_number": "yes",
    "promotional_score": 0.89,
    "CATEGORY_MATCH": "yes",
    "stock_photo": "no"
  },
  "risk_level": 92,
  "qwen_vl_2b": {
    "is_promotional_text": "yes",
    "image_description": "Product image with promotional banner containing phone number and call-to-action text",
    "is_ai_generated": "no",
    "needs_manual_moderation": "yes"
  },
  "final_decision": "rejected"
}
```

---

## Testing

### Single Image
```python
python test_simplified.py
```

### Multiple Images
```python
python test_serverless.py
```

---

## Benefits

✅ **Clean & Simple** - Only essential information  
✅ **Easy to Parse** - Flat structure, no nested "steps" arrays  
✅ **Consistent Format** - Same structure for all responses  
✅ **Yes/No Flags** - Clear boolean values as strings  
✅ **Conditional Qwen** - Only appears when risk_level >= 85  
✅ **Final Decision** - Clear "approved" or "rejected" status  

---

## Deployment

1. Upload updated `handler.py` to RunPod
2. Test with `test_simplified.py`
3. Verify response format matches specification

**Ready to use!** 🚀
