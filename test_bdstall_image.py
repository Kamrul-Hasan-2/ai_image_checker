"""Test the specific image that's being incorrectly flagged"""
import requests
from PIL import Image
from io import BytesIO
from ocr_service import OCRService

# Initialize service
ocr_service = OCRService()

test_url = "https://cdn.bdstall.com/product-image/420663_600X600.webp"

print(f"\n{'='*80}")
print(f"Testing: {test_url}")
print('='*80)

try:
    response = requests.get(test_url, timeout=10)
    image = Image.open(BytesIO(response.content))
    
    print(f"Image size: {image.size}")
    
    # Run OCR
    result = ocr_service.extract_text(image)
    
    print(f"\n📝 Text found: {result['text_found']}")
    print(f"Text count: {result['text_count']}")
    print(f"Full text: '{result['full_text']}'")
    
    if result['extracted_data']:
        print(f"\n📄 All detected text:")
        for item in result['extracted_data']:
            print(f"  - '{item['text']}' (confidence: {item['confidence']:.2f})")
    
    print(f"\n{'='*40}")
    print("PRODUCT TEXT ANALYSIS:")
    print('='*40)
    print(f"Is product text only: {result.get('is_product_text_only', False)}")
    
    print(f"\n{'='*40}")
    print("PROMOTIONAL DETECTION:")
    print('='*40)
    print(f"❌ Promotional detected: {result['promotional_detected']}")
    print(f"Promotional confidence: {result['promotional_confidence']:.3f}")
    print(f"Promo keyword count: {result['promo_keyword_count']}")
    
    print(f"\n📊 Detailed Flags:")
    print(f"  Has phone: {result['has_phone_number']}")
    print(f"  Has price: {result['has_price']}")
    print(f"  Has link: {result['has_link']}")
    print(f"  Has e-commerce UI: {result['has_ecommerce_ui']}")
    print(f"  Seller branding: {result['seller_branding_detected']}")
    print(f"  Strong price indicator: {result['strong_price_indicator']}")
    print(f"  Visual promo score: {result['visual_promo_score']:.2f}")
    print(f"  Has button UI: {result['has_button_ui']}")
    print(f"  Digit count: {result['digit_count']}")
    
    print(f"\n🎯 VERDICT:")
    if result['promotional_detected']:
        print("  ❌❌❌ INCORRECTLY FLAGGED AS PROMOTIONAL")
        print(f"\n  Why flagged:")
        if result['has_phone_number']:
            print("    - Phone number detected")
        if result['has_price']:
            print("    - Price detected")
        if result['has_link']:
            print("    - Link detected")
        if result['has_ecommerce_ui']:
            print("    - E-commerce UI detected")
        if result['strong_price_indicator']:
            print("    - Strong price indicators (digits/currency)")
    else:
        print("  ✅ Correctly identified as NOT promotional")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
