"""Test the actual tool kit image from user"""
from PIL import Image
from ocr_service import OCRService
import sys

# Initialize service
ocr_service = OCRService()

# Test with the actual attached image
# You'll need to save the attached image and provide the path
image_path = input("Enter the path to the tool kit image: ").strip()

try:
    image = Image.open(image_path)
    print(f"\n{'='*80}")
    print(f"Testing Tool Kit Image")
    print(f"Image size: {image.size}")
    print('='*80)
    
    # Run OCR
    result = ocr_service.extract_text(image)
    
    print(f"\n📝 Text found: {result['text_found']}")
    print(f"Text count: {result['text_count']}")
    print(f"Full text: '{result['full_text']}'")
    
    if result['extracted_data']:
        print(f"\n📄 Detected text elements:")
        for item in result['extracted_data']:
            print(f"  - '{item['text']}' (confidence: {item['confidence']:.2f})")
    
    print(f"\n{'='*40}")
    print("PRODUCT TEXT ANALYSIS:")
    print('='*40)
    print(f"✅ Is product text only: {result.get('is_product_text_only', False)}")
    
    print(f"\n{'='*40}")
    print("PROMOTIONAL TEXT ANALYSIS:")
    print('='*40)
    print(f"❌ Promotional detected: {result['promotional_detected']}")
    print(f"Promotional confidence: {result['promotional_confidence']:.3f}")
    print(f"Promo keyword count: {result['promo_keyword_count']}")
    
    print(f"\n📊 Detailed Indicators:")
    print(f"  Has phone: {result['has_phone_number']}")
    print(f"  Has price: {result['has_price']}")
    print(f"  Has link: {result['has_link']}")
    print(f"  Has e-commerce UI: {result['has_ecommerce_ui']}")
    print(f"  Seller branding: {result['seller_branding_detected']}")
    print(f"  Visual promo score: {result['visual_promo_score']:.2f}")
    
    print(f"\n🎯 FINAL VERDICT:")
    if result.get('is_product_text_only'):
        print("  ✅✅✅ Text is PART OF THE PRODUCT BODY (not promotional)")
        print("  This is product branding/labeling - NOT overlay text")
    elif result['promotional_detected']:
        print("  ❌ PROMOTIONAL TEXT DETECTED (overlay/added text)")
    else:
        print("  ✅ No promotional text")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
