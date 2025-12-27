"""
Test the AI Image Checker with a specific image
"""

import requests
from io import BytesIO
import json

# Image URL
IMAGE_URL = "https://i.bikroy-st.com/desktop-t9jn101-for-sale-dhaka/3f3fd173-6192-4166-be07-076e638802b0/620/466/fitted.jpg"
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
    """Test the complete 3-step pipeline"""
    print("\n" + "="*60)
    print("TESTING COMPLETE 3-STEP PIPELINE")
    print("="*60)
    
    image_data.seek(0)  # Reset file pointer
    files = {'file': ('test_image.jpg', image_data, 'image/jpeg')}
    
    response = requests.post(f"{API_BASE}/analyze/pipeline", files=files)
    
    if response.status_code == 200:
        result = response.json()
        print("\n✓ Pipeline completed successfully!\n")
        
        # Display results
        print("📊 FINAL SUMMARY:")
        print("-" * 60)
        summary = result.get('final_summary', {})
        
        print(f"Text Extracted: {summary.get('text_extracted', 'None')[:100]}")
        print(f"Category: {summary.get('category', 'Unknown')}")
        print(f"Risk Level: {summary.get('risk_level', 'Unknown').upper()}")
        print(f"Has Promotional Content: {summary.get('has_promotional_content', False)}")
        print(f"\nFinal Decision: {summary.get('final_decision', 'Unknown')}")
        print(f"Confidence: {summary.get('decision_confidence', 0)}%")
        print(f"\nExplanation: {summary.get('explanation', '')[:200]}...")
        
        print("\n" + "="*60)
        print("DETAILED RESULTS BY STEP:")
        print("="*60)
        
        pipeline = result.get('pipeline_results', {})
        
        # Step 1: OCR
        print("\n[Step 1] EasyOCR Results:")
        ocr = pipeline.get('step1_ocr', {})
        print(f"  Text Found: {ocr.get('text_found', False)}")
        print(f"  Text Count: {ocr.get('text_count', 0)}")
        print(f"  Full Text: {ocr.get('full_text', 'No text')[:150]}")
        analysis = ocr.get('analysis', {})
        print(f"  Promotional Text: {analysis.get('has_promotional_text', False)}")
        print(f"  Brand Indicators: {analysis.get('has_brand_indicators', False)}")
        print(f"  Has Prices: {analysis.get('has_prices', False)}")
        
        # Step 2: CLIP
        print("\n[Step 2] CLIP Results:")
        clip = pipeline.get('step2_clip', {})
        category = clip.get('category', {})
        print(f"  Top Category: {category.get('top_category', 'Unknown')}")
        print(f"  Category Confidence: {category.get('confidence', 0):.2%}")
        risk = clip.get('risk', {})
        print(f"  Risk Level: {risk.get('risk_level', 'Unknown')}")
        print(f"  Safe Content Score: {risk.get('safe_content_score', 0):.2%}")
        promo = clip.get('promo', {})
        print(f"  Is Promotional: {promo.get('is_promotional', False)}")
        
        # Step 3: Qwen2-VL
        print("\n[Step 3] Qwen2-VL Results:")
        qwen = pipeline.get('step3_qwen2vl', {})
        print(f"  Decision: {qwen.get('decision', 'Unknown')}")
        print(f"  Confidence: {qwen.get('confidence', 0)}%")
        print(f"  Violations: {qwen.get('violations', [])}")
        print(f"  Recommended Action: {qwen.get('recommended_action', 'N/A')}")
        
        # Save full results to file
        with open('test_results.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print("\n✓ Full results saved to test_results.json")
        
    else:
        print(f"\n✗ Error: {response.status_code}")
        print(response.text)


def test_individual_steps(image_data):
    """Test each step individually"""
    print("\n" + "="*60)
    print("TESTING INDIVIDUAL STEPS")
    print("="*60)
    
    # Step 1: OCR
    print("\n[Step 1] Testing EasyOCR...")
    image_data.seek(0)
    files = {'file': ('test_image.jpg', image_data, 'image/jpeg')}
    response = requests.post(f"{API_BASE}/step1/ocr", files=files)
    if response.status_code == 200:
        result = response.json()
        ocr_result = result.get('result', {})
        print(f"  ✓ Text found: {ocr_result.get('text_count', 0)} regions")
        print(f"    Sample: {ocr_result.get('full_text', '')[:80]}...")
    
    # Step 2: CLIP
    print("\n[Step 2] Testing CLIP...")
    image_data.seek(0)
    files = {'file': ('test_image.jpg', image_data, 'image/jpeg')}
    response = requests.post(f"{API_BASE}/step2/clip", files=files)
    if response.status_code == 200:
        result = response.json()
        clip_result = result.get('result', {})
        category = clip_result.get('category_analysis', {})
        print(f"  ✓ Category: {category.get('top_category', 'Unknown')}")
        print(f"    Confidence: {category.get('confidence', 0):.2%}")
    
    # Step 3: Qwen2-VL
    print("\n[Step 3] Testing Qwen2-VL...")
    image_data.seek(0)
    files = {'file': ('test_image.jpg', image_data, 'image/jpeg')}
    response = requests.post(f"{API_BASE}/step3/qwen", files=files)
    if response.status_code == 200:
        result = response.json()
        qwen_result = result.get('result', {})
        print(f"  ✓ Decision: {qwen_result.get('decision', 'Unknown')}")
        print(f"    Confidence: {qwen_result.get('confidence', 0)}%")


def main():
    """Main test function"""
    print("\n" + "="*60)
    print("AI IMAGE CHECKER - TEST SCRIPT")
    print("="*60)
    
    # Check server health
    print("\n🔍 Checking server health...")
    try:
        response = requests.get(f"{API_BASE}/")
        if response.status_code == 200:
            health = response.json()
            print(f"✓ Server is healthy!")
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
    
    # Test individual steps
    test_individual_steps(image_data)
    
    print("\n" + "="*60)
    print("✓ ALL TESTS COMPLETED")
    print("="*60)


if __name__ == "__main__":
    main()
