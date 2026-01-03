# Plain JSON Format with Severity Scores

## Response Structure

```json
{
  // Quality Detection (yes/no format)
  "blur_detection": "yes",
  "blur_score": 28.5,
  "screenshort_check": "no",
  "corruption_check": "no",
  
  // OCR Text Extraction
  "image_extract": "Just some text about image",
  
  // Content Detection (true/false format)
  "has_brand_indicators": true,
  "has_phone_number": true,
  "has_prices": false,
  "has_promotional_text": true,
  "has_website_link": true,
  "is_promotional": true,
  "stock_photo": false,
  "illegal_photo": false,
  
  // Category
  "category": "Computer » Monitor » Monitor",
  "category_match": false,
  
  // Severity Scores (numeric)
  "blur_image": 5,
  "screen_short": 0,
  "category_mismatch": 2,
  "illegal": 0,
  "promotional_text": 3,
  "stock_photo_score": 0,
  "watermark": 0,
  
  // Risk Totals
  "total_risk_score": 10,
  "risk_level": 65,
  
  // Qwen Analysis (only if risk_level >= 85)
  "qwen_vl_2b": {
    "is_promotional_text": true,
    "image_description": "Product image with promotional banner",
    "is_ai_generated": false,
    "needs_manual_moderation": true
  },
  
  // Final Decision
  "final_decision": "rejected"
}
```

## Severity Score Table

| Issue | Yes Score | No Score |
|-------|-----------|----------|
| **blur_image** | 5 | 0 |
| **screen_short** | 8 | 0 |
| **category_mismatch** | 2 | 0 |
| **illegal** | 9 | 0 |
| **promotional_text** | 3 | 0 |
| **stock_photo_score** | 10 | 0 |
| **watermark** | 4 | 0 |

## Decision Logic

```
total_risk_score = sum of all severity scores

if total_risk_score > 0 OR risk_level >= 85:
    final_decision = "rejected"
else:
    final_decision = "approved"
```

## Examples

### ✅ Clean Product Image (Approved)
```json
{
  "blur_detection": "no",
  "blur_score": 87.3,
  "screenshort_check": "no",
  "corruption_check": "no",
  "image_extract": "MacBook Pro 16 inch",
  "has_brand_indicators": true,
  "has_phone_number": false,
  "has_prices": false,
  "has_promotional_text": false,
  "has_website_link": false,
  "is_promotional": false,
  "stock_photo": false,
  "illegal_photo": false,
  "category": "Computer » Laptop",
  "category_match": true,
  "blur_image": 0,
  "screen_short": 0,
  "category_mismatch": 0,
  "illegal": 0,
  "promotional_text": 0,
  "stock_photo_score": 0,
  "watermark": 0,
  "total_risk_score": 0,
  "risk_level": 12,
  "final_decision": "approved"
}
```

### ❌ Blurry Image (Rejected)
```json
{
  "blur_detection": "yes",
  "blur_score": 23.1,
  "screenshort_check": "no",
  "corruption_check": "no",
  "image_extract": "Product name",
  "has_brand_indicators": false,
  "has_phone_number": false,
  "has_prices": false,
  "has_promotional_text": false,
  "has_website_link": false,
  "is_promotional": false,
  "stock_photo": false,
  "illegal_photo": false,
  "category": "Smartphone",
  "category_match": true,
  "blur_image": 5,
  "screen_short": 0,
  "category_mismatch": 0,
  "illegal": 0,
  "promotional_text": 0,
  "stock_photo_score": 0,
  "watermark": 0,
  "total_risk_score": 5,
  "risk_level": 8,
  "final_decision": "rejected"
}
```

### ⚠️ Promotional with Phone Number (Rejected)
```json
{
  "blur_detection": "no",
  "blur_score": 92.5,
  "screenshort_check": "no",
  "corruption_check": "no",
  "image_extract": "Call Now: 01712345678 - Best Price!",
  "has_brand_indicators": true,
  "has_phone_number": true,
  "has_prices": true,
  "has_promotional_text": true,
  "has_website_link": false,
  "is_promotional": true,
  "stock_photo": false,
  "illegal_photo": false,
  "category": "Smartphone",
  "category_match": true,
  "blur_image": 0,
  "screen_short": 0,
  "category_mismatch": 0,
  "illegal": 0,
  "promotional_text": 3,
  "stock_photo_score": 0,
  "watermark": 0,
  "total_risk_score": 3,
  "risk_level": 75,
  "final_decision": "rejected"
}
```

### 🚨 High Risk - Goes to Qwen (Rejected)
```json
{
  "blur_detection": "no",
  "blur_score": 88.2,
  "screenshort_check": "no",
  "corruption_check": "no",
  "image_extract": "Visit www.example.com - Call 01712345678",
  "has_brand_indicators": true,
  "has_phone_number": true,
  "has_prices": true,
  "has_promotional_text": true,
  "has_website_link": true,
  "is_promotional": true,
  "stock_photo": false,
  "illegal_photo": false,
  "category": "Laptop",
  "category_match": true,
  "blur_image": 0,
  "screen_short": 0,
  "category_mismatch": 0,
  "illegal": 0,
  "promotional_text": 3,
  "stock_photo_score": 0,
  "watermark": 0,
  "total_risk_score": 3,
  "risk_level": 96,
  "qwen_vl_2b": {
    "is_promotional_text": true,
    "image_description": "Product image with promotional banner containing website and phone number",
    "is_ai_generated": false,
    "needs_manual_moderation": true
  },
  "final_decision": "rejected"
}
```

## Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `blur_detection` | string | "yes" or "no" |
| `blur_score` | number | 0-100 (higher = sharper) |
| `screenshort_check` | string | "yes" if screenshot detected |
| `corruption_check` | string | "yes" if corrupted |
| `image_extract` | string | Text found in image |
| `has_brand_indicators` | boolean | Brand logos detected |
| `has_phone_number` | boolean | Phone number found |
| `has_prices` | boolean | Price information found |
| `has_promotional_text` | boolean | Promotional keywords found |
| `has_website_link` | boolean | Website/URL found |
| `is_promotional` | boolean | Overall promotional detection |
| `stock_photo` | boolean | Stock photo detected |
| `illegal_photo` | boolean | Illegal content detected |
| `category` | string | Product category |
| `category_match` | boolean | Category matches input |
| `blur_image` | number | 5 or 0 |
| `screen_short` | number | 8 or 0 |
| `category_mismatch` | number | 2 or 0 |
| `illegal` | number | 9 or 0 |
| `promotional_text` | number | 3 or 0 |
| `stock_photo_score` | number | 10 or 0 |
| `watermark` | number | 4 or 0 |
| `total_risk_score` | number | Sum of all severity scores |
| `risk_level` | number | 0-100 AI risk assessment |
| `final_decision` | string | "approved" or "rejected" |

## Test

```bash
python test_simplified.py
```

## Deploy

Upload `handler.py` to RunPod - plain JSON format ready! 🚀
