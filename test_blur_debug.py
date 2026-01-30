"""
Local test script to debug blur detection
"""

from PIL import Image, ImageFilter
import numpy as np
from quality_service import QualityCheckService

# Initialize service
quality_service = QualityCheckService()

# Create a blurry test image
print("Creating test blurry image...")
img_array = np.random.randint(0, 255, (500, 500, 3), dtype=np.uint8)
image = Image.fromarray(img_array)
image = image.filter(ImageFilter.GaussianBlur(radius=10))
print("Created blurry test image (500x500 with Gaussian blur radius=10)\n")

print("="*60)
print("RUNNING BLUR DETECTION TEST")
print("="*60 + "\n")

# Run quality check
result = quality_service.check_image(image)

print(f"Overall Result: {'PASS' if result['passed'] else 'FAIL'}")
print(f"Action: {result['action']}")
print(f"Reason: {result['reason']}")
print(f"\nBlur Check Details:")

blur_check = result['checks']['blur']
print(f"  Passed: {blur_check['passed']}")
print(f"  Reason: {blur_check['reason']}")
print(f"  Confidence: {blur_check['confidence']:.3f}")

details = blur_check['details']
print(f"\n  Combined Score: {details['combined_score']:.2f}/100 (threshold: 65)")
print(f"  Hard Reject: {details.get('hard_reject', False)}")
print(f"  Quality Grade: {details['quality_grade']}")

print(f"\n  Key Metrics:")
print(f"    - Laplacian Variance: {details['laplacian_var']:.2f} (threshold: <60=extreme, <150=severe)")
print(f"    - Laplacian Mean: {details['laplacian_mean']:.2f}")
print(f"    - Detail Loss: {details['detail_loss']:.2f} (threshold: <1.2=severe)")
print(f"    - Wavelet Energy: {details['wavelet_energy']:.2f}")
print(f"    - Edge Density: {details['edge_density']:.4f}")
print(f"    - Is Motion Blurred: {details.get('is_motion_blurred', False)}")

print(f"\n  Penalties Applied:")
penalties = details.get('penalties', {})
print(f"    - Noise: -{penalties.get('noise', 0)}")
print(f"    - Detail: -{penalties.get('detail', 0)}")
print(f"    - Motion Blur: -{penalties.get('motion_blur', 0)}")
print(f"    - Severe Blur: -{penalties.get('severe_blur', 0)}")
print(f"    - TOTAL: -{sum(penalties.values())}")

print("\n" + "="*60)
print(f"FINAL VERDICT: {'❌ REJECTED' if not blur_check['passed'] else '✅ PASSED'}")
print("="*60)
