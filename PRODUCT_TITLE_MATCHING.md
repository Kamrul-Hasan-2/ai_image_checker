# Product Title Matching Feature

## Overview
The system now supports **product title matching** to prevent false positives. If you provide a product title, and that title matches the text found in the image (via OCR), the system will recognize it as the product name and **NOT flag it as promotional content**.

## Use Case
You're selling a laptop titled "Dell Inspiron 15 3000". The product image shows the laptop box with "Dell Inspiron 15" printed on it. Without title matching, the system might flag this as promotional text. With title matching, it correctly identifies this as the product itself.

## How It Works

### Matching Algorithm
1. Extract all text from image using OCR
2. Compare product title words with OCR text
3. If ≥60% of title words found in OCR text → **Title Match**
4. Title match = promotional confidence 0.0 (SAFE)

### Priority Order
```
1. Title Match (HIGHEST PRIORITY) → confidence: 0.0
2. Visual Product Detection → confidence: 0.0
3. Text-Only Product Detection → confidence: 0.0
4. Promotional Signals → confidence: 0.90-0.99
```

## API Usage

### Single Image Request
```json
{
  "image": "https://example.com/laptop.jpg",
  "category": "laptop",
  "title": "Dell Inspiron 15 3000",
  "pipeline": "full"
}
```

### Multiple Images Request
```json
{
  "images": [
    {
      "image": "https://cdn.bdstall.com/product-image/419709_600X600.webp",
      "category": "laptop",
      "title": "Dell Inspiron 15 3000"
    },
    {
      "image": "https://example.com/camera.jpg",
      "category": "camera",
      "title": "Imou 3K 5MP Cruiser SC Security Camera"
    }
  ],
  "pipeline": "full"
}
```

### Without Title (Fallback to Other Detection)
```json
{
  "image": "https://example.com/product.jpg",
  "category": "electronics"
  // No title provided - uses visual/text detection
}
```

## Examples

### Example 1: Laptop with Exact Title Match
```json
{
  "title": "Dell Inspiron 15",
  "ocr_text": "Dell Inspiron 15 3000 Series"
}
```
**Result:** NOT PROMOTIONAL ✓ (3/3 words matched)

### Example 2: Camera with Model Number (Your Case)
```json
{
  "title": "Imou 3K 5MP Cruiser SC Security Camera",
  "ocr_text": "Imou 3K 5MP Cruiser SC Remote viewing"
}
```
**Result:** NOT PROMOTIONAL ✓ (5/7 words matched = 71%)

### Example 3: Phone with Partial Match
```json
{
  "title": "Samsung Galaxy A54 5G",
  "ocr_text": "Samsung Galaxy A54 128GB"
}
```
**Result:** NOT PROMOTIONAL ✓ (3/4 words matched = 75%)

### Example 4: Product with Price on Packaging
```json
{
  "title": "LG Inverter AC 1.5 Ton",
  "ocr_text": "LG Inverter 1.5 Ton 18000 BTU ৳45,999"
}
```
**Result:** NOT PROMOTIONAL ✓ (Title match overrides price detection)

### Example 5: Title Doesn't Match - Falls Back
```json
{
  "title": "Samsung Phone",
  "ocr_text": "Buy iPhone 15 Pro Call: 01712345678"
}
```
**Result:** PROMOTIONAL ✗ (Only 1/2 words matched, has phone number)

## Word Matching Rules

### Included Words
- Words with length > 1 character
- All alphanumeric words (including numbers like "3K", "5MP", "15")

### Excluded Words
- Single characters: "a", "i", "x" (too generic)

### Case-Insensitive
- "Dell" matches "dell"
- "WiFi" matches "wifi"

### Partial Words
- "Inspiron" must match exactly
- "15" in title matches "15" in OCR (not "150" or "1500")

## Match Threshold

**60% threshold** means:
- 3/5 words matched = 60% → MATCH ✓
- 2/5 words matched = 40% → NO MATCH ✗
- 5/7 words matched = 71% → MATCH ✓

## Benefits

### 1. Reduces False Positives
- Product packaging text = SAFE
- Product model numbers = SAFE
- Technical specifications = SAFE

### 2. Works with Price on Packaging
Even if OCR detects a price sticker on product packaging, title match takes priority.

### 3. Fuzzy Matching
Handles variations:
- "Dell Inspiron 15" matches "Dell Inspiron 15 3000"
- "Samsung A54" matches "Samsung Galaxy A54 5G"
- "Imou Camera" matches "Imou 3K 5MP Security Camera"

### 4. Language Agnostic
Works with any language as long as title and OCR text use same script.

## Testing

Run the test suite:
```bash
python test_product_title.py
```

Expected output: **8 passed, 0 failed** ✓

## Integration Example (Python)

```python
import requests

# Your API endpoint
url = "https://your-modal-app.modal.run/check"

# Product data
data = {
    "images": [
        {
            "image": "https://cdn.bdstall.com/product-image/419709_600X600.webp",
            "category": "laptop",
            "title": "Dell Inspiron 15 3000 Series"
        }
    ],
    "pipeline": "full"
}

# Make request
response = requests.post(url, json=data)
result = response.json()

# Check promotional score
promo_score = result[0]["promotional_text"]
print(f"Promotional score: {promo_score}/10")
# Expected: 0 (title matches product image)
```

## Best Practices

### 1. Provide Accurate Titles
Use the exact product name from your database:
```json
✓ "Dell Inspiron 15 3000"
✓ "Samsung Galaxy A54 5G 128GB"
✓ "Imou 3K 5MP Cruiser SC"
```

### 2. Include Model Numbers
Model numbers help with matching:
```json
✓ "TP-Link AX1800 WiFi 6 Router"
✓ "LG Inverter AC 1.5 Ton"
```

### 3. Avoid Generic Titles
Too generic = low match confidence:
```json
✗ "Laptop"
✗ "Phone"
✗ "Camera"
```

### 4. Handle Variations
If your title has multiple variations, use the most descriptive one:
```json
✓ "Samsung Galaxy A54 5G" (descriptive)
✗ "Samsung A54" (too short, may miss context)
```

## Performance

- **Title matching:** ~1ms (string comparison)
- **No additional inference:** Uses existing OCR results
- **No impact on speed:** Runs in parallel with other checks

## Limitations

### 1. OCR Quality
If OCR fails to extract text accurately, title matching may fail. This is why we have fallback detection methods.

### 2. Language Mismatch
Title in English but product text in Bengali → No match. Use consistent language.

### 3. Abbreviations
"WiFi" in title but "Wi-Fi" in OCR → May not match. Normalize titles.

## Future Improvements

1. **Fuzzy string matching:** Use Levenshtein distance for typos
2. **Synonym matching:** "Phone" matches "Mobile", "Cell"
3. **Language translation:** Auto-translate for cross-language matching
4. **Brand aliases:** "HP" matches "Hewlett-Packard"

## Related Features

- **Visual Product Detection:** [PRODUCT_DETECTION_LOGIC.md](PRODUCT_DETECTION_LOGIC.md)
- **Product Branding Test:** [test_product_branding.py](test_product_branding.py)
- **OCR Service:** [ocr_service.py](ocr_service.py)

## Support

For issues or questions:
1. Check test files for examples
2. Verify title format (alphanumeric, spaces)
3. Ensure OCR can extract text from image
4. Test with `test_product_title.py`
