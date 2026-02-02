"""Test the street light image for blur and noise detection"""
import requests
import base64
from PIL import Image
from io import BytesIO

# Your deployed Modal endpoint
ENDPOINT = "https://bdstall-ai--ai-image-checker-check-image-endpoint.modal.run"

# Read the image
image_path = r"C:\Users\BLG\Desktop\ai_image_checker\street_light.jpg"

try:
    # Open and prepare image
    with open(image_path, 'rb') as f:
        image_data = f.read()
    
    # Convert to base64
    image_b64 = base64.b64encode(image_data).decode('utf-8')
    
    # Prepare request
    payload = {
        "image_data": image_b64,
        "product_title": "GREEN SOCIAL Street Light",
        "category": "lights"
    }
    
    print("=" * 80)
    print("Testing Street Light Image")
    print("=" * 80)
    print(f"Sending request to: {ENDPOINT}")
    
    # Send request
    response = requests.post(ENDPOINT, json=payload, timeout=120)
    
    if response.status_code == 200:
        result = response.json()
        
        print("\n" + "=" * 80)
        print("QUALITY ANALYSIS RESULTS")
        print("=" * 80)
        
        print(f"\n✅ Overall Status: {result['status']}")
        print(f"📊 Overall Quality Score: {result['overall_quality_score']:.2f}/1.00")
        
        # Blur Analysis
        print("\n" + "-" * 40)
        print("BLUR DETECTION:")
        print("-" * 40)
        blur = result['quality_analysis']['blur']
        print(f"  Blur Score: {blur['blur_score']:.3f}")
        print(f"  Laplacian Variance: {blur['laplacian_variance']:.2f}")
        print(f"  Is Blurry: {blur['is_blurry']}")
        print(f"  Assessment: {blur['assessment']}")
        
        # Noise Analysis
        print("\n" + "-" * 40)
        print("NOISE DETECTION:")
        print("-" * 40)
        noise = result['quality_analysis']['noise']
        print(f"  Noise Score: {noise['noise_score']:.3f}")
        print(f"  Noise Level: {noise['noise_level']:.2f}")
        print(f"  Is Noisy: {noise['is_noisy']}")
        print(f"  Assessment: {noise['assessment']}")
        
        # Other quality metrics
        print("\n" + "-" * 40)
        print("OTHER QUALITY METRICS:")
        print("-" * 40)
        exposure = result['quality_analysis']['exposure']
        print(f"  Exposure: {exposure['assessment']}")
        print(f"  Brightness: {exposure['brightness']:.2f}")
        
        color = result['quality_analysis']['color']
        print(f"  Color Balance: {color['assessment']}")
        
        resolution = result['quality_analysis']['resolution']
        print(f"  Resolution: {resolution['assessment']}")
        print(f"  Dimensions: {resolution['width']}x{resolution['height']}")
        
        # Issues
        if result['issues']:
            print("\n" + "-" * 40)
            print("⚠️  DETECTED ISSUES:")
            print("-" * 40)
            for issue in result['issues']:
                print(f"  - {issue}")
        else:
            print("\n✅ No quality issues detected!")
        
        print("\n" + "=" * 80)
        
    else:
        print(f"\n❌ Error: {response.status_code}")
        print(response.text)
        
except FileNotFoundError:
    print(f"❌ Image file not found at: {image_path}")
    print("Please save the image first!")
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
