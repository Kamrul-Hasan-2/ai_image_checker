"""
Test the AI Image Checker with a specific image
"""

import requests
from io import BytesIO
import json

# Image URL
IMAGE_URL = "https://cdn.bdstall.com/product-image/414291_800X800.jpg"
API_BASE = "http://localhost:8000"


def download_image(url):
    """Download image from URL"""
    print(f"📥 Downloading image from: {url}")
    response = requests.get(url)
    if response.status_code == 200:
        print("✓ Image downloaded successfully")
        return BytesIO(response.content)
    else:
        print(f"✗ Failed to download image: {response.status_code}")
        return None


def test_complete_pipeline(image_data):
    """Test the complete smart pipeline"""
    print("\n" + "="*60)
    print("TESTING SMART 5-STEP PIPELINE")
    print("="*60)
    
    image_data.seek(0)  # Reset file pointer
    files = {'file': ('test_image.jpg', image_data, 'image/jpeg')}
    
    response = requests.post(f"{API_BASE}/analyze", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print("\n✓ Pipeline completed successfully!\n")
        
        # Display results
        print("📊 FINAL SUMMARY:")
        print("-" * 60)
        
        print(f"Final Decision: {result.get('final_decision', 'Unknown')}")
        print(f"Reason: {result.get('reason', 'N/A')}")
        print(f"Stopped at Step: {result.get('stopped_at', 'Unknown')}")
        print(f"Confidence: {result.get('confidence', 'N/A')}")
        if 'risk' in result:
            print(f"Risk Score: {result.get('risk', 0):.2f}")
        if 'category' in result:
            print(f"Category: {result.get('category', 'N/A')}")
        
        print("\n" + "="*60)
        print("PIPELINE LOG:")
        print("="*60)
        
        pipeline_log = result.get('log', [])
        
        for log_entry in pipeline_log:
            step_num = log_entry.get('step', '?')
            service = log_entry.get('service', 'Unknown')
            print(f"\n[Step {step_num}] {service}")
            
            step_result = log_entry.get('result', {})
            if step_result:
                for key, value in step_result.items():
                    if isinstance(value, dict):
                        print(f"  {key}:")
                        for k, v in value.items():
                            print(f"    {k}: {v}")
                    else:
                        print(f"  {key}: {value}")
        
        # Save full results to file
        with open('test_results.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("\n✓ Full results saved to test_results.json")
        
    else:
        print(f"\n✗ Error: {response.status_code}")
        print(response.text)


def test_individual_steps(image_data):
    """Individual step testing not available in smart pipeline"""
    print("\n" + "="*60)
    print("NOTE: Smart pipeline uses integrated steps")
    print("Individual step testing not available")
    print("The pipeline automatically stops at the optimal step")
    print("="*60)


def main():
    print("\n" + "="*60)
    print("AI IMAGE CHECKER - TEST SCRIPT")
    print("="*60)
    
    # Check server health
    print("\n🔍 Checking server health...")
    try:
        response = requests.get(f"{API_BASE}/health")
        if response.status_code == 200:
            health = response.json()
            print("✓ Server is healthy!")
            print(f"  Pipeline: {health.get('pipeline', 'Unknown')}")
            models = health.get('models', {})
            for step, status in models.items():
                print(f"  {step}: {status}")
        else:
            print("✗ Server is not responding properly")
            return
    except Exception as e:
        print(f"✗ Cannot connect to server: {e}")
        print("\nPlease start the server first with: python main.py")
        return
    
    # Download image
    image_data = download_image(IMAGE_URL)
    if not image_data:
        return
    
    # Test complete pipeline
    test_complete_pipeline(image_data)
    
    # Test individual steps (note)
    test_individual_steps(image_data)
    
    print("\n" + "="*60)
    print("✓ ALL TESTS COMPLETED")
    print("="*60)


if __name__ == "__main__":
    main()
