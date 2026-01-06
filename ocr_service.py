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
        
        return {
            "text_found": len(all_text) > 0,
            "text_count": len(all_text),
            "full_text": full_text,
            "extracted_data": extracted_data
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
