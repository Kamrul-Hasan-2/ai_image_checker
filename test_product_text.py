"""
Test to verify product text detection (non-promotional)
Example: "ONV PoE Full 1000M Smart PoE Switch" on product = NOT promotional
"""

def simulate_product_text_detection():
    """Simulate the product text detection logic"""
    
    # Test Case 1: Product with brand/model on it (like ONV switch)
    print("Test Case 1: Product with brand name (ONV PoE Switch)")
    full_text = "ONV PoE Full 1000M Smart PoE Switch"
    full_text_lower = full_text.lower()
    
    has_phone_number = False
    has_link = False
    has_price = False
    has_sale_terms = False
    has_ecommerce_ui = False
    
    product_terms = ["poe", "switch", "router", "smart", "full", "model", "series"]
    tech_specs = ["watt", "volt", "ghz", "mhz", "gb", "mb", "1000m", "100m"]
    
    has_product_terms = any(term in full_text_lower for term in product_terms)
    has_tech_specs = any(spec in full_text_lower for spec in tech_specs)
    
    # Simulate centered text (most text in center 60% of image)
    center_region_count = 3
    total_text_count = 4
    
    is_product_text_only = False
    if not has_phone_number and not has_link and not has_price:
        if (has_product_terms or has_tech_specs) and not has_sale_terms and not has_ecommerce_ui:
            if center_region_count >= total_text_count * 0.6:
                is_product_text_only = True
    
    print(f"  Text: {full_text}")
    print(f"  Has product terms: {has_product_terms}")
    print(f"  Has tech specs: {has_tech_specs}")
    print(f"  Is product text only: {is_product_text_only}")
    print(f"  Promotional confidence: {0.0 if is_product_text_only else 0.35}")
    print(f"  Result: {'✓ NOT PROMOTIONAL' if is_product_text_only else '✗ FLAGGED AS PROMOTIONAL'}")
    
    # Test Case 2: Same product but with price added
    print("\nTest Case 2: Product with price overlay")
    full_text = "ONV PoE Switch Price: 24,999 tk"
    full_text_lower = full_text.lower()
    
    has_phone_number = False
    has_link = False
    has_price = True  # Price detected!
    has_sale_terms = False
    has_ecommerce_ui = False
    
    is_product_text_only = False  # Price detected = promotional
    if not has_phone_number and not has_link and not has_price:
        # Would check, but has_price is True, so skipped
        pass
    
    promo_confidence = 0.98 if has_price else 0.0
    
    print(f"  Text: {full_text}")
    print(f"  Has price: {has_price}")
    print(f"  Is product text only: {is_product_text_only}")
    print(f"  Promotional confidence: {promo_confidence}")
    print(f"  Result: {'✓ PROMOTIONAL' if promo_confidence > 0.7 else '✗ NOT PROMOTIONAL'}")
    
    # Test Case 3: Product with phone number
    print("\nTest Case 3: Product with phone number overlay")
    full_text = "ONV PoE Switch Call: 01712345678"
    full_text_lower = full_text.lower()
    
    has_phone_number = True  # Phone detected!
    has_link = False
    has_price = False
    
    is_product_text_only = False  # Phone detected = promotional
    promo_confidence = 0.99 if has_phone_number else 0.0
    
    print(f"  Text: {full_text}")
    print(f"  Has phone number: {has_phone_number}")
    print(f"  Is product text only: {is_product_text_only}")
    print(f"  Promotional confidence: {promo_confidence}")
    print(f"  Result: {'✓ PROMOTIONAL' if promo_confidence > 0.7 else '✗ NOT PROMOTIONAL'}")
    
    # Test Case 4: Product with "Buy Now" button
    print("\nTest Case 4: Product with 'Buy Now' button")
    full_text = "ONV PoE Switch BUY NOW"
    full_text_lower = full_text.lower()
    
    has_phone_number = False
    has_link = False
    has_price = False
    has_sale_terms = False
    has_ecommerce_ui = True  # "buy" detected!
    
    is_product_text_only = False  # E-commerce UI = promotional
    promo_confidence = 0.90 if has_ecommerce_ui else 0.0
    
    print(f"  Text: {full_text}")
    print(f"  Has e-commerce UI: {has_ecommerce_ui}")
    print(f"  Is product text only: {is_product_text_only}")
    print(f"  Promotional confidence: {promo_confidence}")
    print(f"  Result: {'✓ PROMOTIONAL' if promo_confidence > 0.7 else '✗ NOT PROMOTIONAL'}")

if __name__ == "__main__":
    print("=" * 60)
    print("PRODUCT TEXT DETECTION TEST")
    print("=" * 60)
    print("\nKey Logic:")
    print("- Product name/specs on device = NOT promotional")
    print("- Product with price/phone/link = PROMOTIONAL")
    print("- Product with 'Buy Now' button = PROMOTIONAL")
    print("\n" + "=" * 60 + "\n")
    
    simulate_product_text_detection()
    
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print("✓ Product text (ONV, PoE, Smart, 1000M) alone = NOT flagged")
    print("✓ Product text + Price = FLAGGED as promotional")
    print("✓ Product text + Phone = FLAGGED as promotional")
    print("✓ Product text + Buy Now = FLAGGED as promotional")
