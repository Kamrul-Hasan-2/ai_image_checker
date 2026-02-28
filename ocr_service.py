"""
EasyOCR Service for text extraction from images
Step 1 in the pipeline: Extract all text content
"""

import re
import easyocr
import cv2
import numpy as np
from PIL import Image
from typing import Dict, List, Tuple


class OCRService:
    def __init__(self, languages: List[str] = ['en'], model_storage_directory: str = None):
        """Initialize EasyOCR reader with optional model storage directory"""
        print(f"Loading EasyOCR model for languages: {languages}")
        
        if model_storage_directory:
            print(f"Using cached models from: {model_storage_directory}")
            self.reader = easyocr.Reader(
                languages,
                gpu=True,
                model_storage_directory=model_storage_directory,
                download_enabled=False
            )
        else:
            self.reader = easyocr.Reader(
                languages,
                gpu=True,
                model_storage_directory='/root/.cache/easyocr',
                download_enabled=True
            )
        
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
        
        # VISUAL FEATURE ANALYSIS (doesn't rely on OCR)
        # Detect button-like regions (e.g., "Buy Now" buttons)
        gray = cv2.cvtColor(img_array, cv2.COLOR_RGB2GRAY) if len(img_array.shape) == 3 else img_array
        edges = cv2.Canny(gray, 50, 150)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        # Count button-like rectangles (common in e-commerce)
        button_count = 0
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            aspect_ratio = w / h if h > 0 else 0
            area = w * h
            # Button characteristics: wide rectangles, medium size
            if 2.0 < aspect_ratio < 6.0 and 5000 < area < 50000:
                button_count += 1
        
        has_button_ui = button_count >= 2  # Multiple buttons = likely e-commerce
        
        # Analyze text density in different regions (prices often at bottom)
        bottom_region = gray[int(img_height * 0.6):, :]
        _, bottom_thresh = cv2.threshold(bottom_region, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        bottom_text_density = np.sum(bottom_thresh > 0) / (bottom_region.shape[0] * bottom_region.shape[1])
        has_bottom_text = bottom_text_density > 0.05  # Significant text at bottom
        
        # Convert RGB to BGR for OpenCV
        if len(img_array.shape) == 3 and img_array.shape[2] == 3:
            img_array = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
        
        # SINGLE PASS ONLY for speed - no enhancement
        results = self.reader.readtext(img_array, paragraph=False)
        
        # Use results as-is
        unique_results = results
        
        # CHARACTER-LEVEL ANALYSIS (detect digits and currency symbols)
        full_image_text = ''.join([text for (_, text, _) in unique_results])
        digit_count = sum(c.isdigit() for c in full_image_text)
        has_currency_symbol = any(c in full_image_text for c in ['₹', '₨', '$', '€', '৳'])
        has_comma_in_numbers = bool(re.search(r'\d,\d', full_image_text))
        
        # Strong price indicator: digits + currency OR comma in numbers (removed standalone digit count)
        strong_price_indicator = (
            (digit_count >= 3 and has_currency_symbol) or  # 3+ digits with currency
            has_comma_in_numbers  # Comma in numbers = formatted price (e.g., 24,999)
            # REMOVED: digit_count >= 6 (was flagging model numbers like "18000 BTU")
        )
        
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
        
        # SIMPLIFIED WATERMARK DETECTION (fewer keywords for speed)
        watermark_keywords = [
            "shutterstock", "getty", "istock", "watermark"
        ]
        
        # Bangladesh marketplace watermarks (HIGH PRIORITY)
        bd_marketplace_keywords = ["bikroy", "daraz"]
        
        # Check for watermark keywords (case-insensitive)
        watermark_found = any(keyword in full_text_lower for keyword in watermark_keywords)
        
        # Check for BD marketplace watermarks
        bd_watermark_found = any(keyword in full_text_lower for keyword in bd_marketplace_keywords)
        
        # SKIP word repetition check for speed
        max_repetition = 0
        repetitive_watermark = False
        
        # Calculate text coverage percentage
        text_coverage = (text_area / total_area) * 100 if total_area > 0 else 0
        
        # Watermark confidence (0.0 to 1.0)
        watermark_confidence = 0.0
        if bd_watermark_found:
            watermark_confidence = 0.99  # Bikroy/Daraz = definite watermark
        elif watermark_found:
            watermark_confidence = 0.95  # Other stock photo watermarks
            watermark_confidence = 0.90  # Repeated text + coverage (lowered threshold more)
        elif text_coverage > 15:
            watermark_confidence = 0.75  # Medium text coverage suggests overlay (lowered)
        elif len(all_text) > 5 and text_coverage > 10:
            watermark_confidence = 0.65  # Many text elements suggest watermark
        
        # RULE-BASED PROMOTIONAL TEXT DETECTION
        # Phone number patterns (English and Bengali digits) - ENHANCED
        phone_patterns = [
            r'\+?88[0-9]{11}',  # Bangladesh: +8801712345678
            r'\+?৮৮[০-৯]{11}',  # Bangladesh Bengali: +৮৮০১৭১২৩৪৫৬৭৮
            r'01[0-9]{9}',      # Mobile: 01712345678
            r'০১[০-৯]{9}',      # Bengali mobile: ০১৭১২৩৪৫৬৭৮
            r'[0-9]{3}[-.\\s_:,]?[0-9]{3,4}[-.\\s_:,]?[0-9]{2}[-.\\s_:,]?[0-9]{2}',  # With separators
            r'[০-৯]{3}[-.\\s_:,]?[০-৯]{3,4}[-.\\s_:,]?[০-৯]{2}[-.\\s_:,]?[০-৯]{2}',  # Bengali with separators
            r'[০-৯]{11}',       # 11 Bengali digits
            r'[০-৯]{10}',       # 10 Bengali digits
            r'[0-9]{10,11}',    # Simple 10-11 digit sequence
            r'[0-9]{4}[-\s][0-9]{6}',  # Format: 1234-567890 or 1234 567890
            r'[০-৯]{4}[-\s][০-৯]{6}',  # Bengali format
            r'মোবাইল.*[০-৯০1]{10,11}',  # Bengali "mobile" with numbers
            r'ফোন.*[০-৯০1]{10,11}',    # Bengali "phone" with numbers
            r'mobile.*[০-৯০1]{10,11}',  # English "mobile" mixed
            r'phone.*[০-৯০1]{10,11}',   # English "phone" mixed
        ]
        has_phone_number = any(re.search(pattern, full_text, re.IGNORECASE) for pattern in phone_patterns)
        
        # Price patterns (detect prices in multiple formats)
        price_patterns = [
            # Indian rupee format (lakhs): ₹1,03,155 or Rs.1,03,155
            r'[₹₨Rs\.]\s*[0-9]{1,3},[0-9]{2},[0-9]{3}',  # Indian lakh: ₹1,03,155
            r'[₹₨Rs\.]\s*[0-9]{1,2},[0-9]{2},[0-9]{2},[0-9]{3}',  # Indian crore: ₹1,25,00,000
            r'[₹₨Rs\.]\s*[0-9]{1,3},[0-9]{3}',  # Standard: ₹24,999
            r'[₹₨Rs\.]\s*[0-9]{3,7}',  # Without comma: ₹24999 (3+ digits)
            # Standard format
            r'[0-9]{1,3},[0-9]{2},[0-9]{3}',  # Indian lakh without symbol: 1,03,155
            r'[0-9]{1,3},[0-9]{3}',  # Standard: 24,999 or 1,999
            # Bangladesh taka
            r'[0-9]{3,6}\s*(tk|taka|৳)',  # e.g., 999 tk or 17999 tk
            r'(tk|taka|৳)\s*[0-9]{3,6}',  # e.g., tk 999 or tk 17999
            # Price keywords
            r'price[:\s]*[0-9,]+',  # price: 1,03,155
            r'(rs|rupees?)[.\s]*[0-9,]+',  # Rs. 103155 or rupees 103155
            # Fallback: any large number with comma (likely price)
            r'[0-9]{2,3},[0-9]{3,5}',  # Any comma-separated number
            # Standalone numbers that look like prices (3+ digits)
            r'\b[0-9]{3,7}\b',  # Any 3-7 digit number standalone
        ]
        has_price = any(re.search(pattern, full_text, re.IGNORECASE) for pattern in price_patterns)
        
        # FALLBACK: Use strong indicators if OCR missed the exact pattern
        if not has_price and strong_price_indicator:
            has_price = True
        
        # Website/social media link patterns
        link_keywords = [
            "www.", ".com", ".net", ".org", ".bd", "http", "https",
            "facebook.com", "fb.com", "fb.me", "instagram.com", "youtube.com",
            "whatsapp", "telegram", "viber", "imo", "messenger"
        ]
        has_link = any(keyword in full_text_lower for keyword in link_keywords)
        
        promo_keywords = [
            # Sale/Purchase - STRONG indicators only
            "buy", "sale", "sell", "discount", "offer", "deal", "price",
            "free shipping", "delivery", "order now", "purchase", "limited", "hurry",
            "save", "off %", "% off", "today only", "special offer",
            # E-commerce specific
            "buy now", "shop now", "shopping", "add to cart", "checkout",
            # Contact/Reach out
            "call now", "contact us", "visit us", "inbox", "dm", "message us",
            "whatsapp us", "reach us",
            # Bengali marketplace
            "bikroy", "kena", "dam", "booking", "advance"
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
        promo_found = promo_count >= 1  # At least 1 promotional keyword (lowered from 2)
        
        # Additional promotional indicators
        sale_terms = ["sale", "offer", "discount", "save", "off", "deal", "limited"]
        has_sale_terms = any(term in full_text_lower for term in sale_terms)
        
        # E-commerce UI indicators (Buy Now, Add to Cart, etc.)
        ecommerce_ui_terms = ["buy now", "shop now", "add to cart", "checkout", "order now"]
        has_ecommerce_ui = any(term in full_text_lower for term in ecommerce_ui_terms)
        
        # DETECT PRODUCT TEXT vs PROMOTIONAL TEXT
        # Product text characteristics:
        # - Part of the product (brand names, model numbers, specs on device)
        # - Usually centered, small text areas, integrated into product
        # - No prices, phone numbers, or contact info
        # - Technical specs without "buy/sale" context
        # - Often in product color/design (black text on black product)
        
        # Analyze text spatial distribution (product text is usually centered on product)
        text_positions = []
        text_sizes = []
        for (bbox, text, confidence) in unique_results:
            bbox_array = np.array(bbox)
            center_x = np.mean(bbox_array[:, 0])
            center_y = np.mean(bbox_array[:, 1])
            width = np.max(bbox_array[:, 0]) - np.min(bbox_array[:, 0])
            height = np.max(bbox_array[:, 1]) - np.min(bbox_array[:, 1])
            
            text_positions.append((center_x / img_width, center_y / img_height))
            text_sizes.append(width * height)
        
        # Product text is typically:
        # 1. Centered in image (product photo centered)
        # 2. Small relative to image size
        # 3. Not concentrated at edges/corners (where overlay text usually is)
        is_centered_text = False
        is_small_text = False
        is_not_corner_text = True
        
        if text_positions:
            avg_x = np.mean([pos[0] for pos in text_positions])
            avg_y = np.mean([pos[1] for pos in text_positions])
            
            # Centered: between 0.3-0.7 in both x and y
            is_centered_text = 0.25 < avg_x < 0.75 and 0.25 < avg_y < 0.75
            
            # Small text: average text size < 3% of image area
            avg_text_size = np.mean(text_sizes) if text_sizes else 0
            is_small_text = avg_text_size < (total_area * 0.03)
            
            # Check if text is at corners/edges (promotional overlay pattern)
            corner_text_count = sum(1 for pos in text_positions 
                                   if (pos[0] < 0.15 or pos[0] > 0.85) or 
                                      (pos[1] < 0.15 or pos[1] > 0.85))
            is_not_corner_text = corner_text_count < len(text_positions) * 0.5
        
        # Product-specific text patterns (brand names, model numbers, specs)
        product_text_patterns = [
            # Brand/model indicators
            r'\b[A-Z][a-z]+\s+[A-Z0-9]+',  # Brand Model (e.g., Canon 600D)
            r'\b[0-9]{2,5}[A-Z]{1,3}\b',  # Model numbers (e.g., 600D, 18000BTU)
            r'\b[A-Z]{2,10}\b',  # Brand names in caps (e.g., INSULATING, CANON)
            # Measurements/specs on product
            r'\d+\s*(mm|cm|inch|ml|kg|w|v|hz|btu|rpm)',  # 14mm, 18000 BTU
            r'\d+x\d+',  # Dimensions: 10x14
            # Product features
            r'\b(pro|plus|max|ultra|mini|lite)\b',
        ]
        
        has_product_pattern = any(re.search(pattern, full_text, re.IGNORECASE) 
                                 for pattern in product_text_patterns)
        
        # SIMPLIFIED: If no price, phone, or link + no strong sale terms = product text
        is_product_text_only = False
        if not has_phone_number and not has_link and not has_price and not has_ecommerce_ui:
            # No clear promotional signals
            # If there's text but no promotional intent, likely product branding
            if len(all_text) > 0:
                # Must NOT have strong sale terms
                strong_sale_terms = ["buy now", "call now", "order now", "sale", "discount", "offer", 
                                    "shop now", "visit us", "contact", "inbox", "dm us", "whatsapp"]
                has_strong_sale = any(term in full_text_lower for term in strong_sale_terms)
                
                if not has_strong_sale:
                    # Additional checks for product text
                    # Product text is usually: centered + small OR has product patterns
                    product_text_confidence = 0
                    
                    if is_centered_text:
                        product_text_confidence += 1
                    if is_small_text:
                        product_text_confidence += 1
                    if is_not_corner_text:
                        product_text_confidence += 1
                    if has_product_pattern:
                        product_text_confidence += 2
                    if len(all_text) <= 5:  # Few text elements = likely product branding
                        product_text_confidence += 1
                    if len(all_text) <= 10 and text_coverage < 10:  # Low text coverage
                        product_text_confidence += 1
                    
                    # If confidence >= 2 (LOWERED from 3), it's product text
                    # This catches more genuine product text cases
                    if product_text_confidence >= 2:
                        is_product_text_only = True
        
        # DETECT PROMOTIONAL STICKERS on products (orange/colorful stickers with text)
        # These are often missed because the product is real, but the sticker is promotional
        has_promotional_sticker = False
        if len(all_text) > 0 and text_coverage < 20:  # Moderate text coverage (not full overlay)
            # Check if text contains business name + contact info pattern
            # Common pattern: "STORE NAME" + text on a sticker (usually colorful background)
            if has_business_name and (has_phone_number or has_price or has_link):
                # Business name + contact = likely promotional sticker
                has_promotional_sticker = True
            # Also check for concentrated text in one area (typical of stickers)
            elif len(text_positions) >= 2:
                # Check if text is clustered in one region (sticker pattern)
                x_positions = [pos[0] for pos in text_positions]
                y_positions = [pos[1] for pos in text_positions]
                x_std = np.std(x_positions)
                y_std = np.std(y_positions)
                # Low standard deviation = clustered text = likely sticker
                is_clustered = x_std < 0.2 and y_std < 0.2
                if is_clustered and has_business_name:
                    has_promotional_sticker = True
        
        # MULTI-SIGNAL PROMOTIONAL CONFIDENCE (0.0 to 1.0)
        promo_confidence = 0.0
        visual_promo_score = 0.0
        
        # SKIP promotional detection if it's only product text
        if is_product_text_only:
            promo_confidence = 0.0  # Not promotional - just product branding
        else:
            # Visual features boost confidence
            if has_button_ui:
                visual_promo_score += 0.4
            if has_bottom_text:
                visual_promo_score += 0.3
            if strong_price_indicator:
                visual_promo_score += 0.5
            if has_promotional_sticker:
                visual_promo_score += 0.6  # Promotional sticker on product
            
            # Text-based detection
            if has_phone_number or has_link:
                promo_confidence = 0.99  # Phone/link = clear promotional intent (raised)
            elif has_price or strong_price_indicator:
                promo_confidence = 0.98  # Price detected = promotional post (raised)
            elif has_ecommerce_ui and visual_promo_score > 0.3:
                promo_confidence = 0.90  # E-commerce UI + visual cues
            elif visual_promo_score >= 0.6:
                promo_confidence = 0.85  # Strong visual promotional indicators
            elif has_promotional_sticker:
                promo_confidence = 0.90  # Promotional sticker detected
            elif is_seller_branding:
                promo_confidence = 0.80  # Business name overlay
            elif promo_count >= 3:
                promo_confidence = 0.85  # Many promo keywords
            elif promo_count >= 2:
                promo_confidence = 0.70  # 2 keywords
            elif visual_promo_score >= 0.3:
                promo_confidence = 0.60  # Moderate visual cues
            elif promo_count == 1:
                promo_confidence = 0.35   # Single keyword
        
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
            "promotional_detected": False if is_product_text_only else (has_phone_number or has_link or has_price or has_ecommerce_ui),
            "promotional_confidence": promo_confidence,
            "promo_keyword_count": promo_count,
            "seller_branding_detected": is_seller_branding,
            "has_promotional_sticker": has_promotional_sticker,
            "has_phone_number": has_phone_number,
            "has_price": has_price,
            "has_link": has_link,
            "has_ecommerce_ui": has_ecommerce_ui,
            "is_product_text_only": is_product_text_only,
            "visual_promo_score": visual_promo_score,
            "strong_price_indicator": strong_price_indicator,
            "has_button_ui": has_button_ui,
            "digit_count": digit_count,
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
