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
        Includes preprocessing for faded/transparent watermarks
        
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
        
        # Create enhanced version for better watermark detection
        # Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
        if len(img_array.shape) == 3:
            lab = cv2.cvtColor(img_array, cv2.COLOR_BGR2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8,8))  # Slightly more aggressive
            l_enhanced = clahe.apply(l)
            enhanced = cv2.merge([l_enhanced, a, b])
            enhanced = cv2.cvtColor(enhanced, cv2.COLOR_LAB2BGR)
        else:
            clahe = cv2.createCLAHE(clipLimit=3.5, tileGridSize=(8,8))
            enhanced = clahe.apply(img_array)
        
        # Perform OCR on original and enhanced images (2 passes only for speed)
        results = self.reader.readtext(img_array)
        results_enhanced = self.reader.readtext(enhanced)
        
        # Combine results from both passes (deduplicate by text content)
        all_results = results + results_enhanced
        seen_texts = set()
        unique_results = []
        for result in all_results:
            text = result[1].lower().strip()
            if text not in seen_texts and len(text) > 0:
                seen_texts.add(text)
                unique_results.append(result)
        
        # Parse results
        extracted_data = []
        all_text = []
        word_list = []
        text_area = 0
        
        for (bbox, text, confidence) in unique_results:
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
        
        # Bangladesh marketplace watermarks (HIGH PRIORITY)
        bd_marketplace_keywords = ["bikroy", "daraz", "bikroy.com", "daraz.com.bd", "bik", "kroy"]
        
        # Check for watermark keywords (case-insensitive)
        watermark_found = any(keyword in full_text_lower for keyword in watermark_keywords)
        
        # Check for BD marketplace watermarks (even partial match)
        bd_watermark_found = any(keyword in full_text_lower for keyword in bd_marketplace_keywords)
        
        # Also check if "bikroy" can be formed from multiple words (e.g., "bik roy")
        if not bd_watermark_found:
            text_no_spaces = full_text_lower.replace(" ", "").replace("-", "")
            bd_watermark_found = "bikroy" in text_no_spaces or "daraz" in text_no_spaces
        
        # Check for word repetition (stock photos repeat watermarks)
        from collections import Counter
        word_counts = Counter(word_list)
        max_repetition = max(word_counts.values()) if word_counts else 0
        repetitive_watermark = max_repetition >= 3
        
        # Calculate text coverage percentage
        text_coverage = (text_area / total_area) * 100 if total_area > 0 else 0
        
        # Watermark confidence (0.0 to 1.0)
        watermark_confidence = 0.0
        if bd_watermark_found:
            watermark_confidence = 0.99  # Bikroy/Daraz = definite watermark (maximum)
        elif watermark_found:
            watermark_confidence = 0.95  # Other stock photo watermarks (increased)
        elif repetitive_watermark and text_coverage > 8:
            watermark_confidence = 0.90  # Repeated text + coverage (lowered threshold more)
        elif text_coverage > 15:
            watermark_confidence = 0.75  # Medium text coverage suggests overlay (lowered)
        elif len(all_text) > 5 and text_coverage > 10:
            watermark_confidence = 0.65  # Many text elements suggest watermark
        
        # RULE-BASED PROMOTIONAL TEXT DETECTION
        # Phone number patterns (English and Bengali digits)
        import re
        phone_patterns = [
            r'\+?88[0-9]{11}',  # Bangladesh: +8801712345678
            r'01[0-9]{9}',      # Mobile: 01712345678
            r'[0-9]{3}[-.\\s_]?[0-9]{3,4}[-.\\s_]?[0-9]{2}[-.\\s_]?[0-9]{2}',  # With separators
            r'০১[০-৯]{9}',      # Bengali digits: ০১৭১২৩৪৫৬৭৮
            r'[০-৯]{11}',       # 11 Bengali digits
        ]
        has_phone_number = any(re.search(pattern, full_text) for pattern in phone_patterns)
        
        # Website/social media link patterns
        link_keywords = [
            "www.", ".com", ".net", ".org", ".bd", "http", "https",
            "facebook.com", "fb.com", "fb.me", "instagram.com", "youtube.com",
            "whatsapp", "telegram", "viber", "imo", "messenger"
        ]
        has_link = any(keyword in full_text_lower for keyword in link_keywords)
        
        promo_keywords = [
            # Sale/Purchase
            "buy", "sale", "sell", "discount", "offer", "deal", "price", "tk", "taka",
            "free", "shipping", "delivery", "order", "purchase", "limited", "hurry",
            # Contact
            "call", "contact", "visit", "whatsapp", "inbox", "dm", "message", "chat",
            "phone", "mobile", "number", "reach", "connect",
            # Authenticity claims
            "original", "authentic", "genuine", "warranty", "guarantee", "certified",
            "100%", "best", "top", "quality", "premium", "exclusive",
            # Bengali common (transliterated)
            "bikroy", "kena", "dam", "booking", "advance", "jomi", "land", "plot", "flat", "rent"
        ]
        
        # Seller/Business indicators (company names, house, store, shop, etc.)
        business_indicators = [
            "house", "store", "shop", "enterprise", "company", "limited",
            "ltd", "inc", "corp", "corporation", "business", "trading",
            "mart", "center", "centre", "suppliers", "solutions", "services",
            "engineering", "technologies", "group", "international",
            "zone", "plaza", "market", "bazar", "outlet", "showroom"
        ]
        
        # Check for seller/business names (e.g., "Mobile Zone")
        words_in_text = full_text_lower.split()
        has_business_name = any(indicator in full_text_lower for indicator in business_indicators)
        
        # If text has business indicators + it's overlaid on image = promotional
        # More lenient: allow even single word + indicator (e.g., "MOBILE" + "ZONE")
        is_seller_branding = has_business_name and len(words_in_text) >= 1 and len(words_in_text) <= 8
        
        # Count promotional keywords
        promo_count = sum(1 for keyword in promo_keywords if keyword in full_text_lower)
        promo_found = promo_count >= 2  # At least 2 promotional keywords
        
        # Promotional confidence (0.0 to 1.0)
        promo_confidence = 0.0
        if has_phone_number or has_link:
            promo_confidence = 0.95  # Phone/link = clear promotional intent
        elif is_seller_branding:
            promo_confidence = 0.85  # Business name overlay is strong promotional signal (increased)
        elif promo_count >= 3:
            promo_confidence = 0.95  # Many promo keywords (increased)
        elif promo_count >= 2:
            promo_confidence = 0.75  # 2 keywords (increased)
        elif promo_count == 1:
            promo_confidence = 0.4   # Even 1 keyword is suspicious (increased)
        
        # OCR RISK SCORE (weighted)
        ocr_risk = watermark_confidence * 0.6 + promo_confidence * 0.4
        
        return {
            "text_found": len(all_text) > 0,
            "text_count": len(all_text),
            "full_text": full_text,
            "extracted_data": extracted_data,
            # Rule-based detection (HIGH CONFIDENCE)
            "watermark_detected": watermark_found or repetitive_watermark or bd_watermark_found,
            "watermark_confidence": watermark_confidence,
            "watermark_keywords_found": watermark_found or bd_watermark_found,
            "bd_marketplace_watermark": bd_watermark_found,
            "repetitive_text": repetitive_watermark,
            "max_word_repetition": max_repetition,
            "text_coverage_percent": text_coverage,
            "promotional_detected": promo_found or is_seller_branding or has_phone_number or has_link,
            "promotional_confidence": promo_confidence,
            "promo_keyword_count": promo_count,
            "seller_branding_detected": is_seller_branding,
            "has_phone_number": has_phone_number,
            "has_link": has_link,
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
