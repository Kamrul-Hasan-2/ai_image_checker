"""
Test to verify product title matching prevents promotional false positives
"""

def test_product_title_matching():
    """Test that matching product titles with OCR text = NOT promotional"""
    
    print("=" * 70)
    print("PRODUCT TITLE MATCHING TEST")
    print("=" * 70)
    print("\nRule: If product title matches OCR text → NOT promotional")
    print("Even if text contains specs/features on product image")
    print("=" * 70 + "\n")
    
    test_cases = [
        {
            "name": "Dell Laptop - Title matches exactly",
            "title": "Dell Inspiron 15",
            "ocr_text": "Dell Inspiron 15 3000 Series",
            "has_price": False,
            "expected": "NOT PROMOTIONAL",
            "expected_match": True
        },
        {
            "name": "Imou Camera - Title matches (your example)",
            "title": "Imou 3K 5MP Cruiser SC Security Camera",
            "ocr_text": "Imou 3K 5MP Cruiser SC Remote viewing",
            "has_price": False,
            "expected": "NOT PROMOTIONAL",
            "expected_match": True
        },
        {
            "name": "Samsung Phone - Partial match (>60%)",
            "title": "Samsung Galaxy A54 5G",
            "ocr_text": "Samsung Galaxy A54 128GB",
            "has_price": False,
            "expected": "NOT PROMOTIONAL",
            "expected_match": True
        },
        {
            "name": "Router - Title match with specs",
            "title": "TP-Link WiFi 6 Router",
            "ocr_text": "TP-Link WiFi 6 AX1800 Dual Band",
            "has_price": False,
            "expected": "NOT PROMOTIONAL",
            "expected_match": True
        },
        {
            "name": "LG AC - Title match with price on packaging",
            "title": "LG Inverter AC 1.5 Ton",
            "ocr_text": "LG Inverter 1.5 Ton 18000 BTU",
            "has_price": True,  # Price on packaging
            "expected": "NOT PROMOTIONAL",  # Title match overrides price
            "expected_match": True
        },
        {
            "name": "iPhone - NO title provided, has price",
            "title": None,  # No title provided
            "ocr_text": "iPhone 15 Pro Price: 99,999 tk",
            "has_price": True,
            "expected": "PROMOTIONAL",
            "expected_match": False
        },
        {
            "name": "Random ad - Title doesn't match",
            "title": "Samsung Phone",
            "ocr_text": "Buy iPhone 15 Pro Call: 01712345678",
            "has_price": True,
            "expected": "PROMOTIONAL",  # No match, different product
            "expected_match": False
        },
        {
            "name": "Laptop - Title match but promotional context",
            "title": "Dell Laptop",
            "ocr_text": "Dell Laptop SALE 50% OFF Call Now 01712345678",
            "has_price": False,
            "expected": "NOT PROMOTIONAL",  # Title match = product mention, not ad
            "expected_match": True
        },
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        # Simulate title matching logic
        title = test.get("title")
        ocr_text = test["ocr_text"].lower()
        has_price = test["has_price"]
        
        is_title_match = False
        if title:
            title_lower = title.lower().strip()
            title_words = [w for w in title_lower.split() if len(w) > 1]  # Filter short words
            if len(title_words) > 0:
                # Count words that match (fuzzy matching)
                matched_words = sum(1 for word in title_words if word in ocr_text)
                match_ratio = matched_words / len(title_words)
                is_title_match = match_ratio >= 0.6
        
        # Promotional detection with title priority
        promotional_detected = False
        promo_confidence = 0.0
        
        if is_title_match:
            # Title matches = text is product name, NOT promotional
            promotional_detected = False
            promo_confidence = 0.0
        elif has_price:
            # No title match + price = promotional
            promotional_detected = True
            promo_confidence = 0.98
        
        result = "PROMOTIONAL" if promotional_detected else "NOT PROMOTIONAL"
        status = "✓" if result == test["expected"] else "✗"
        match_status = "✓" if is_title_match == test["expected_match"] else "✗"
        
        if result == test["expected"] and is_title_match == test["expected_match"]:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} {test['name']}")
        print(f"  Title: {title or '(none)'}")
        print(f"  OCR Text: {test['ocr_text']}")
        print(f"  Title Match: {is_title_match} {match_status}")
        if title:
            title_words = [w for w in title.lower().split() if len(w) > 1]
            matched = [w for w in title_words if w in ocr_text]
            if len(title_words) > 0:
                print(f"  Matched words: {matched} ({len(matched)}/{len(title_words)})")
        print(f"  Promotional: {promotional_detected} (confidence: {promo_confidence})")
        print(f"  Expected: {test['expected']}, Got: {result}")
        print()
    
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    print("\nKEY INSIGHTS:")
    print("✓ Title match (≥60% words) = NOT PROMOTIONAL (confidence: 0.0)")
    print("✓ Works even if image has price on packaging")
    print("✓ Prevents false positives when product name appears in image")
    print("✓ Falls back to other detection if title doesn't match")
    print("\nUSAGE:")
    print('  POST /check with: {"image": "...", "title": "Dell Inspiron 15"}')

if __name__ == "__main__":
    test_product_title_matching()
