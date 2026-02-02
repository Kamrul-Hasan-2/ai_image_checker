"""
Analyze blur detection for a specific image
"""

import requests
from PIL import Image
import io
from quality_service import QualityCheckService

# Initialize quality service
quality_service = QualityCheckService()

# Test image URL - replace with your image URL
test_image_url = "YOUR_IMAGE_URL_HERE"

print("=" * 80)
print("BLUR DETECTION ANALYSIS")
print("=" * 80)

try:
    # Load image
    print(f"\nLoading image from URL...")
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
    response = requests.get(test_image_url, headers=headers, timeout=10)
    response.raise_for_status()
    image = Image.open(io.BytesIO(response.content)).convert('RGB')
    
    print(f"Image size: {image.size[0]}x{image.size[1]}")
    
    # Run quality check
    print("\nRunning quality check...")
    result = quality_service.check_image(image)
    
    blur_check = result['checks']['blur']
    details = blur_check.get('details', {})
    
    # Display results
    print("\n" + "=" * 80)
    print("RESULTS")
    print("=" * 80)
    print(f"Blur Detected: {'YES ✗' if not blur_check['passed'] else 'NO ✓'}")
    print(f"Reason: {blur_check['reason']}")
    print(f"Confidence: {blur_check.get('confidence', 0):.2%}")
    
    print("\n" + "-" * 80)
    print("DETAILED METRICS")
    print("-" * 80)
    print(f"Combined Score: {details.get('combined_score', 0):.1f}/100 (threshold: 80)")
    print(f"Quality Grade: {details.get('quality_grade', 'unknown').upper()}")
    print(f"Hard Reject: {'YES ✗' if details.get('hard_reject', False) else 'NO ✓'}")
    
    print("\nSharpness Metrics:")
    print(f"  Laplacian Variance: {details.get('laplacian_var', 0):.1f} (need: 350+)")
    print(f"  Laplacian Mean: {details.get('laplacian_mean', 0):.2f} (need: 10+)")
    print(f"  Tenengrad Score: {details.get('tenengrad_score', 0):.1f} (need: 600+)")
    print(f"  Gradient Std: {details.get('gradient_std', 0):.2f} (need: 22+)")
    
    print("\nFrequency Analysis:")
    print(f"  High Freq Energy: {details.get('high_freq_energy', 0):.2f} (need: 25+)")
    print(f"  Freq Ratio: {details.get('freq_ratio', 0):.3f} (need: 0.35+)")
    print(f"  Wavelet Energy: {details.get('wavelet_energy', 0):.2f} (need: 15+)")
    
    print("\nEdge Detection:")
    print(f"  Edge Density: {details.get('edge_density', 0):.4f} (need: 0.10+)")
    print(f"  Strong Edge Density: {details.get('strong_edge_density', 0):.4f}")
    print(f"  Edge Strength Ratio: {details.get('edge_strength_ratio', 0):.3f} (need: 0.35+)")
    
    print("\nDetail Analysis:")
    print(f"  Detail Loss 3x3: {details.get('detail_loss', 0):.2f} (need: 5.5+)")
    print(f"  Detail Loss 5x5: {details.get('detail_loss_5x5', 0):.2f}")
    print(f"  Detail Loss 7x7: {details.get('detail_loss_7x7', 0):.2f}")
    
    print("\nNoise Analysis:")
    print(f"  Is Noisy: {'YES ✗' if details.get('is_noisy', False) else 'NO ✓'}")
    print(f"  Noise Score: {details.get('noise_score', 0):.1f} (threshold: 110)")
    print(f"  High Freq Noise: {details.get('high_freq_noise', 0):.2f} (threshold: 6)")
    print(f"  SNR: {details.get('snr', 0):.2f} (threshold: 8)")
    print(f"  Texture Consistency: {details.get('texture_consistency', 0):.1f}")
    
    print("\nMotion Blur:")
    print(f"  Is Motion Blurred: {'YES ✗' if details.get('is_motion_blurred', False) else 'NO ✓'}")
    print(f"  Motion Blur Indicator: {details.get('motion_blur_indicator', 0):.3f}")
    
    print("\nImage Properties:")
    print(f"  Contrast: {details.get('contrast', 0):.2f} (threshold: 30)")
    print(f"  Dynamic Range: {details.get('dynamic_range', 0):.1f} (threshold: 100)")
    
    penalties = details.get('penalties', {})
    total_penalty = sum(penalties.values())
    print(f"\nPenalties Applied (Total: {total_penalty}):")
    for penalty_name, penalty_value in penalties.items():
        if penalty_value > 0:
            print(f"  {penalty_name}: -{penalty_value}")
    
    print("\n" + "=" * 80)
    print("INTERPRETATION")
    print("=" * 80)
    
    score = details.get('combined_score', 0)
    if score >= 90:
        print("✓ GOOD QUALITY: Image passes with excellent sharpness")
    elif score >= 80:
        print("⚠ BORDERLINE: Image barely passes quality check")
    else:
        print("✗ POOR QUALITY: Image is too blurry/noisy - REJECTED")
    
    # Suggestions
    print("\nKey Issues:")
    laplacian = details.get('laplacian_var', 0)
    if laplacian < 80:
        print("  - CRITICAL: Laplacian variance extremely low (< 80)")
    elif laplacian < 200:
        print("  - SEVERE: Laplacian variance very low (< 200)")
    elif laplacian < 350:
        print("  - WARNING: Laplacian variance too low (< 350) - needs 350+ for quality")
    elif laplacian < 500:
        print("  - NOTICE: Laplacian variance moderate (< 500) - may have subtle blur")
    elif laplacian < 400:
        print("  - Laplacian variance below recommended (< 400)")
    
    if details.get('is_noisy', False):
        print("  - Image is noisy/grainy")
    
    if details.get('is_motion_blurred', False):
        print("  - Motion blur detected")
    
    detail_loss = details.get('detail_loss', 0)
    if detail_loss < 0.8:
        print("  - CRITICAL: Severely lacks detail")
    elif detail_loss < 1.5:
        print("  - Lacks detail")
    
    print("\n" + "=" * 80)
    
except Exception as e:
    print(f"\n✗ ERROR: {str(e)}")
    import traceback
    traceback.print_exc()
