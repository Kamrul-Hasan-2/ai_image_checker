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
        print("EXPECTED FORMAT:")
        print("=" * 70)
        print("""
{
  "blur_detection": "yes/no",
  "blur_score": 28.5,
  "screenshort_check": "yes/no",
  "corruption_check": "yes/no",
  
  "image_extract": "Just some text about image",
  
  "has_brand_indicators": true/false,
  "has_phone_number": true/false,
  "has_prices": true/false,
  "has_promotional_text": true/false,
  "has_website_link": true/false,
  "is_promotional": true/false,
  "stock_photo": true/false,
  "illegal_photo": true/false,
  
  "category": "Computer » Monitor » Monitor",
  "category_match": true/false,
  
  "blur_image": 5,           // 5 if yes, 0 if no
  "screen_short": 8,          // 8 if yes, 0 if no
  "category_mismatch": 2,     // 2 if yes, 0 if no
  "illegal": 9,               // 9 if yes, 0 if no
  "promotional_text": 3,      // 3 if yes, 0 if no
  "stock_photo_score": 10,    // 10 if yes, 0 if no
  "watermark": 4,             // 4 if yes, 0 if no
  
  "total_risk_score": 12,
  "risk_level": 96,
  
  "qwen_vl_2b": {  // Only if risk_level >= 85
    "is_promotional_text": true/false,
    "image_description": "...",
    "is_ai_generated": true/false,
    "needs_manual_moderation": true/false
  },
  
  "final_decision": "approved/rejected"
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
