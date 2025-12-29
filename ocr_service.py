"""
EasyOCR Service for text extraction from images
Step 1 in the pipeline: Extract all text content
"""

import easyocr
import cv2
import numpy as np
from PIL import Image
from typing import Dict, List, Tuple


class OCRService:
    def __init__(self, languages: List[str] = ['en']):
        """Initialize EasyOCR reader"""
        print(f"Loading EasyOCR model for languages: {languages}")
        self.reader = easyocr.Reader(languages, gpu=True)
        print("EasyOCR model loaded successfully")
    
    def extract_text(self, image: Image.Image) -> Dict:
        """
        Extract text from image using EasyOCR
        
        Returns:
            Dict containing extracted text, bounding boxes, and confidence scores
        """
        # Convert PIL Image to numpy array for OpenCV
        img_array = np.array(image)
        
        # Convert RGB to BGR for OpenCV
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Perform OCR
        results = self.reader.readtext(img_array)
        
        # Parse results
        extracted_data = []
        all_text = []
        
        for (bbox, text, confidence) in results:
            extracted_data.append({
                "text": text,
                "confidence": float(confidence),
                "bbox": bbox
            })
            all_text.append(text)
        
        # Combine all text
        full_text = " ".join(all_text)
        
        # Analyze text content
        analysis = self._analyze_text(all_text)
        
        return {
            "text_found": len(all_text) > 0,
            "text_count": len(all_text),
            "full_text": full_text,
            "extracted_data": extracted_data,
            "analysis": analysis
        }
    
    def _analyze_text(self, text_list: List[str]) -> Dict:
        """Analyze extracted text for specific patterns"""
        full_text = " ".join(text_list)
        full_text_lower = full_text.lower()
        
        # Promotional keywords (not product names - only sale/discount/contact info)
        promo_keywords = [
            'sale', 'discount', 'off', '%', 'offer', 'deal', 'promo',
            'buy now', 'order now', 'call now', 'limited time', 'hurry',
            'free shipping', 'cash on delivery', 'cod', 'emi available',
            'lowest price', 'best price', 'special offer', 'clearance'
        ]
        promo_detected = any(keyword in full_text_lower for keyword in promo_keywords)
        
        # Check for phone numbers (BD format)
        import re
        phone_pattern = r'(?:\+?88)?01[3-9]\d{8}'
        has_phone = bool(re.search(phone_pattern, full_text))
        
        # Check for website links
        website_pattern = r'(?:www\.|https?://|\.com|\.bd|\.net|\.org)'
        has_website_link = bool(re.search(website_pattern, full_text_lower))
        
        # Check for brand indicators (not promotional)
        brand_indicators = ['®', '™', '©', 'inc', 'ltd', 'corp', 'llc']
        brand_detected = any(indicator in full_text_lower for indicator in brand_indicators)
        
        # Check for prices (not promotional by itself)
        has_prices = any(char in full_text_lower for char in ['৳', 'tk', 'taka', 'price', 'rs'])
        
        return {
            "has_promotional_text": promo_detected,
            "has_phone_number": has_phone,
            "has_website_link": has_website_link,
            "has_brand_indicators": brand_detected,
            "has_prices": has_prices,
            "is_promotional": promo_detected or has_phone or has_website_link,
            "text_density": "high" if len(text_list) > 10 else "medium" if len(text_list) > 3 else "low"
        }
    
    def detect_text_regions(self, image: Image.Image) -> Image.Image:
        """
        Draw bounding boxes around detected text regions
        Returns annotated image
        """
        img_array = np.array(image)
        
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        results = self.reader.readtext(img_array)
        
        for (bbox, text, confidence) in results:
            # Convert bbox to integer coordinates
            top_left = tuple(map(int, bbox[0]))
            bottom_right = tuple(map(int, bbox[2]))
            
            # Draw rectangle
            cv2.rectangle(img_array, top_left, bottom_right, (0, 255, 0), 2)
            
            # Put confidence score
            cv2.putText(
                img_array, 
                f"{confidence:.2f}", 
                top_left, 
                cv2.FONT_HERSHEY_SIMPLEX, 
                0.5, 
                (0, 255, 0), 
                1
            )
        
        # Convert back to PIL Image
        img_array = cv2.cvtColor(img_array, cv2.COLOR_BGR2RGB)
        return Image.fromarray(img_array)
