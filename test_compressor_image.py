"""
Test to analyze the noisy compressor image and find why it's not being rejected
"""

from PIL import Image
import numpy as np
from quality_service import QualityCheckService

# Initialize service
quality_service = QualityCheckService()

# Create a test image that simulates the noisy compressor characteristics
# Based on visual inspection: visible grain, moderate sharpness, low detail
print("Creating test image similar to noisy compressor...")

# Compressor-like image: some structure but with significant noise
img_array = np.zeros((600, 600, 3), dtype=np.uint8)

# Add blue background
img_array[:, :] = [30, 100, 180]

# Add some structure (mesh pattern)
for i in range(0, 600, 20):
    img_array[i:i+2, :] = [10, 50, 100]
for j in range(0, 600, 20):
    img_array[:, j:j+2] = [10, 50, 100]

# Add moderate noise to simulate grain
noise = np.random.normal(0, 25, (600, 600, 3))
img_array = np.clip(img_array.astype(np.float32) + noise, 0, 255).astype(np.uint8)

image = Image.fromarray(img_array)

print(f"Image size: {image.size}\n")
print("="*70)
print("TESTING NOISY COMPRESSOR-LIKE IMAGE")
print("="*70)

# Run quality check
result = quality_service.check_image(image)

blur_check = result['checks']['blur']
details = blur_check['details']

print(f"\nResult: {'PASS ✅' if blur_check['passed'] else 'FAIL ❌'}")
print(f"Reason: {blur_check['reason']}")
print(f"Combined Score: {details['combined_score']:.2f}/100 (threshold: <70 = REJECT)")
print(f"Hard Reject: {details.get('hard_reject', False)}")

print(f"\n{'='*70}")
print("DETAILED METRICS")
print(f"{'='*70}")
print(f"Laplacian: {details['laplacian_var']:.2f} (need: <80=extreme, <200=severe, <350=moderate)")
print(f"Detail Loss: {details['detail_loss']:.2f} (need: <0.8=extreme, <1.5=severe, <2.5=moderate)")
print(f"Wavelet Energy: {details['wavelet_energy']:.2f} (need: <8=severe)")
print(f"Edge Density: {details['edge_density']:.4f} (need: <0.025=severe)")
print(f"\nNoise Score: {details['noise_score']:.2f} (need: >100=detected, >130=high)")
print(f"High Freq Noise: {details['high_freq_noise']:.2f} (need: >5=detected, >7=high)")
print(f"SNR: {details['snr']:.2f} (need: <10=bad)")
print(f"Is Noisy: {details.get('is_noisy', False)}")

print(f"\n{'='*70}")
print("PENALTIES APPLIED")
print(f"{'='*70}")
penalties = details.get('penalties', {})
for key, value in penalties.items():
    if value > 0:
        print(f"{key.title().replace('_', ' ')}: -{value}")
total = sum(penalties.values())
print(f"{'─'*70}")
print(f"TOTAL: -{total}")

print(f"\n{'='*70}")
if not blur_check['passed']:
    print("✅ SUCCESS: Correctly detected as poor quality!")
else:
    print("❌ PROBLEM: Image passed but should be rejected!")
    print("\nDIAGNOSIS:")
    
    # Check what's preventing rejection
    issues = []
    if details['laplacian_var'] >= 350:
        issues.append(f"Laplacian too high ({details['laplacian_var']:.0f}) - not triggering blur penalty")
    if details['noise_score'] < 100:
        issues.append(f"Noise score too low ({details['noise_score']:.0f}) - not detected as noisy")
    if details['snr'] >= 10:
        issues.append(f"SNR too good ({details['snr']:.1f}) - not triggering poor signal penalty")
    if details['combined_score'] >= 70:
        issues.append(f"Score too high ({details['combined_score']:.0f}) - above rejection threshold")
    if not details.get('hard_reject'):
        issues.append("No hard rejection criteria triggered")
    
    for issue in issues:
        print(f"  • {issue}")
        
    print(f"\nRECOMMENDATION: Need to adjust thresholds to catch this image type")
print(f"{'='*70}")
