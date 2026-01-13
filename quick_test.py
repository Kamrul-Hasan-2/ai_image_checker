"""Quick test for AI Image Checker"""
import requests
import json

# Test with any image URL
IMAGE_URL = "https://cdn.bdstall.com/product-image/414291_800X800.jpg"
API_URL = "http://127.0.0.1:8000/api/ai_check_detectction"

print("🔍 Testing AI Image Checker...")
print(f"📷 Image: {IMAGE_URL}\n")

response = requests.post(
    API_URL, 
    json={"image_url": IMAGE_URL},
    timeout=180  # Increased for AI processing time
)

if response.status_code == 200:
    result = response.json()
    print("✅ RESULT:")
    print("="*60)
    print(f"Decision: {result.get('decision', 'Unknown')}")
    print(f"Confidence: {result.get('confidence', 0)}%")
    print(f"Explanation: {result.get('explanation', 'N/A')}")
    print(f"Violations: {result.get('violations', [])}")
    print(f"Categories: {result.get('categories_detected', [])}")
    print("="*60)
    print("\n📄 Full JSON:")
    print(json.dumps(result, indent=2))
else:
    print(f"❌ Error: {response.status_code}")
    print(response.text)
