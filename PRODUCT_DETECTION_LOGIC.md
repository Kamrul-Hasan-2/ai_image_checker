# Product Photo Detection Logic

## Problem Statement
Product images often contain text (brand names, model numbers, specifications) that should NOT be flagged as promotional content. Example: A security camera box with "Imou 3K 5MP" printed on it.

## Solution: Three-Tier Detection System

### Tier 1: Visual Product Detection (HIGHEST PRIORITY)
**Technology:** CLIP visual-semantic model  
**Purpose:** Detect if image shows an actual product

#### Detection Criteria:
- Clean product photography on white background
- Product in packaging/box
- Professional product image without text overlay
- Product displayed on shelf or table
- E-commerce product listing photo

#### Logic:
```python
if is_product_photo (CLIP confidence > 0.30):
    → Text on image = NOT PROMOTIONAL
    → Confidence = 0.0
    → SAFE ✓
```

**Examples:**
- ✓ Security camera in box with "Imou 3K 5MP" text
- ✓ iPhone packaging with Apple logo
- ✓ Router with "WiFi 6" specs printed on it
- ✓ Product with price on packaging (e.g., "$99.99" sticker on box)

### Tier 2: Text-Only Product Detection
**Technology:** OCR + Rule-based analysis  
**Purpose:** Identify product branding vs promotional text

#### Detection Criteria:
```
is_product_text_only = True IF:
  - NO phone number detected
  - NO website/link detected  
  - NO price detected
  - NO e-commerce UI (Buy Now, Add to Cart)
  - NO strong sale terms (discount, sale, offer)
```

#### Logic:
```python
if is_product_text_only:
    → Text = Product branding/specs
    → Confidence = 0.0
    → SAFE ✓
```

**Examples:**
- ✓ "Samsung Galaxy A54"
- ✓ "ONV PoE 8G+2G Full 1000M Smart PoE Switch"
- ✓ "LG Inverter 1.5 Ton 18000 BTU"

### Tier 3: Promotional Signal Detection
**Technology:** OCR + Pattern matching  
**Purpose:** Flag actual promotional content

#### Detection Criteria:
```
promotional_detected = True IF:
  - Has phone number (01712345678)
  - Has price (৳24,999, 99,999 tk)
  - Has website/link (www.shop.com)
  - Has e-commerce UI (Buy Now, Add to Cart)
```

#### Confidence Levels:
- `0.99` - Phone number or website detected
- `0.98` - Price detected
- `0.90` - E-commerce UI elements

**Examples:**
- ✗ "iPhone 15 Pro Price: 99,999 tk Call: 01712345678"
- ✗ "Samsung Galaxy BUY NOW www.shop.com"
- ✗ "Smart Router SALE 50% OFF"

## Decision Flow

```
Image Input
    │
    ├─→ Visual Product Detection (CLIP)
    │   │
    │   ├─→ is_product_photo = True?
    │   │   └─→ YES → NOT PROMOTIONAL ✓ (confidence: 0.0)
    │   │
    │   └─→ NO → Continue to Tier 2
    │
    ├─→ Text-Only Product Detection (OCR)
    │   │
    │   ├─→ is_product_text_only = True?
    │   │   └─→ YES → NOT PROMOTIONAL ✓ (confidence: 0.0)
    │   │
    │   └─→ NO → Continue to Tier 3
    │
    └─→ Promotional Signal Detection
        │
        ├─→ has_phone OR has_link?
        │   └─→ YES → PROMOTIONAL ✗ (confidence: 0.99)
        │
        ├─→ has_price?
        │   └─→ YES → PROMOTIONAL ✗ (confidence: 0.98)
        │
        └─→ has_ecommerce_ui?
            └─→ YES → PROMOTIONAL ✗ (confidence: 0.90)
```

## Key Insights

### Why Visual Detection is Critical
1. **Packaging text is legitimate**: Product boxes show brand names, specs, model numbers
2. **E-commerce photos are clean**: Professional product photos are NOT ads
3. **Context matters**: Same text has different meaning on product vs promotional banner

### Example Comparisons

| Image Type | Text Content | Product Photo? | Result |
|------------|--------------|----------------|--------|
| Camera in box | "Imou 3K 5MP Cruiser SC" | ✓ Yes | NOT PROMOTIONAL |
| Promotional banner | "Imou Camera 99,999 tk Call Now" | ✗ No | PROMOTIONAL |
| iPhone packaging | "iPhone 15 Pro" | ✓ Yes | NOT PROMOTIONAL |
| Sale flyer | "iPhone 15 Pro Price: 99,999 tk" | ✗ No | PROMOTIONAL |
| Router on table | "WiFi 6 1000M" | ✓ Yes | NOT PROMOTIONAL |
| Ad poster | "WiFi Router SALE www.shop.com" | ✗ No | PROMOTIONAL |

## Implementation Files

- **[clip_service.py](clip_service.py)** - `detect_product_photo()` method (lines 995-1041)
- **[ocr_service.py](ocr_service.py)** - `is_product_text_only` flag (lines 249-263)
- **[modal_handler.py](modal_handler.py)** - Integration logic (lines 162-218)
- **[test_product_branding.py](test_product_branding.py)** - Test cases and validation

## Testing

Run the test suite:
```bash
python test_product_branding.py
```

Expected output: **10 passed, 0 failed** ✓

## Performance Impact

- **Visual detection**: ~50-100ms per image (CLIP inference)
- **Text detection**: ~200-300ms per image (OCR already running)
- **Overall impact**: Minimal, as OCR is already the bottleneck

## Future Improvements

1. **Fine-tune CLIP**: Train on e-commerce product photos for better accuracy
2. **Cache results**: Store product photo detection results to avoid re-inference
3. **Multi-region analysis**: Detect if text is overlaid vs printed on product
4. **Confidence calibration**: Adjust thresholds based on real-world data
