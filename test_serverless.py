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


def test_single_image():
    """Test with single image URL"""
    print("🧪 Testing with SINGLE image...")
    
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


def test_multiple_images():
    """Test with multiple images in array"""
    print("🧪 Testing with MULTIPLE images...")
    
    data = {
        "input": {
            "images": [
                {
                    "image": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9",
                    "category": "smartphone"
                },
                {
                    "image": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e",
                    "category": "headphones"
                },
                {
                    "image": "https://cdn.bdstall.com/product-image/414968_800X800.webp",
                    "category": "Computer » PC & Laptop » Laptop"
                }
            ],
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


def check_job_status(job_id, test_name="Test"):
    """Check job status and get results"""
    status_url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/status/{job_id}"
    
    print(f"\n⏳ Checking job status for {test_name}: {job_id}")
    
    max_attempts = 60
    for attempt in range(max_attempts):
        response = requests.get(status_url, headers=headers)
        result = response.json()
        
        status = result.get('status')
        print(f"  Attempt {attempt + 1}/{max_attempts}: {status}")
        
        if status == 'COMPLETED':
            print(f"\n✅ {test_name} completed!")
            output = result.get('output')
            
            # Pretty print the output
            print("\n" + "="*70)
            print(f"RESULTS - {test_name}")
            print("="*70)
            
            # Check if batch mode or single mode
            if output.get('mode') == 'batch':
                print(f"\n📦 Batch Mode - {output.get('total_images')} images processed")
                print(f"Pipeline: {output.get('pipeline_mode')}")
                
                # Show summary
                summary = output.get('summary', {})
                print(f"\n📊 Summary:")
                print(f"  ✅ Approved: {summary.get('approved')}")
                print(f"  ❌ Rejected: {summary.get('rejected')}")
                print(f"  📈 Success Rate: {summary.get('success_rate')}")
                
                # Show each image result
                for img_result in output.get('results', []):
                    idx = img_result.get('image_index')
                    category = img_result.get('category')
                    decision = img_result.get('final_decision')
                    confidence = img_result.get('final_confidence', 0)
                    
                    status_icon = "✅" if decision else "❌"
                    print(f"\n  {status_icon} Image {idx}: {category}")
                    print(f"     Decision: {'APPROVED' if decision else 'REJECTED'}")
                    print(f"     Confidence: {confidence:.2%}")
                    
                    if 'matched_at' in img_result:
                        print(f"     Matched at: {img_result['matched_at']}")
                    if 'risk_level' in img_result:
                        print(f"     Risk Level: {img_result['risk_level']}")
            else:
                # Single image mode
                print(f"\n📸 Single Image Mode")
                print(f"Category: {output.get('category')}")
                print(f"Pipeline: {output.get('pipeline_mode')}")
                print(f"\n🎯 Final Decision: {'✅ APPROVED' if output.get('final_decision') else '❌ REJECTED'}")
                print(f"Confidence: {output.get('final_confidence', 0):.2%}")
                
                if 'matched_at' in output:
                    print(f"Matched at: {output['matched_at']}")
                if 'risk_level' in output:
                    print(f"Risk Level: {output['risk_level']}")
                if 'reasoning' in output:
                    print(f"\n💡 Reasoning: {output['reasoning']}")
            
            print("\n" + "="*70)
            print("\n📋 Full JSON Response:")
            print(json.dumps(output, indent=2))
            
            return output
            
        elif status == 'FAILED':
            print(f"\n❌ {test_name} failed!")
            print(json.dumps(result, indent=2))
            return None
        
        time.sleep(2)
    
    print(f"\n⚠️ Timeout waiting for {test_name} completion")
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
    
    # Test 1: Single Image with full pipeline
    print("\n" + "=" * 70)
    print("TEST 1: Single Image")
    print("=" * 70)
    job_id = test_single_image()
    if job_id:
        check_job_status(job_id, "Single Image Test")
    
    print("\n" + "=" * 70 + "\n")
    
    # Test 2: Multiple Images (NEW!)
    print("\n" + "=" * 70)
    print("TEST 2: Multiple Images (Batch Mode)")
    print("=" * 70)
    job_id = test_multiple_images()
    if job_id:
        check_job_status(job_id, "Multiple Images Test")
    
    print("\n" + "=" * 70 + "\n")
    
    # Test 3: Quality check only
    print("\n" + "=" * 70)
    print("TEST 3: Quality Check Only")
    print("=" * 70)
    job_id = test_quality_only()
    if job_id:
        check_job_status(job_id, "Quality Only Test")
    
    print("\n" + "=" * 70 + "\n")
    
    # Test 4: Synchronous request
    # Uncomment to test sync mode:
    # print("\n" + "=" * 70)
    # print("TEST 4: Synchronous Request")
    # print("=" * 70)
    # run_sync_request()
    
    print("\n✅ All tests completed!")
