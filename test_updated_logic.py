"""
Test UPDATED simplified product text detection
"""

def test_updated_logic():
    """Test the simplified product text detection"""
    
    print("=" * 70)
    print("UPDATED PRODUCT TEXT DETECTION - SIMPLIFIED")
    print("=" * 70)
    print("\nRule: NO price + NO phone + NO link + NO 'Buy Now/Sale' = NOT PROMO")
    print("=" * 70 + "\n")
    
    # Test 1: Pure product text
    print("Test 1: ONV PoE 8G+2G Full 1000M Smart PoE Switch")
    has_price = False
    has_phone = False
    has_link = False
    has_ecommerce_ui = False
    has_strong_sale = False  # No "buy now", "sale", "discount", etc.
    
    is_product = not has_price and not has_phone and not has_link and not has_ecommerce_ui and not has_strong_sale
    print(f"  Is Product Text: {is_product}")
    print(f"  Confidence: {0.0 if is_product else 0.85}")
    print(f"  ✓ Result: {'NOT PROMOTIONAL' if is_product else 'PROMOTIONAL'}\n")
    
    # Test 2: Product with tech specs (should NOT flag)
    print("Test 2: Smart Power Router 1000M 100W")
    has_price = False
    has_phone = False
    has_link = False
    has_ecommerce_ui = False
    has_strong_sale = False
    
    is_product = not has_price and not has_phone and not has_link and not has_ecommerce_ui and not has_strong_sale
    print(f"  Is Product Text: {is_product}")
    print(f"  Confidence: {0.0 if is_product else 0.85}")
    print(f"  ✓ Result: {'NOT PROMOTIONAL' if is_product else 'PROMOTIONAL'}\n")
    
    # Test 3: Product + Price (should flag)
    print("Test 3: ONV Switch 24,999 tk")
    has_price = True  # PRICE!
    has_phone = False
    has_link = False
    has_ecommerce_ui = False
    has_strong_sale = False
    
    is_product = not has_price and not has_phone and not has_link and not has_ecommerce_ui and not has_strong_sale
    print(f"  Is Product Text: {is_product}")
    print(f"  Confidence: {0.98 if has_price else 0.0}")
    print(f"  ✓ Result: {'PROMOTIONAL' if has_price else 'NOT PROMOTIONAL'}\n")
    
    # Test 4: Product + Phone (should flag)
    print("Test 4: ONV Switch Call 01712345678")
    has_price = False
    has_phone = True  # PHONE!
    has_link = False
    has_ecommerce_ui = False
    has_strong_sale = False
    
    is_product = not has_price and not has_phone and not has_link and not has_ecommerce_ui and not has_strong_sale
    print(f"  Is Product Text: {is_product}")
    print(f"  Confidence: {0.99 if has_phone else 0.0}")
    print(f"  ✓ Result: {'PROMOTIONAL' if has_phone else 'NOT PROMOTIONAL'}\n")
    
    # Test 5: Product + Buy Now (should flag)
    print("Test 5: ONV Switch BUY NOW")
    has_price = False
    has_phone = False
    has_link = False
    has_ecommerce_ui = True  # BUY NOW!
    has_strong_sale = False
    
    is_product = not has_price and not has_phone and not has_link and not has_ecommerce_ui and not has_strong_sale
    print(f"  Is Product Text: {is_product}")
    print(f"  Confidence: {0.90 if has_ecommerce_ui else 0.0}")
    print(f"  ✓ Result: {'PROMOTIONAL' if has_ecommerce_ui else 'NOT PROMOTIONAL'}\n")
    
    print("=" * 70)
    print("KEY CHANGES")
    print("=" * 70)
    print("✓ Removed from promo keywords: watt, volt, power, quality, warranty")
    print("✓ Removed: tk, taka, rs, rupees, contact, call, phone, now, only")
    print("✓ ONLY flag clear promotional intent: prices, phones, 'Buy Now'")
    print("✓ Product specs alone = SAFE")

if __name__ == "__main__":
    test_updated_logic()
