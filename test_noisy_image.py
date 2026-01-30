"""
Test script for noisy/grainy industrial compressor image
"""

from PIL import Image, ImageFilter
import numpy as np
from quality_service import QualityCheckService

# Initialize service
quality_service = QualityCheckService()

# Create a noisy/grainy test image similar to the industrial compressor
print("Creating noisy/grainy test image (similar to industrial compressor)...")
img_array = np.random.randint(100, 200, (400, 400, 3), dtype=np.uint8)
image = Image.fromarray(img_array)

# Add some structure but keep it noisy
image = image.filter(ImageFilter.GaussianBlur(radius=3))
# Add noise back
noise = np.random.normal(0, 20, (400, 400, 3))
img_with_noise = np.array(image).astype(np.float32) + noise
img_with_noise = np.clip(img_with_noise, 0, 255).astype(np.uint8)
image = Image.fromarray(img_with_noise)

print(f"Image size: {image.size} (400x400 as requested)")
print("\n" + "="*70)
print("RUNNING BLUR/NOISE DETECTION TEST ON 400x400 NOISY IMAGE")
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
print(f"\nCombined Score: {details['combined_score']:.2f}/100 (threshold: <65 = REJECT)")
print(f"Hard Reject: {details.get('hard_reject', False)}")
print(f"Quality Grade: {details['quality_grade'].upper()}")

print(f"\n{'='*70}")
print("KEY METRICS (Lower = Worse Quality)")
print(f"{'='*70}")
print(f"Laplacian Variance: {details['laplacian_var']:.2f}")
print(f"  └─ <60=extreme blur | <150=severe | <250=moderate")
print(f"\nDetail Loss: {details['detail_loss']:.2f}")
print(f"  └─ <1.2=severe | <2.5=moderate")
print(f"\nWavelet Energy: {details['wavelet_energy']:.2f}")
print(f"  └─ <5=severe | <8=moderate")
print(f"\nEdge Density: {details['edge_density']:.4f}")
print(f"  └─ <0.03=too smooth | <0.06=low detail")

print(f"\n{'='*70}")
print("NOISE METRICS (Higher = More Noise)")
print(f"{'='*70}")
print(f"Noise Score: {details['noise_score']:.2f}")
print(f"  └─ >120=moderate | >150=high | >200=severe")
print(f"\nHigh Freq Noise: {details['high_freq_noise']:.2f}")
print(f"  └─ >6=moderate | >8=high | >10=severe")
print(f"\nSNR (Signal-to-Noise): {details['snr']:.2f}")
print(f"  └─ <8=bad | <10=poor | <12=fair")
print(f"\nIs Noisy: {details.get('is_noisy', False)}")
print(f"Is Motion Blurred: {details.get('is_motion_blurred', False)}")

print(f"\n{'='*70}")
print("PENALTIES APPLIED")
print(f"{'='*70}")
penalties = details.get('penalties', {})
total_penalty = sum(penalties.values())
print(f"Noise Penalty: -{penalties.get('noise', 0)}")
print(f"Detail Penalty: -{penalties.get('detail', 0)}")
print(f"Motion Blur Penalty: -{penalties.get('motion_blur', 0)}")
print(f"Severe Blur Penalty: -{penalties.get('severe_blur', 0)}")
print(f"Contrast Penalty: -{penalties.get('contrast', 0)}")
print(f"{'─'*70}")
print(f"TOTAL PENALTY: -{total_penalty} points")

print(f"\n{'='*70}")
print(f"FINAL VERDICT: {'❌ REJECTED (BLOCKED)' if not blur_check['passed'] else '✅ PASSED (ALLOWED)'}")
print(f"{'='*70}")

if not blur_check['passed']:
    print("\n✅ SUCCESS: Noisy/blurry image correctly detected and rejected!")
else:
    print("\n⚠️ WARNING: Image was NOT rejected - thresholds may need adjustment")
