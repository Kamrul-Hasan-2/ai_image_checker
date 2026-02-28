"""
Debug script to test image detection on a specific image
"""
import sys
import os
from PIL import Image

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Import services
from quality_service import QualityCheckService
from ocr_service import OCRService
from clip_service import CLIPService

def test_image(image_path):
    """Test image detection"""
    print("\n" + "="*80)
    print("DEBUG: Testing Image Detection")
    print("="*80)
    
    # Load image
    image = Image.open(image_path).convert('RGB')
    print(f"\n✅ Image loaded: {image.size}")
    
    # Initialize services
    print("\n📦 Initializing services...")
    ocr_service = OCRService(languages=['en'])
    clip_service = CLIPService(model_name="openai/clip-vit-base-patch32")
    print("✅ Services initialized\n")
    
    # Resize for processing
    max_size = 800
    if max(image.size) > max_size:
        ratio = max_size / max(image.size)
        new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
        image = image.resize(new_size, Image.Resampling.LANCZOS)
        print(f"✅ Image resized to: {image.size}\n")
    
    # Run OCR
    print("🔍 Running OCR analysis...")
    print("-" * 80)
    ocr_result = ocr_service.extract_text(image)
    
    print("\n📝 OCR RESULTS:")
    print("-" * 80)
    print(f"Full text: {ocr_result.get('full_text', '')}")
    print(f"\nExtracted data:")
    for item in ocr_result.get('extracted_data', []):
        print(f"  - {item['text']} (confidence: {item['confidence']:.2f})")
    
    print(f"\n🚨 PROMOTIONAL DETECTION:")
    print("-" * 80)
    print(f"  Has price: {ocr_result.get('has_price', False)}")
    print(f"  Has phone number: {ocr_result.get('has_phone_number', False)}")
    print(f"  Has link: {ocr_result.get('has_link', False)}")
    print(f"  Has e-commerce UI: {ocr_result.get('has_ecommerce_ui', False)}")
    print(f"  Has button UI: {ocr_result.get('has_button_ui', False)}")
    print(f"  Has business name: {ocr_result.get('has_business_name', False)}")
    print(f"  Has promotional sticker: {ocr_result.get('has_promotional_sticker', False)}")
    print(f"  Promotional detected: {ocr_result.get('promotional_detected', False)}")
    print(f"  Promotional confidence: {ocr_result.get('promotional_confidence', 0.0):.2f}")
    print(f"  Is product text only: {ocr_result.get('is_product_text_only', False)}")
    
    print(f"\n💧 WATERMARK DETECTION:")
    print("-" * 80)
    print(f"  Watermark confidence: {ocr_result.get('watermark_confidence', 0.0):.2f}")
    print(f"  BD marketplace watermark: {ocr_result.get('bd_marketplace_watermark', False)}")
    
    print(f"\n📊 OTHER METRICS:")
    print("-" * 80)
    print(f"  Digit count: {ocr_result.get('digit_count', 0)}")
    print(f"  Strong price indicator: {ocr_result.get('strong_price_indicator', False)}")
    print(f"  Visual promo score: {ocr_result.get('visual_promo_score', 0.0):.2f}")
    
    # Run CLIP product detection
    print(f"\n🎯 CLIP PRODUCT DETECTION:")
    print("-" * 80)
    product_check = clip_service.detect_product_photo(image)
    print(f"  Is product photo: {product_check.get('is_product_photo', False)}")
    print(f"  Product score: {product_check.get('product_score', 0.0):.2f}")
    print(f"  Top labels: {product_check.get('top_labels', [])}")
    
    print("\n" + "="*80)
    print("DEBUG COMPLETE")
    print("="*80 + "\n")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_image_debug.py <image_path>")
        sys.exit(1)
    
    image_path = sys.argv[1]
    if not os.path.exists(image_path):
        print(f"Error: Image file not found: {image_path}")
        sys.exit(1)
    
    test_image(image_path)
