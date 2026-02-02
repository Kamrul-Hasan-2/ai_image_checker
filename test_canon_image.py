"""Test Canon camera image for blur detection"""
import requests
from PIL import Image
from io import BytesIO
from quality_service import QualityCheckService

# Initialize service
quality_service = QualityCheckService()

# The Canon camera image from the user
# Save the attached image first or use a similar image URL
# For now, let's test with a similar camera product image

test_images = [
    # Product photos with clean backgrounds - should NOT be marked as blurry
    "https://images-na.ssl-images-amazon.com/images/I/81v5xqhgseL._AC_SL1500_.jpg",  # Camera
    "https://m.media-amazon.com/images/I/71HblAHs5xL._AC_SL1500_.jpg",  # Laptop
    "https://cdn.bdstall.com/product-image/398608_600X600.jpg",  # Camera from request
]

for img_url in test_images:
    print(f"\n{'='*80}")
    print(f"Testing: {img_url}")
    print('='*80)
    
    try:
        # Download image
        response = requests.get(img_url, timeout=10)
        image = Image.open(BytesIO(response.content))
        
        print(f"Image size: {image.size}")
        
        # Run quality check
        result = quality_service.check_image(image)
        
        print(f"\n✓ Passed: {result['passed']}")
        print(f"Action: {result['action']}")
        print(f"Reason: {result['reason']}")
        
        # Show blur details
        blur_check = result['checks']['blur']
        print(f"\n{'='*40}")
        print("BLUR ANALYSIS:")
        print('='*40)
        print(f"Blur passed: {blur_check['passed']}")
        print(f"Blur confidence: {blur_check.get('confidence', 0):.3f}")
        
        details = blur_check.get('details', {})
        print(f"\nKey Metrics:")
        print(f"  🎯 Product photo layout: {details.get('is_product_photo_layout', False)}")
        print(f"  📍 Center edge density: {details.get('center_edge_density', 0):.4f}")
        print(f"  📦 Border edge density: {details.get('border_edge_density', 0):.4f}")
        print(f"  Laplacian variance: {details.get('laplacian_var', 0):.2f}")
        print(f"  Tenengrad score: {details.get('tenengrad_score', 0):.2f}")
        print(f"  Edge density: {details.get('edge_density', 0):.4f}")
        print(f"  High freq energy: {details.get('high_freq_energy', 0):.2f}")
        print(f"  Detail loss 3x3: {details.get('detail_loss_3x3', 0):.2f}")
        print(f"  Wavelet energy: {details.get('wavelet_energy', 0):.2f}")
        print(f"  SNR: {details.get('snr', 0):.2f}")
        print(f"  Is noisy: {details.get('is_noisy', False)}")
        print(f"  Is motion blurred: {details.get('is_motion_blurred', False)}")
        print(f"  Hard reject: {details.get('hard_reject', False)}")
        
        print(f"\nScores:")
        print(f"  Combined score: {details.get('combined_score', 0):.2f}")
        print(f"  Noise penalty: {details.get('noise_penalty', 0)}")
        print(f"  Detail penalty: {details.get('detail_penalty', 0)}")
        print(f"  Motion blur penalty: {details.get('motion_blur_penalty', 0)}")
        print(f"  Severe blur penalty: {details.get('severe_blur_penalty', 0)}")
        
        print(f"\nBlur reason: {blur_check.get('reason', 'N/A')}")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
