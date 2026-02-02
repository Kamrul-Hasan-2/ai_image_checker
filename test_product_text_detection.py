"""Test product text vs promotional text detection"""
import requests
from PIL import Image
from io import BytesIO
from ocr_service import OCRService

# Initialize service
ocr_service = OCRService()

test_images = [
    ("Tool Kit with INSULATING text", "https://i5.walmartimages.com/seo/CARTMAN-Tool-Kit-39-Piece-Tool-Set-with-Plastic-Toolbox-Storage-Case-Socket-and-Bit-Set_eb5e5c6e-9e0a-4e1f-8e5e-5c5c5e5e5c5e.jpg"),
    ("Camera with Canon branding", "https://cdn.bdstall.com/product-image/398608_600X600.jpg"),
]

for name, img_url in test_images:
    print(f"\n{'='*80}")
    print(f"Testing: {name}")
    print(f"URL: {img_url}")
    print('='*80)
    
    try:
        response = requests.get(img_url, timeout=10)
        image = Image.open(BytesIO(response.content))
        
        print(f"Image size: {image.size}")
        
        # Run OCR
        result = ocr_service.extract_text(image)
        
        print(f"\n📝 Text found: {result['text_found']}")
        print(f"Full text: {result['full_text']}")
        
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
        
        print(f"\n📊 Indicators:")
        print(f"  Has phone: {result['has_phone_number']}")
        print(f"  Has price: {result['has_price']}")
        print(f"  Has link: {result['has_link']}")
        print(f"  Has e-commerce UI: {result['has_ecommerce_ui']}")
        print(f"  Seller branding: {result['seller_branding_detected']}")
        
        print(f"\n🎯 VERDICT:")
        if result.get('is_product_text_only'):
            print("  ✅ Text is PART OF THE PRODUCT (not promotional)")
        elif result['promotional_detected']:
            print("  ❌ PROMOTIONAL TEXT DETECTED (overlay/added text)")
        else:
            print("  ✅ No promotional text")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
