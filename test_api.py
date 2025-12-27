"""
Example usage scripts for the AI Image Checker API
"""

import requests
import json
from pathlib import Path


BASE_URL = "http://localhost:8000"


def test_quick_analysis(image_path: str):
    """Test quick CLIP-only analysis"""
    print("\n" + "="*50)
    print("Testing Quick Analysis")
    print("="*50)
    
    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/analyze/quick",
            files={'file': f}
        )
    
    result = response.json()
    print(json.dumps(result, indent=2))
    return result


def test_full_analysis(image_path: str):
    """Test full analysis with both models"""
    print("\n" + "="*50)
    print("Testing Full Analysis")
    print("="*50)
    
    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/analyze/full",
            files={'file': f}
        )
    
    result = response.json()
    print(json.dumps(result, indent=2))
    
    # Print key findings
    print("\n📊 Key Findings:")
    print(f"   Decision: {result.get('final_decision', 'N/A')}")
    
    if 'moderation' in result:
        mod = result['moderation']
        print(f"   Confidence: {mod.get('confidence', 'N/A')}%")
        print(f"   Explanation: {mod.get('explanation', 'N/A')[:100]}...")
    
    return result


def test_brand_similarity(image1_path: str, image2_path: str):
    """Test brand/logo similarity comparison"""
    print("\n" + "="*50)
    print("Testing Brand Similarity")
    print("="*50)
    
    with open(image1_path, 'rb') as f1, open(image2_path, 'rb') as f2:
        response = requests.post(
            f"{BASE_URL}/compare/similarity",
            files={'file1': f1, 'file2': f2}
        )
    
    result = response.json()
    print(json.dumps(result, indent=2))
    
    if 'similarity' in result:
        sim = result['similarity']
        score = sim.get('similarity_score', 0)
        print(f"\n📊 Similarity Score: {score:.2%}")
        print(f"   Are Similar: {'Yes' if sim.get('is_similar', False) else 'No'}")
    
    return result


def test_text_matching(image_path: str, descriptions: list):
    """Test image matching against text descriptions"""
    print("\n" + "="*50)
    print("Testing Text Matching")
    print("="*50)
    
    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/compare/text",
            files={'file': f},
            data={'descriptions': ','.join(descriptions)}
        )
    
    result = response.json()
    print(json.dumps(result, indent=2))
    
    if 'text_matching' in result:
        match = result['text_matching']
        print(f"\n📊 Best Match: {match.get('best_match', 'N/A')}")
        print(f"   Confidence: {match.get('confidence', 0):.2%}")
    
    return result


def test_dispute_resolution(image_path: str, initial_decision: str, reason: str):
    """Test dispute resolution"""
    print("\n" + "="*50)
    print("Testing Dispute Resolution")
    print("="*50)
    
    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/dispute",
            files={'file': f},
            data={
                'initial_decision': initial_decision,
                'dispute_reason': reason
            }
        )
    
    result = response.json()
    print(json.dumps(result, indent=2))
    
    if 'dispute_resolution' in result:
        res = result['dispute_resolution']
        print(f"\n📊 Dispute: {res.get('dispute_resolution', 'N/A')}")
        print(f"   Final Decision: {res.get('final_decision', 'N/A')}")
        print(f"   Confidence: {res.get('confidence', 0)}%")
    
    return result


def test_promo_detection(image_path: str):
    """Test promotional banner detection"""
    print("\n" + "="*50)
    print("Testing Promo Banner Detection")
    print("="*50)
    
    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/check/promo",
            files={'file': f}
        )
    
    result = response.json()
    print(json.dumps(result, indent=2))
    
    if 'promo_detection' in result:
        promo = result['promo_detection']
        print(f"\n📊 Is Promotional: {'Yes' if promo.get('is_promotional', False) else 'No'}")
        print(f"   Confidence: {promo.get('confidence', 0):.2%}")
    
    return result


def test_risk_assessment(image_path: str):
    """Test content risk assessment"""
    print("\n" + "="*50)
    print("Testing Risk Assessment")
    print("="*50)
    
    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/check/risk",
            files={'file': f}
        )
    
    result = response.json()
    print(json.dumps(result, indent=2))
    
    if 'risk_assessment' in result:
        risk = result['risk_assessment']
        print(f"\n📊 Risk Level: {risk.get('risk_level', 'N/A').upper()}")
        print(f"   Safe Content Score: {risk.get('safe_content_score', 0):.2%}")
    
    return result


def test_explanation(image_path: str, question: str):
    """Test getting explanation about image"""
    print("\n" + "="*50)
    print("Testing Image Explanation")
    print("="*50)
    
    with open(image_path, 'rb') as f:
        response = requests.post(
            f"{BASE_URL}/explain",
            files={'file': f},
            data={'question': question}
        )
    
    result = response.json()
    print(json.dumps(result, indent=2))
    return result


def check_server_health():
    """Check if server is running and healthy"""
    try:
        response = requests.get(f"{BASE_URL}/")
        result = response.json()
        print("\n✅ Server is healthy!")
        print(json.dumps(result, indent=2))
        return True
    except Exception as e:
        print(f"\n❌ Server is not responding: {e}")
        return False


if __name__ == "__main__":
    # Check server health first
    if not check_server_health():
        print("\n⚠️  Please start the server first with: python main.py")
        exit(1)
    
    # Example usage - replace with your actual image paths
    print("\n" + "="*60)
    print("AI Image Checker - Example Usage")
    print("="*60)
    
    # Replace these with actual image paths for testing
    IMAGE_PATH = "test_image.jpg"
    IMAGE_PATH_2 = "test_image2.jpg"
    
    # Uncomment the tests you want to run:
    
    # test_quick_analysis(IMAGE_PATH)
    # test_full_analysis(IMAGE_PATH)
    # test_brand_similarity(IMAGE_PATH, IMAGE_PATH_2)
    # test_text_matching(IMAGE_PATH, ["Nike logo", "Adidas logo", "Product photo"])
    # test_promo_detection(IMAGE_PATH)
    # test_risk_assessment(IMAGE_PATH)
    # test_explanation(IMAGE_PATH, "What objects can you see in this image?")
    # test_dispute_resolution(IMAGE_PATH, "REJECT", "This is a false positive")
    
    print("\n" + "="*60)
    print("To run tests, update IMAGE_PATH variables and uncomment test functions")
    print("="*60)
