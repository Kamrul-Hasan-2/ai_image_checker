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
        """Analyze extracted text for specific patterns with enhanced detection"""
        full_text = " ".join(text_list)
        full_text_lower = full_text.lower()
        
        # Expanded promotional keywords (aggressive detection)
        promo_keywords = [
            # Direct sales language
            'sale', 'discount', 'off', '%', 'percent', 'offer', 'deal', 'promo', 'promotion',
            'buy now', 'order now', 'call now', 'shop now', 'get now', 'book now',
            'limited time', 'hurry', 'urgent', 'today only', 'last chance', 'don\'t miss',
            # Pricing/deals
            'free shipping', 'free delivery', 'cash on delivery', 'cod', 'emi', 'installment',
            'lowest price', 'best price', 'best deal', 'hot deal', 'mega sale', 'flash sale',
            'special offer', 'clearance', 'bargain', 'cheap', 'affordable',
            # Call to action
            'contact us', 'call us', 'whatsapp', 'inbox', 'message us', 'dm us',
            'visit us', 'store location', 'delivery available', 'home delivery',
            # Bengali promotional text
            'অফার', 'ডিসকাউন‌্ট', 'সেল', 'কিনুন', 'অর্ডার',
            # Urgency/scarcity
            'stock limited', 'few left', 'running out', 'while supplies last',
            'pre-order', 'reserve now', 'first come',
            # Quality claims
            'original', 'authentic', 'genuine', '100% original', 'warranty',
            'money back', 'guaranteed', 'certified'
        ]
        
        # Count promotional keywords
        promo_count = sum(1 for keyword in promo_keywords if keyword in full_text_lower)
        promo_detected = promo_count > 0
        
        # Enhanced regex patterns
        import re
        
        # Phone numbers (BD, India, generic)
        phone_patterns = [
            r'(?:\+?88)?[ -]?01[3-9]\d{8}',  # Bangladesh
            r'(?:\+?91)?[ -]?[6-9]\d{9}',  # India
            r'\d{3}[-.]?\d{3}[-.]?\d{4}',  # Generic
            r'\d{4}[-.]?\d{6}',  # Alternative format
        ]
        has_phone = any(re.search(pattern, full_text) for pattern in phone_patterns)
        
        # Website links and domains
        website_patterns = [
            r'(?:www\.|https?://)',
            r'\w+\.(?:com|bd|net|org|in|shop|store|online)',
            r'facebook\.com',
            r'daraz|bikroy|ajkerdeal|pickaboo|ryans|startech'
        ]
        has_website_link = any(re.search(pattern, full_text_lower) for pattern in website_patterns)
        
        # Social media handles
        social_pattern = r'@\w+|#\w+'
        has_social_media = bool(re.search(social_pattern, full_text))
        
        # Email addresses
        email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
        has_email = bool(re.search(email_pattern, full_text))
        
        # Check for brand indicators (not promotional by themselves)
        brand_indicators = ['®', '™', '©', 'inc', 'ltd', 'corp', 'llc', 'pvt']
        brand_detected = any(indicator in full_text_lower for indicator in brand_indicators)
        
        # Check for prices with currency symbols
        price_patterns = [
            r'৳\s*\d+',  # Taka symbol
            r'tk\.?\s*\d+',  # TK
            r'taka\s*\d+',
            r'rs\.?\s*\d+',  # Rupees
            r'\$\s*\d+',  # Dollar
            r'price:?\s*\d+'
        ]
        has_prices = any(re.search(pattern, full_text_lower) for pattern in price_patterns)
        
        # Text density scoring (0-100)
        text_count = len(text_list)
        total_chars = len(full_text)
        avg_word_length = total_chars / max(text_count, 1)
        
        # High text density + short words = likely promotional
        text_density_score = min((text_count * avg_word_length) / 50, 1.0) * 100
        
        # Calculate promotional score (0-100)
        promo_score = 0
        if promo_detected:
            promo_score += min(promo_count * 15, 40)  # Up to 40 points
        if has_phone:
            promo_score += 25
        if has_website_link:
            promo_score += 20
        if has_social_media:
            promo_score += 10
        if has_email:
            promo_score += 10
        if has_prices and (promo_detected or has_phone):
            promo_score += 15  # Prices + contact = promotional
        if text_density_score > 60:
            promo_score += 10  # Too much text
        
        promo_score = min(promo_score, 100)
        
        # Determine if promotional (threshold: 35)
        is_promotional = promo_score >= 35
        
        return {
            "has_promotional_text": promo_detected,
            "promo_keyword_count": promo_count,
            "has_phone_number": has_phone,
            "has_website_link": has_website_link,
            "has_social_media": has_social_media,
            "has_email": has_email,
            "has_brand_indicators": brand_detected,
            "has_prices": has_prices,
            "is_promotional": is_promotional,
            "promotional_score": promo_score,
            "text_count": text_count,
            "text_density": "high" if text_count > 10 else "medium" if text_count > 3 else "low",
            "text_density_score": text_density_score
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
