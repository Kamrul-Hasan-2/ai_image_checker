"""
CLIP Service - v2.0 OPTIMIZED
Visual analysis: illegal content, watermark, promotional detection
Removed: category matching, brand comparison (unused in hybrid system)
"""

import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image, ImageEnhance, ImageOps, ImageFilter
import numpy as np
from typing import List, Dict, Tuple
import cv2


class CLIPService:
    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        """Initialize CLIP model and processor"""
        print(f"Loading CLIP model: {model_name}")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.model.eval()  # Set to evaluation mode for better inference
        self.processor = CLIPProcessor.from_pretrained(model_name)
        print(f"CLIP model loaded on {self.device}")
        
        # Temperature scaling for better calibration
        self.temperature = 1.0
        
        # Illegal products list (ONLY truly dangerous items)
        self.illegal_products = [
            "real loaded gun firearm weapon", "real pistol handgun with trigger", 
            "real rifle assault weapon", "real shotgun firearm",
            "naked nude woman explicit content", "pornographic sexual explicit image",
            "nude adult explicit photo",
            "heroin drug narcotic substance", "cocaine drug powder",
            "yaba drug pills tablets", "marijuana cannabis drug"
        ]
        
        # Risk categories
        self.risk_categories = [
            "safe general content",
            "promotional advertisement",
            "weapons or firearms",
            "medical drugs or substances",
            "financial stock trading",
            "violent or graphic content"
        ]
        
        # AI-generated image indicators
        self.ai_indicators = [
            "real photograph taken with camera",
            "AI generated synthetic digital art image",
            "computer generated CGI artificial image",
            "photorealistic real world photograph"
        ]
        
    def _preprocess_for_text_detection(self, image: Image.Image) -> List[Image.Image]:
        """Generate 2 preprocessed versions for faster processing"""
        preprocessed = []
        preprocessed.append(image)
        # High contrast for text/watermarks
        enhancer = ImageEnhance.Contrast(image)
        high_contrast = enhancer.enhance(2.0)
        preprocessed.append(high_contrast)
        return preprocessed
    
    def _analyze_image_regions(self, image: Image.Image) -> List[Image.Image]:
        """Analyze 2 key regions for faster processing"""
        regions = []
        width, height = image.size
        regions.append(image)
        # Bottom region (most common watermark location)
        bottom_region = image.crop((0, int(height * 0.7), width, height))
        regions.append(bottom_region)
        return regions
    
    def verify_image_body_content(self, image: Image.Image, title: str, description: str) -> Dict:
        """Verify if image body content matches product title/description
        
        This checks if the image actually shows what it's supposed to show.
        For example: if title is "RAM Memory", image should show RAM hardware.
        This prevents promotional images from being misclassified as product images.
        
        Args:
            image: PIL Image to verify
            title: Product title (e.g., "SK Hynix 8GB RAM")
            description: Product description
            
        Returns:
            Dict with body_matches (bool) and confidence (float)
        """
        if not title and not description:
            return {"body_matches": False, "confidence": 0.0}
        
        # Convert image to RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Keep prompts short to avoid CLIP's 77 token limit
        # Extract first 5-6 words from title for compact prompt
        product_words = (title or description or "").split()[:6]
        product_text = " ".join(product_words).lower()
        
        # SHORT verification prompts (under 77 tokens total)
        verification_prompts = [
            f"photo of {product_text}",
            f"real {product_text}",
            "product photo on white background"
        ]
        
        # SHORT negative prompts
        negative_prompts = [
            "promotional ad with text",
            "marketing banner",
            "sale advertisement"
        ]
        
        all_prompts = verification_prompts + negative_prompts
        
        inputs = self.processor(
            text=all_prompts,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image / self.temperature
            probs = logits_per_image.softmax(dim=1)[0]
        
        # Calculate scores
        verification_scores = probs[:len(verification_prompts)]
        negative_scores = probs[len(verification_prompts):]
        
        avg_verification = verification_scores.mean().item()
        avg_negative = negative_scores.mean().item()
        
        # Body matches if verification score > negative score
        body_matches = avg_verification > avg_negative
        confidence = avg_verification - avg_negative
        
        return {
            "body_matches": body_matches,
            "confidence": max(0.0, confidence),
            "verification_score": avg_verification,
            "negative_score": avg_negative
        }
    
    def check_illegal_content(self, image: Image.Image) -> Dict:
        """Check if image contains illegal products with enhanced accuracy"""
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        inputs = self.processor(
            text=self.illegal_products,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image / self.temperature
            probs = logits_per_image.softmax(dim=1)[0]
        
        # Get top 3 scores for better accuracy
        top3_values, top3_indices = torch.topk(probs, k=min(3, len(probs)))
        max_score = top3_values[0].item()
        max_idx = top3_indices[0].item()
        illegal_product = self.illegal_products[max_idx]
        
        # Calculate confidence: check if top score is significantly higher than others
        confidence_gap = max_score - top3_values[1].item() if len(top3_values) > 1 else max_score
        is_confident = confidence_gap > 0.50  # Huge confidence gap required
        
        # Extremely rare - basically only for actual gun/adult photos
        # All normal products return 0
        if is_confident and max_score > 0.95:  # Near perfect with huge gap
            is_illegal = True
        else:
            is_illegal = False  # Default: always legal (99.9% of cases)
        
        return {
            "is_illegal": is_illegal,
            "illegal_product": illegal_product if is_illegal else None,
            "confidence": max_score,
            "confidence_gap": confidence_gap,
            "all_scores": {}
        }
    
    def check_watermark(self, image: Image.Image) -> Dict:
        """Check if image has website watermark using feature engineering"""
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Enhanced prompts focusing on visual features CLIP can see
        watermark_labels = [
            "photo with text overlay on image",
            "image with transparent text watermark",
            "photo with website logo overlay",
            "picture with text stamp",
            "clean photo without text overlay"
        ]
        
        max_watermark_score = 0
        max_clean_score = 0
        detection_count = 0
        
        # Strategy 1: Analyze preprocessed versions
        preprocessed_images = self._preprocess_for_text_detection(image)
        for prep_img in preprocessed_images:
            inputs = self.processor(
                text=watermark_labels,
                images=prep_img,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image / self.temperature
                probs = logits_per_image.softmax(dim=1)[0]
            
            # Get watermark and clean scores
            watermark_score = probs[:4].max().item()
            clean_score = probs[4].item()
            
            max_watermark_score = max(max_watermark_score, watermark_score)
            max_clean_score = max(max_clean_score, clean_score)
            
            # Count detections
            if watermark_score > 0.22:
                detection_count += 1
        
        # Strategy 2: Check specific regions (watermarks often in corners/bottom)
        regions = self._analyze_image_regions(image)
        for region in regions[1:]:  # Skip full image, already analyzed
            inputs = self.processor(
                text=watermark_labels,
                images=region,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image / self.temperature
                probs = logits_per_image.softmax(dim=1)[0]
            
            watermark_score = probs[:4].max().item()
            max_watermark_score = max(max_watermark_score, watermark_score)
            
            if watermark_score > 0.25:
                detection_count += 1
        
        # Decision logic: multiple signals increase confidence
        has_watermark = (
            max_watermark_score > 0.28 or  # High confidence single detection
            detection_count >= 2 or  # Multiple regions show watermark
            (max_watermark_score > 0.22 and max_watermark_score > max_clean_score * 1.3)  # Score significantly higher than clean
        )
        
        watermark_type = "website" if has_watermark else None
        
        return {
            "has_watermark": has_watermark,
            "watermark_type": watermark_type,
            "confidence": max_watermark_score,
            "detection_count": detection_count
        }
    
    def check_ai_generated(self, image: Image.Image) -> Dict:
        """
        Check if image is AI-generated using CLIP
        This is a preliminary check - Qwen2-VL does more detailed analysis
        """
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        inputs = self.processor(
            text=self.ai_indicators,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image / self.temperature
            probs = logits_per_image.softmax(dim=1)[0]
        
        # Scores for each indicator
        real_photo_score = probs[0].item()
        ai_generated_score = probs[1].item()
        cgi_score = probs[2].item()
        photorealistic_score = probs[3].item()
        
        # Combine AI indicators
        total_ai_score = ai_generated_score + cgi_score
        total_real_score = real_photo_score + photorealistic_score
        
        # Determine if likely AI-generated
        # Conservative threshold: only flag if strong AI indicators
        is_ai_generated = (
            total_ai_score > total_real_score and
            total_ai_score > 0.45  # Require high confidence
        )
        
        return {
            "is_ai_generated": is_ai_generated,
            "ai_confidence": total_ai_score,
            "real_confidence": total_real_score,
            "ai_score": ai_generated_score,
            "cgi_score": cgi_score,
            "real_photo_score": real_photo_score,
            "requires_qwen_review": total_ai_score > 0.30  # Lower threshold for escalation
        }
    
    def analyze_image(self, image: Image.Image) -> Dict:
        """Comprehensive image analysis using CLIP - OPTIMIZED"""
        risk_scores = self.get_risk_scores(image)
        promo_scores = self.detect_promo_banner(image)
        
        return {
            "risk_analysis": risk_scores,
            "promo_analysis": promo_scores,
            "illegal_check": self.check_illegal_content(image),
            "watermark_check": self.check_watermark(image),
            "ai_check": self.check_ai_generated(image)
        }
    
    def get_risk_scores(self, image: Image.Image) -> Dict:
        """
        Assess content risk using CLIP
        Returns max risk score from: promo/weapon/medical/stock categories
        Threshold: risk >= 0.55 requires escalation (lowered for better detection)
        """
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        inputs = self.processor(
            text=self.risk_categories,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image / self.temperature
            probs = logits_per_image.softmax(dim=1)[0]
        
        scores = {cat: float(prob) for cat, prob in zip(self.risk_categories, probs)}
        
        # Calculate max risk (excluding "safe general content")
        risk_scores = {
            "promo": scores["promotional advertisement"],
            "weapon": scores["weapons or firearms"],
            "medical": scores["medical drugs or substances"],
            "stock": scores["financial stock trading"],
            "violent": scores["violent or graphic content"]
        }
        
        max_risk_category = max(risk_scores, key=risk_scores.get)
        max_risk_score = risk_scores[max_risk_category]
        
        # More sensitive threshold: 0.55 instead of 0.70
        requires_escalation = max_risk_score >= 0.55
        
        # Calculate weighted risk level (0-100)
        weighted_risk = (
            risk_scores["promo"] * 30 +
            risk_scores["weapon"] * 100 +
            risk_scores["medical"] * 80 +
            risk_scores["stock"] * 70 +
            risk_scores["violent"] * 100
        )
        
        return {
            "scores": scores,
            "risk_scores": risk_scores,
            "max_risk": max_risk_score,
            "max_risk_category": max_risk_category,
            "weighted_risk_level": min(weighted_risk, 100),
            "safe_score": scores["safe general content"],
            "requires_escalation": requires_escalation,
            "action": "ESCALATE_TO_QWEN2B" if requires_escalation else "APPROVE"
        }
    
    def detect_product_photo(self, image: Image.Image) -> Dict:
        """Detect if image shows an actual product (not promotional banner)"""
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Enhanced labels to identify product photos (especially hardware/electronics)
        product_labels = [
            "product photo white background",
            "hardware component close-up",
            "electronics product packaging",
            "product on black background",
            "isolated product image",
            "promotional ad with text overlay",
            "marketing banner sale",
            "advertisement contact info"
        ]
        
        inputs = self.processor(
            text=product_labels,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image / self.temperature
            probs = logits_per_image.softmax(dim=1)[0]
        
        # Product photo indicators (first 5 labels)
        product_score = probs[:5].max().item()
        # Promotional indicators (last 3 labels)
        promo_score = probs[5:].max().item()
        
        # Determine if it's a product photo - lower threshold for better detection
        is_product_photo = product_score > promo_score and product_score > 0.25
        
        return {
            "is_product_photo": is_product_photo,
            "product_score": product_score,
            "promo_score": promo_score,
            "confidence": product_score if is_product_photo else promo_score
        }

    def detect_promo_banner(self, image: Image.Image) -> Dict:
        """Detect promotional content using advanced feature engineering"""
        # Convert image to RGB if needed
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Enhanced prompts focusing on visual promotional elements
        promo_labels = [
            "advertisement poster with sale text",
            "promotional banner with discount",
            "photo with contact information",
            "marketing flyer design",
            "seller advertisement image",
            "product photo without ads",
            "clean product image"
        ]
        
        max_promo_score = 0
        max_clean_score = 0
        promo_detection_count = 0
        
        # Strategy 1: Analyze with contrast enhancement (makes text pop)
        preprocessed_images = self._preprocess_for_text_detection(image)
        for prep_img in preprocessed_images:
            inputs = self.processor(
                text=promo_labels,
                images=prep_img,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image / self.temperature
                probs = logits_per_image.softmax(dim=1)[0]
            
            # Promo indicators vs clean product
            promo_score = probs[:5].max().item()
            clean_score = probs[5:].max().item()
            
            max_promo_score = max(max_promo_score, promo_score)
            max_clean_score = max(max_clean_score, clean_score)
            
            # Count strong detections
            if promo_score > 0.35:
                promo_detection_count += 1
        
        # Strategy 2: Check for text-heavy regions (promotional images have more text)
        regions = self._analyze_image_regions(image)
        text_region_scores = []
        
        for region in regions:
            # Use simpler prompt for region analysis
            region_labels = ["image with text overlay", "image without text"]
            inputs = self.processor(
                text=region_labels,
                images=region,
                return_tensors="pt",
                padding=True
            ).to(self.device)
            
            with torch.no_grad():
                outputs = self.model(**inputs)
                logits_per_image = outputs.logits_per_image / self.temperature
                probs = logits_per_image.softmax(dim=1)[0]
            
            text_region_scores.append(probs[0].item())
        
        # High text coverage suggests promotional content
        avg_text_score = sum(text_region_scores) / len(text_region_scores)
        has_high_text_coverage = avg_text_score > 0.5
        
        # Decision logic: combine multiple signals
        is_promotional = (
            max_promo_score > 0.42 or  # High confidence detection
            promo_detection_count >= 2 or  # Multiple preprocessed versions detect promo
            (max_promo_score > 0.35 and has_high_text_coverage) or  # Moderate score + text overlay
            (max_promo_score > max_clean_score * 1.4 and max_promo_score > 0.30)  # Significantly more promo than clean
        )
        
        return {
            "is_promotional": is_promotional,
            "confidence": max_promo_score,
            "promo_score": max_promo_score,
            "clean_score": max_clean_score,
            "text_coverage": avg_text_score,
            "detection_count": promo_detection_count
        }

