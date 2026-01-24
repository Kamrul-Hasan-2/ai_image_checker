"""
Test to verify product branding/logos are NOT flagged as promotional
"""

def test_product_branding():
    """Test that product names/logos on products are NOT promotional"""
    
    print("=" * 70)
    print("PRODUCT BRANDING TEST - ENHANCED WITH VISUAL DETECTION")
    print("=" * 70)
    print("\nRule 1: If image shows actual product → text is NOT promotional")
    print("Rule 2: Product text without price/phone/link → NOT promotional")
    print("Rule 3: Product + price/phone/link → PROMOTIONAL")
    print("=" * 70 + "\n")
    
    test_cases = [
        {
            "name": "iPhone with Apple logo",
            "text": "iPhone Apple",
            "has_price": False,
            "has_phone": False,
            "has_link": False,
            "has_ecommerce_ui": False,
            "is_product_photo": False,  # Assume visual detection not run
            "expected": "NOT PROMOTIONAL"
        },
        {
            "name": "Security Camera in packaging (THIS IMAGE)",
            "text": "Imou 3K 5MP Cruiser SC",
            "has_price": False,
            "has_phone": False,
            "has_link": False,
            "has_ecommerce_ui": False,
            "is_product_photo": True,  # Visual detection confirms product photo
            "expected": "NOT PROMOTIONAL"
        },
        {
            "name": "Samsung phone with Samsung text",
            "text": "Samsung Galaxy A54",
            "has_price": False,
            "has_phone": False,
            "has_link": False,
            "has_ecommerce_ui": False,
            "is_product_photo": False,
            "expected": "NOT PROMOTIONAL"
        },
        {
            "name": "ONV switch with brand name",
            "text": "ONV PoE 8G+2G Full 1000M Smart PoE Switch",
            "has_price": False,
            "has_phone": False,
            "has_link": False,
            "has_ecommerce_ui": False,
            "is_product_photo": False,
            "expected": "NOT PROMOTIONAL"
        },
        {
            "name": "LG inverter with specs",
            "text": "LG Inverter 1.5 Ton 18000 BTU",
            "has_price": False,
            "has_phone": False,
            "has_link": False,
            "has_ecommerce_ui": False,
            "is_product_photo": False,
            "expected": "NOT PROMOTIONAL"
        },
        {
            "name": "Router with tech specs",
            "text": "Smart Router 1000M WiFi 6",
            "has_price": False,
            "has_phone": False,
            "has_link": False,
            "has_ecommerce_ui": False,
            "is_product_photo": False,
            "expected": "NOT PROMOTIONAL"
        },
        {
            "name": "Product photo WITH price (still product photo)",
            "text": "iPhone 15 Pro 99,999 tk",
            "has_price": True,
            "has_phone": False,
            "has_link": False,
            "has_ecommerce_ui": False,
            "is_product_photo": True,  # Visual confirms it's product photo
            "expected": "NOT PROMOTIONAL"  # Price on product packaging = OK
        },
        {
            "name": "iPhone + Price (NOT product photo)",
            "text": "iPhone 15 Pro Price: 99,999 tk",
            "has_price": True,
            "has_phone": False,
            "has_link": False,
            "has_ecommerce_ui": False,
            "is_product_photo": False,
            "expected": "PROMOTIONAL"
        },
        {
            "name": "Samsung + Phone number",
            "text": "Samsung Galaxy Call: 01712345678",
            "has_price": False,
            "has_phone": True,
            "has_link": False,
            "has_ecommerce_ui": False,
            "is_product_photo": False,
            "expected": "PROMOTIONAL"
        },
        {
            "name": "Product + Buy Now",
            "text": "Smart Router BUY NOW",
            "has_price": False,
            "has_phone": False,
            "has_link": False,
            "has_ecommerce_ui": True,
            "is_product_photo": False,
            "expected": "PROMOTIONAL"
        },
    ]
    
    passed = 0
    failed = 0
    
    for test in test_cases:
        # Simulate the logic
        has_price = test["has_price"]
        has_phone = test["has_phone"]
        has_link = test["has_link"]
        has_ecommerce_ui = test["has_ecommerce_ui"]
        is_product_photo = test.get("is_product_photo", False)
        
        strong_sale_terms = ["buy now", "call now", "order now", "sale", "discount", "offer"]
        has_strong_sale = any(term in test["text"].lower() for term in strong_sale_terms)
        
        # Product text detection
        is_product_text_only = False
        if not has_phone and not has_link and not has_price and not has_ecommerce_ui:
            if not has_strong_sale:
                is_product_text_only = True
        
        # Promotional detection (ENHANCED WITH VISUAL DETECTION)
        promotional_detected = False
        promo_confidence = 0.0
        
        if is_product_photo:
            # CRITICAL: If visual detection confirms product photo, text is NOT promotional
            promotional_detected = False
            promo_confidence = 0.0
        elif is_product_text_only:
            # Product branding/text without sale indicators = NOT promotional
            promotional_detected = False
            promo_confidence = 0.0
        else:
            # Check for promotional signals
            promotional_detected = has_phone or has_link or has_price or has_ecommerce_ui
            
            if promotional_detected:
                if has_phone or has_link:
                    promo_confidence = 0.99
                elif has_price:
                    promo_confidence = 0.98
                elif has_ecommerce_ui:
                    promo_confidence = 0.90
        
        result = "PROMOTIONAL" if promotional_detected else "NOT PROMOTIONAL"
        status = "✓" if result == test["expected"] else "✗"
        
        if result == test["expected"]:
            passed += 1
        else:
            failed += 1
        
        print(f"{status} {test['name']}")
        print(f"  Text: {test['text']}")
        print(f"  Is product photo (visual): {is_product_photo}")
        print(f"  Is product text only: {is_product_text_only}")
        print(f"  Promotional detected: {promotional_detected}")
        print(f"  Confidence: {promo_confidence}")
        print(f"  Expected: {test['expected']}, Got: {result}")
        print()
    
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)
    print("\nKEY POINTS:")
    print("✓ Product photo (visual detection) = confidence 0.0 (SAFE)")
    print("✓ Product branding/logos = confidence 0.0 (SAFE)")
    print("✓ Even if product photo has price on packaging = SAFE")
    print("✓ Promotional banner + price/phone = confidence 0.98-0.99 (PROMOTIONAL)")

if __name__ == "__main__":
    test_product_branding()
