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
        Extract text from image using EasyOCR with rule-based detection
        
        Returns:
            Dict containing extracted text, watermark detection, and promotional detection
        """
        # Convert PIL Image to numpy array for OpenCV
        img_array = np.array(image)
        img_height, img_width = img_array.shape[:2]
        total_area = img_width * img_height
        
        # Convert RGB to BGR for OpenCV
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # Perform OCR
        results = self.reader.readtext(img_array)
        
        # Parse results
        extracted_data = []
        all_text = []
        word_list = []
        text_area = 0
        
        for (bbox, text, confidence) in results:
            extracted_data.append({
                "text": text,
                "confidence": float(confidence),
                "bbox": bbox
            })
            all_text.append(text)
            word_list.extend(text.lower().split())
            
            # Calculate text area
            bbox_array = np.array(bbox)
            width = np.max(bbox_array[:, 0]) - np.min(bbox_array[:, 0])
            height = np.max(bbox_array[:, 1]) - np.min(bbox_array[:, 1])
            text_area += width * height
        
        # Combine all text
        full_text = " ".join(all_text)
        full_text_lower = full_text.lower()
        
        # RULE-BASED WATERMARK DETECTION (Hard Evidence)
        watermark_keywords = [
            "shutterstock", "getty", "istock", "preview", "sample", 
            "watermark", "depositphotos", "alamy", "dreamstime",
            "bigstock", "fotolia", "canva", "pexels", "unsplash"
        ]
        
        # Check for watermark keywords
        watermark_found = any(keyword in full_text_lower for keyword in watermark_keywords)
        
        # Check for word repetition (stock photos repeat watermarks)
        from collections import Counter
        word_counts = Counter(word_list)
        max_repetition = max(word_counts.values()) if word_counts else 0
        repetitive_watermark = max_repetition >= 3
        
        # Calculate text coverage percentage
        text_coverage = (text_area / total_area) * 100 if total_area > 0 else 0
        
        # Watermark confidence (0.0 to 1.0)
        watermark_confidence = 0.0
        if watermark_found:
            watermark_confidence = 0.9  # Keyword match is strong evidence
        elif repetitive_watermark and text_coverage > 15:
            watermark_confidence = 0.8  # Repeated text + high coverage
        elif text_coverage > 30:
            watermark_confidence = 0.6  # Very high text coverage suggests overlay
        
        # RULE-BASED PROMOTIONAL TEXT DETECTION
        promo_keywords = [
            "buy", "sale", "discount", "offer", "free", "limited",
            "deal", "promo", "save", "off", "%", "tk", "taka",
            "call", "contact", "whatsapp", "phone", "delivery"
        ]
        
        # Seller/Business indicators (company names, house, store, shop, etc.)
        business_indicators = [
            "house", "store", "shop", "enterprise", "company", "limited",
            "ltd", "inc", "corp", "corporation", "business", "trading",
            "mart", "center", "centre", "suppliers", "solutions", "services",
            "engineering", "technologies", "group", "international"
        ]
        
        # Check for seller/business names (e.g., "Desh Engineering House")
        words_in_text = full_text_lower.split()
        has_business_name = any(indicator in full_text_lower for indicator in business_indicators)
        
        # If text has business indicators + it's overlaid on image = promotional
        is_seller_branding = has_business_name and len(words_in_text) >= 2 and len(words_in_text) <= 6
        
        # Count promotional keywords
        promo_count = sum(1 for keyword in promo_keywords if keyword in full_text_lower)
        promo_found = promo_count >= 2  # At least 2 promotional keywords
        
        # Promotional confidence (0.0 to 1.0)
        promo_confidence = 0.0
        if is_seller_branding:
            promo_confidence = 0.75  # Business name overlay is strong promotional signal
        elif promo_count >= 3:
            promo_confidence = 0.9   # Many promo keywords
        elif promo_count >= 2:
            promo_confidence = 0.7
        elif promo_count == 1:
            promo_confidence = 0.3
        
        # OCR RISK SCORE (weighted)
        ocr_risk = watermark_confidence * 0.6 + promo_confidence * 0.4
        
        return {
            "text_found": len(all_text) > 0,
            "text_count": len(all_text),
            "full_text": full_text,
            "extracted_data": extracted_data,
            # Rule-based detection (HIGH CONFIDENCE)
            "watermark_detected": watermark_found or repetitive_watermark,
            "watermark_confidence": watermark_confidence,
            "watermark_keywords_found": watermark_found,
            "repetitive_text": repetitive_watermark,
            "max_word_repetition": max_repetition,
            "text_coverage_percent": text_coverage,
            "promotional_detected": promo_found or is_seller_branding,
            "promotional_confidence": promo_confidence,
            "promo_keyword_count": promo_count,
            "seller_branding_detected": is_seller_branding,
            "ocr_risk": ocr_risk  # 0.0 to 1.0
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
