"""
Comprehensive test of the entire Modal handler flow
Tests the EXACT logic that runs in Modal
"""

import sys
sys.path.insert(0, "/root") if "/root" not in sys.path else None

import requests
from PIL import Image
from io import BytesIO
from quality_service import QualityCheckService

print("="*70)
print("COMPREHENSIVE MODAL FLOW TEST")
print("="*70)

# Initialize quality service
quality_service = QualityCheckService()

# Test image URL from your Postman request
image_url = "https://cdn.bdstall.com/product-image/420065_600X600.webp"

print(f"\n1. Loading image from: {image_url[:60]}...")
try:
    response = requests.get(image_url, timeout=10)
    response.raise_for_status()
    image = Image.open(BytesIO(response.content))
    print(f"   ✅ Image loaded: {image.size}, {image.mode}")
except Exception as e:
    print(f"   ❌ Error: {e}")
    exit(1)

print(f"\n2. Running quality check (BEFORE any resize)...")
quality_result = quality_service.check_image(image)

print(f"\n3. Extracting results from quality check...")
opencv_risk = quality_result.get("opencv_risk", 0.0)
screenshot_confidence = quality_result.get("screenshot_confidence", 0.0)
blur_confidence = quality_result.get("blur_confidence", 0.0)

print(f"   opencv_risk: {opencv_risk}")
print(f"   screenshot_confidence: {screenshot_confidence}")
print(f"   blur_confidence: {blur_confidence}")

print(f"\n4. Checking blur detection (Modal handler logic)...")
print(f"   quality_result['checks']['blur']['passed'] = {quality_result['checks']['blur']['passed']}")

# This is the EXACT logic in modal_handler.py line 204
blur_detected = not quality_result['checks']['blur']['passed']

print(f"   blur_detected = not quality_result['checks']['blur']['passed']")
print(f"   blur_detected = not {quality_result['checks']['blur']['passed']}")
print(f"   blur_detected = {blur_detected}")

print(f"\n5. API response value (Modal handler line 300)...")
blur_image_value = 5 if blur_detected else 0
print(f"   'blur_image': {blur_image_value}")

print(f"\n{'='*70}")
print("DETAILED BLUR CHECK RESULTS")
print(f"{'='*70}")

blur_check = quality_result['checks']['blur']
details = blur_check['details']

print(f"\nBlur Check Passed: {blur_check['passed']}")
print(f"Reason: {blur_check['reason']}")
print(f"Confidence: {blur_check['confidence']:.3f}")
print(f"\nCombined Score: {details['combined_score']:.2f}/100 (threshold: <60 = FAIL)")
print(f"Hard Reject: {details.get('hard_reject', False)}")
print(f"Quality Grade: {details['quality_grade']}")

print(f"\n{'='*70}")
print("KEY METRICS")
print(f"{'='*70}")
print(f"Laplacian Variance: {details['laplacian_var']:.2f}")
print(f"  (<80=extreme | <200=severe | <350=moderate)")
print(f"Detail Loss: {details['detail_loss']:.2f}")
print(f"  (<0.8=extreme | <1.5=severe | <2.5=moderate)")
print(f"Wavelet Energy: {details['wavelet_energy']:.2f}")
print(f"Edge Density: {details['edge_density']:.4f}")
print(f"\nNoise Score: {details['noise_score']:.2f}")
print(f"  (>100=detected | >130=high | >180=severe)")
print(f"High Freq Noise: {details['high_freq_noise']:.2f}")
print(f"  (>5=detected | >7=high | >9=severe)")
print(f"SNR: {details['snr']:.2f}")
print(f"  (<3=extreme | <10=bad | <12=fair)")
print(f"Is Noisy: {details.get('is_noisy', False)}")
print(f"Is Motion Blurred: {details.get('is_motion_blurred', False)}")

print(f"\n{'='*70}")
print("PENALTIES")
print(f"{'='*70}")
penalties = details.get('penalties', {})
for key, value in penalties.items():
    if value > 0:
        print(f"{key.replace('_', ' ').title()}: -{value}")
print(f"Total: -{sum(penalties.values())}")

print(f"\n{'='*70}")
print("FINAL VERDICT")
print(f"{'='*70}")
if blur_detected:
    print("❌ BLUR DETECTED - API will return 'blur_image': 5")
else:
    print("✅ NO BLUR - API will return 'blur_image': 0")
    
if not blur_check['passed']:
    print("✅ Quality check correctly identifies blur/poor quality")
else:
    print("⚠️ Quality check passed - image considered acceptable")
    
print(f"{'='*70}\n")
