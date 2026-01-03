"""
Test simplified JSON response format
"""
import requests
import json

# RunPod configuration
ENDPOINT_ID = "w4nz9f65kklau1"
API_KEY = "rpa_J8BNLTEF77UW3LNXY8VR7T054IGL2T0N98LVKA65z8h29z"
ENDPOINT_URL = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/run"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}

# Test with single image
print("=" * 70)
print("Testing Simplified JSON Response Format")
print("=" * 70)

data = {
    "input": {
        "image": "https://cdn.bdstall.com/product-image/412549_800X800.webp",
        "category": "smartphone",
        "pipeline": "full"
    }
}

print("\n📤 Sending request...")
response = requests.post(ENDPOINT_URL, headers=headers, json=data)
result = response.json()

print(f"\n✅ Response received!")
print(f"Status: {result.get('status')}")
print(f"Job ID: {result.get('id')}")

# Check status
import time
status_url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/status/{result.get('id')}"

print("\n⏳ Waiting for result...")
for i in range(30):
    time.sleep(3)
    status_response = requests.get(status_url, headers=headers)
    status_result = status_response.json()
    
    if status_result.get('status') == 'COMPLETED':
        print("\n" + "=" * 70)
        print("SIMPLIFIED JSON RESPONSE")
        print("=" * 70)
        
        output = status_result.get('output', {})
        print(json.dumps(output, indent=2))
        
        print("\n" + "=" * 70)
        print("EXPECTED MINIMAL FORMAT:")
        print("=" * 70)
        print("""
{
  "blur_image": 5,              // 5 if yes, 0 if no
  "screen_short": 0,             // 8 if yes, 0 if no
  "category_mismatch": 2,        // 2 if yes, 0 if no
  "illegal": 0,                  // 9 if yes, 0 if no
  "promotional_text": 3,         // 3 if yes, 0 if no
  "stock_photo": 0,              // 10 if yes, 0 if no
  "watermark": 0,                // 4 if yes, 0 if no
  "total_risk_score": 10,
  "risk_level": 96,
  "qwen_needs_moderation": true, // Only if risk_level >= 85
  "final_decision": "rejected"
}
        """)
        
        print("\n✅ Test completed!")
        break
    elif status_result.get('status') == 'FAILED':
        print(f"\n❌ Job failed!")
        print(json.dumps(status_result, indent=2))
        break
    
    print(f"  Status: {status_result.get('status')} (attempt {i+1}/30)")

print("\n" + "=" * 70)
