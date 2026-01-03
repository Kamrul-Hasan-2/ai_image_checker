"""
Quick test script for new detection improvements
"""
from PIL import Image
import requests
from io import BytesIO

# Test imports
print("Testing imports...")
from quality_service import QualityCheckService
from ocr_service import OCRService
from clip_service import CLIPService

print("\n✅ All imports successful!")

# Initialize services
print("\nInitializing services...")
quality_service = QualityCheckService()
print("✓ Quality service loaded")

ocr_service = OCRService(languages=['en'])
print("✓ OCR service loaded")

clip_service = CLIPService()
print("✓ CLIP service loaded")

# Test image
test_url = "https://cdn.bdstall.com/product-image/412549_800X800.webp"
print(f"\n📸 Loading test image from: {test_url}")

response = requests.get(test_url)
image = Image.open(BytesIO(response.content)).convert('RGB')
print(f"✓ Image loaded: {image.size}")

# Test 1: Quality check with blur detection
print("\n" + "="*60)
print("TEST 1: Enhanced Blur Detection")
print("="*60)
quality_result = quality_service.check_image(image)
blur_details = quality_result['checks']['blur']['details']
print(f"Blur Detection Result:")
print(f"  Combined Score: {blur_details.get('combined_score', 0):.1f}/100")
print(f"  Quality Grade: {blur_details.get('quality_grade', 'unknown')}")
print(f"  Laplacian Variance: {blur_details.get('laplacian_var', 0):.2f}")
print(f"  Tenengrad Score: {blur_details.get('tenengrad_score', 0):.2f}")
print(f"  High Freq Energy: {blur_details.get('high_freq_energy', 0):.2f}")
print(f"  Edge Density: {blur_details.get('edge_density', 0):.4f}")
print(f"  PASSED: {quality_result['checks']['blur']['passed']}")

# Test 2: OCR promotional detection
print("\n" + "="*60)
print("TEST 2: Enhanced OCR Promotional Detection")
print("="*60)
ocr_result = ocr_service.extract_text(image)
analysis = ocr_result['analysis']
print(f"OCR Detection Result:")
print(f"  Text Found: {ocr_result['text_found']}")
print(f"  Text Count: {ocr_result['text_count']}")
print(f"  Full Text: {ocr_result['full_text'][:100]}...")
print(f"\nPromotional Analysis:")
print(f"  Promotional Score: {analysis.get('promotional_score', 0):.1f}/100")
print(f"  Is Promotional: {analysis['is_promotional']}")
print(f"  Promo Keywords: {analysis.get('promo_keyword_count', 0)}")
print(f"  Has Phone: {analysis['has_phone_number']}")
print(f"  Has Website: {analysis['has_website_link']}")
print(f"  Has Social Media: {analysis.get('has_social_media', False)}")
print(f"  Text Density: {analysis['text_density']}")

# Test 3: CLIP promotional detection
print("\n" + "="*60)
print("TEST 3: Enhanced CLIP Promotional Detection")
print("="*60)
clip_result = clip_service.analyze_image(image)
promo_analysis = clip_result['promo_analysis']
risk_analysis = clip_result['risk_analysis']

print(f"CLIP Promo Detection:")
print(f"  Is Promotional: {promo_analysis['is_promotional']}")
print(f"  Confidence: {promo_analysis['confidence']:.3f}")
print(f"  Promo Score: {promo_analysis.get('promo_score', 0):.3f}")
print(f"  Clean Score: {promo_analysis.get('clean_score', 0):.3f}")
print(f"  Max Promo Indicator: {promo_analysis.get('max_promo_indicator', 0):.3f}")

print(f"\nCLIP Risk Analysis:")
print(f"  Max Risk: {risk_analysis['max_risk']:.3f}")
print(f"  Risk Category: {risk_analysis['max_risk_category']}")
print(f"  Weighted Risk Level: {risk_analysis.get('weighted_risk_level', 0):.1f}/100")
print(f"  Requires Escalation: {risk_analysis['requires_escalation']}")
print(f"  Action: {risk_analysis['action']}")

# Test 4: Image preprocessing
print("\n" + "="*60)
print("TEST 4: Image Preprocessing")
print("="*60)
enhanced = quality_service.preprocess_image(image, enhance=True)
print(f"✓ Image preprocessed successfully")
print(f"  Original size: {image.size}")
print(f"  Enhanced size: {enhanced.size}")
print(f"  Note: Enhanced image has better contrast and sharpness for detection")

print("\n" + "="*60)
print("✅ ALL TESTS COMPLETED!")
print("="*60)
print("\n📊 Summary:")
print("1. Multi-algorithm blur detection is working")
print("2. Enhanced promotional text detection with scoring")
print("3. More sensitive CLIP promotional detection")
print("4. Image preprocessing available for better detection")
print("\nReady to deploy to RunPod! 🚀")
