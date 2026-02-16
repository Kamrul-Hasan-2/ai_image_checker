"""
Test if the local server is responding correctly
"""
import requests
import json

print("Testing local server at http://localhost:8000/image_checker/health")
print("="*60)

try:
    response = requests.get("http://localhost:8000/image_checker/health", timeout=5)
    print(f"✅ Status Code: {response.status_code}")
    print(f"✅ Response: {json.dumps(response.json(), indent=2)}")
except requests.exceptions.ConnectionError:
    print("❌ ERROR: Cannot connect to server. Is it running?")
    print("   Start it with: python main.py --port 8000")
except Exception as e:
    print(f"❌ ERROR: {e}")

print("\n" + "="*60)
print("Testing root endpoint at http://localhost:8000/image_checker")
try:
    response = requests.get("http://localhost:8000/image_checker", timeout=5)
    print(f"✅ Status Code: {response.status_code}")
    print(f"✅ Response: {json.dumps(response.json(), indent=2)}")
except Exception as e:
    print(f"❌ ERROR: {e}")
