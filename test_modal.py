"""
Test script for Modal.com deployment
"""

import requests
import json

# Your Modal endpoint URL (you'll get this after deploying)
# Format: https://YOUR_USERNAME--ai-image-checker-check-image-endpoint.modal.run
MODAL_ENDPOINT = "https://bdstall-ai--ai-image-checker-check-image-endpoint.modal.run"


def test_single_image():
    """Test single image processing"""
    print("Testing single image...")
    
    payload = {
        "image": "https://picsum.photos/800/600",
        "category": "electronics",
        "pipeline": "full"
    }
    
    response = requests.post(MODAL_ENDPOINT, json=payload)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print("-" * 60)


def test_multiple_images():
    """Test multiple images processing"""
    print("Testing multiple images...")
    
    payload = {
        "images": [
            {
                "image": "https://picsum.photos/800/600",
                "category": "electronics"
            },
            {
                "image": "https://picsum.photos/600/800",
                "category": "clothing"
            }
        ],
        "pipeline": "full"
    }
    
    response = requests.post(MODAL_ENDPOINT, json=payload)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print("-" * 60)


def test_with_base64():
    """Test with base64 encoded image"""
    print("Testing base64 image...")
    
    import base64
    from PIL import Image
    import io
    
    # Create a simple test image
    img = Image.new('RGB', (100, 100), color='red')
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG')
    img_str = base64.b64encode(buffer.getvalue()).decode()
    
    payload = {
        "image": f"data:image/jpeg;base64,{img_str}",
        "category": "test",
        "pipeline": "full"
    }
    
    response = requests.post(MODAL_ENDPOINT, json=payload)
    
    print(f"Status Code: {response.status_code}")
    print(f"Response: {json.dumps(response.json(), indent=2)}")
    print("-" * 60)


if __name__ == "__main__":
    print("=" * 60)
    print("Modal.com Image Checker Test")
    print("=" * 60)
    
    print("\nNOTE: Update MODAL_ENDPOINT with your actual endpoint URL")
    print("You'll get this after running: modal deploy modal_handler.py\n")
    
    if MODAL_ENDPOINT == "YOUR_MODAL_ENDPOINT_URL_HERE":
        print("❌ Please update MODAL_ENDPOINT in the script first!")
        print("\nTo deploy:")
        print("1. pip install modal")
        print("2. python -m modal setup")
        print("3. modal deploy modal_handler.py")
        print("4. Copy the endpoint URL and update this script")
    else:
        try:
            test_single_image()
            test_multiple_images()
            test_with_base64()
            print("✅ All tests completed!")
        except Exception as e:
            print(f"❌ Error: {e}")
