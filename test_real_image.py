"""
Test the actual image from Postman request
"""

import requests
from PIL import Image
from io import BytesIO
from quality_service import QualityCheckService

# Initialize service
quality_service = QualityCheckService()

# Actual image URL from Postman
image_url = "https://cdn.bdstall.com/product-image/420065_600X600.webp"

print(f"Downloading image from: {image_url}")
try:
    response = requests.get(image_url, timeout=10)
    response.raise_for_status()
    image = Image.open(BytesIO(response.content))
    
    print(f"✅ Image loaded successfully")
    print(f"Size: {image.size}")
    print(f"Mode: {image.mode}")
    print(f"Format: {image.format}")
    
except Exception as e:
    print(f"❌ Error loading image: {e}")
    exit(1)

print("\n" + "="*70)
print("RUNNING QUALITY CHECK ON ACTUAL IMAGE")
print("="*70 + "\n")

# Run quality check
result = quality_service.check_image(image)

print(f"Overall Result: {'PASS ✅' if result['passed'] else 'FAIL ❌'}")
print(f"Action: {result['action']}")
print(f"Reason: {result['reason']}")

blur_check = result['checks']['blur']
print(f"\n{'='*70}")
print(f"BLUR/NOISE CHECK: {'PASSED ✅' if blur_check['passed'] else 'FAILED ❌'}")
print(f"{'='*70}")
print(f"Reason: {blur_check['reason']}")
print(f"Confidence: {blur_check['confidence']:.3f}")

details = blur_check['details']
print(f"\nCombined Score: {details['combined_score']:.2f}/100")
print(f"  Threshold: <65 = REJECT")
print(f"Hard Reject: {details.get('hard_reject', False)}")
print(f"Quality Grade: {details['quality_grade'].upper()}")

print(f"\n{'='*70}")
print("SHARPNESS METRICS (Higher = Sharper)")
print(f"{'='*70}")
print(f"Laplacian Variance: {details['laplacian_var']:.2f}")
print(f"  Ranges: <60=extreme | <150=severe | <250=moderate | 250+=good")
print(f"Laplacian Mean: {details['laplacian_mean']:.2f}")
print(f"Tenengrad: {details['tenengrad_score']:.2f}")
print(f"Gradient Std: {details['gradient_std']:.2f}")
print(f"Detail Loss: {details['detail_loss']:.2f} (<1.2=severe | <2.5=moderate)")
print(f"Wavelet Energy: {details['wavelet_energy']:.2f} (<5=severe | <8=moderate)")
print(f"Edge Density: {details['edge_density']:.4f} (<0.03=low | <0.06=moderate)")
print(f"High Freq Energy: {details['high_freq_energy']:.2f}")

print(f"\n{'='*70}")
print("NOISE METRICS (Higher = More Noise)")
print(f"{'='*70}")
print(f"Noise Score: {details['noise_score']:.2f}")
print(f"  Ranges: >120=moderate | >150=high | >200=severe")
print(f"High Freq Noise: {details['high_freq_noise']:.2f}")
print(f"  Ranges: >6=moderate | >8=high | >10=severe")
print(f"SNR: {details['snr']:.2f}")
print(f"  Ranges: <3=extreme | <8=bad | <10=poor | 10+=good")
print(f"Texture Consistency: {details['texture_consistency']:.2f}")
print(f"Contrast: {details['contrast']:.2f}")
print(f"Is Noisy: {details.get('is_noisy', False)}")
print(f"Is Motion Blurred: {details.get('is_motion_blurred', False)}")

print(f"\n{'='*70}")
print("PENALTIES APPLIED")
print(f"{'='*70}")
penalties = details.get('penalties', {})
for key, value in penalties.items():
    if value > 0:
        print(f"{key.replace('_', ' ').title()}: -{value}")
print(f"{'─'*70}")
print(f"TOTAL PENALTY: -{sum(penalties.values())} points")

print(f"\n{'='*70}")
if not blur_check['passed']:
    print(f"FINAL: ❌ REJECTED - Blur/noise detected correctly!")
else:
    print(f"FINAL: ✅ PASSED - Image quality acceptable")
    print(f"\n⚠️ If this image looks blurry/noisy to you, thresholds need adjustment")
print(f"{'='*70}")
