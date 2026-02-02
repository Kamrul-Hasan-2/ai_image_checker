"""Test balanced blur detection - catch real blur but not false positives"""
import requests
from PIL import Image
from io import BytesIO
from quality_service import QualityCheckService

# Initialize service
quality_service = QualityCheckService()

test_images = [
    ("Canon Printer (slightly blurry)", "https://i5.walmartimages.com/asr/72c8d8e3-0a3d-4d6a-9c3e-8e5e5c5c5e5e.jpg"),
    ("Laptop (clean)", "https://m.media-amazon.com/images/I/71HblAHs5xL._AC_SL1500_.jpg"),
    ("Camera from request (clean)", "https://cdn.bdstall.com/product-image/398608_600X600.jpg"),
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
        
        result = quality_service.check_image(image)
        
        print(f"\n✓ Overall Passed: {result['passed']}")
        print(f"Action: {result['action']}")
        
        blur_check = result['checks']['blur']
        details = blur_check.get('details', {})
        
        print(f"\n{'='*40}")
        print("BLUR VERDICT:")
        print('='*40)
        print(f"Blur passed: {'✅ YES' if blur_check['passed'] else '❌ NO (REJECTED)'}")
        print(f"Blur confidence: {blur_check.get('confidence', 0):.3f}")
        print(f"Combined score: {details.get('combined_score', 0):.2f}/100")
        print(f"Quality grade: {details.get('quality_grade', 'N/A')}")
        
        print(f"\n📊 Key Metrics:")
        print(f"  Product layout: {details.get('is_product_photo_layout', False)}")
        print(f"  Laplacian var: {details.get('laplacian_var', 0):.2f}")
        print(f"  Edge density: {details.get('edge_density', 0):.4f}")
        print(f"  Detail loss: {details.get('detail_loss', 0):.2f}")
        print(f"  Wavelet energy: {details.get('wavelet_energy', 0):.2f}")
        print(f"  Hard reject: {details.get('hard_reject', False)}")
        
        print(f"\n💬 Reason: {blur_check.get('reason', 'N/A')}")
        
    except Exception as e:
        print(f"Error: {e}")
