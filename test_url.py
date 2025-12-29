"""
Test the AI Image Checker with image URL
"""

import requests
import json

# Image URL
IMAGE_URL = "https://cdn.bdstall.com/product-image/414291_800X800.jpg"
API_BASE = "http://localhost:8000"


def test_image_url(image_url):
    """Test with image URL"""
    print("\n" + "="*60)
    print("AI IMAGE CHECKER - URL TEST")
    print("="*60)
    print(f"\nImage URL: {image_url}")
    
    # Call API with POST
    api_url = f"{API_BASE}/api/ai_check_detectction"
    payload = {"image_url": image_url}
    print(f"\nCalling API with POST...")
    
    try:
        response = requests.post(api_url, json=payload, timeout=120)
        
        if response.status_code == 200:
            result = response.json()
            
            print("\n" + "="*60)
            print("RESULT:")
            print("="*60)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            
            print("\n" + "="*60)
            print("SUMMARY:")
            print("="*60)
            print(f"Decision: {result.get('decision', 'Unknown')}")
            print(f"Confidence: {result.get('confidence', 0)}%")
            print(f"Explanation: {result.get('explanation', 'N/A')}")
            print(f"Violations: {', '.join(result.get('violations', []))}")
            print(f"Categories: {', '.join(result.get('categories_detected', []))}")
            
        else:
            print(f"\n✗ Error: {response.status_code}")
            print(response.text)
    
    except Exception as e:
        print(f"\n✗ Error: {e}")


if __name__ == "__main__":
    test_image_url(IMAGE_URL)
