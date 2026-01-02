"""
Test script for RunPod Serverless endpoint
"""

import requests
import json
import time

# RunPod configuration
ENDPOINT_ID = "w4nz9f65kklau1"  # Your endpoint ID
API_KEY = "rpa_J8BNLTEF77UW3LNXY8VR7T054IGL2T0N98LVKA65z8h29z"
ENDPOINT_URL = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/run"

headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {API_KEY}"
}


def test_image_url():
    """Test with image URL"""
    print("🧪 Testing with image URL...")
    
    data = {
        "input": {
            "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9",
            "category": "smartphone",
            "pipeline": "full"
        }
    }
    
    response = requests.post(ENDPOINT_URL, headers=headers, json=data)
    result = response.json()
    
    print(f"Status: {result.get('status')}")
    print(f"Job ID: {result.get('id')}")
    
    return result.get('id')


def test_image_base64():
    """Test with base64 image"""
    print("🧪 Testing with base64 image...")
    
    # Example base64 (you can replace with actual base64 string)
    data = {
        "input": {
            "image": "data:image/jpeg;base64,/9j/4AAQSkZJRg...",  # Add full base64 here
            "category": "laptop",
            "pipeline": "fast"
        }
    }
    
    response = requests.post(ENDPOINT_URL, headers=headers, json=data)
    result = response.json()
    
    print(f"Status: {result.get('status')}")
    print(f"Job ID: {result.get('id')}")
    
    return result.get('id')


def test_quality_only():
    """Test quality check only"""
    print("🧪 Testing quality check only...")
    
    data = {
        "input": {
            "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e",
            "category": "headphones",
            "pipeline": "quality_only"
        }
    }
    
    response = requests.post(ENDPOINT_URL, headers=headers, json=data)
    result = response.json()
    
    print(f"Status: {result.get('status')}")
    print(f"Job ID: {result.get('id')}")
    
    return result.get('id')


def check_job_status(job_id):
    """Check job status and get results"""
    status_url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/status/{job_id}"
    
    print(f"\n⏳ Checking job status: {job_id}")
    
    max_attempts = 60
    for attempt in range(max_attempts):
        response = requests.get(status_url, headers=headers)
        result = response.json()
        
        status = result.get('status')
        print(f"  Attempt {attempt + 1}: {status}")
        
        if status == 'COMPLETED':
            print("\n✅ Job completed!")
            print(json.dumps(result.get('output'), indent=2))
            return result.get('output')
        elif status == 'FAILED':
            print("\n❌ Job failed!")
            print(json.dumps(result, indent=2))
            return None
        
        time.sleep(2)
    
    print("\n⚠️ Timeout waiting for job completion")
    return None


def run_sync_request():
    """Run synchronous request (waits for result)"""
    print("🚀 Testing synchronous request...")
    
    sync_url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/runsync"
    
    data = {
        "input": {
            "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e",
            "category": "headphones",
            "pipeline": "full"
        }
    }
    
    response = requests.post(sync_url, headers=headers, json=data, timeout=120)
    result = response.json()
    
    print("\n📊 Result:")
    print(json.dumps(result, indent=2))
    
    return result


if __name__ == "__main__":
    print("=" * 70)
    print("AI IMAGE CHECKER - RunPod Serverless Test")
    print("=" * 70)
    
    # Test 1: Image URL with full pipeline
    job_id = test_image_url()
    if job_id:
        check_job_status(job_id)
    
    print("\n" + "=" * 70 + "\n")
    
    # Test 2: Quality check only
    job_id = test_quality_only()
    if job_id:
        check_job_status(job_id)
    
    print("\n" + "=" * 70 + "\n")
    
    # Test 3: Synchronous request
    # Uncomment to test sync mode:
    # run_sync_request()
    
    print("\n✅ All tests completed!")
