"""
CLIP Service for fast image analysis:
- Category & risk scoring
- Brand/logo similarity
- Promo banner detection
"""

import torch
from transformers import CLIPProcessor, CLIPModel
from PIL import Image
import numpy as np
from typing import List, Dict, Tuple


class CLIPService:
    def __init__(self, model_name: str = "openai/clip-vit-base-patch32"):
        """Initialize CLIP model and processor"""
        print(f"Loading CLIP model: {model_name}")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self.model = CLIPModel.from_pretrained(model_name).to(self.device)
        self.processor = CLIPProcessor.from_pretrained(model_name)
        print(f"CLIP model loaded on {self.device}")
        
        # Define categories for classification
        self.categories = [
            "product photo",
            "person or people",
            "landscape or nature",
            "food or beverage",
            "technology or electronics",
            "fashion or clothing",
            "interior design",
            "vehicle or transportation",
            "art or illustration",
            "text or document"
        ]
        
        # Define risk categories
        self.risk_categories = [
            "safe content",
            "inappropriate content",
            "violent content",
            "adult content",
            "disturbing content",
            "graphic content"
        ]
        
        # Promo banner indicators
        self.promo_indicators = [
            "promotional banner",
            "advertisement banner",
            "sale banner",
            "discount banner",
            "marketing banner",
            "regular photo without banner"
        ]
    
    def analyze_image(self, image: Image.Image) -> Dict:
        """Comprehensive image analysis using CLIP"""
        category_scores = self.get_category_scores(image)
        risk_scores = self.get_risk_scores(image)
        promo_scores = self.detect_promo_banner(image)
        
        return {
            "category_analysis": category_scores,
            "risk_analysis": risk_scores,
            "promo_analysis": promo_scores
        }
    
    def get_category_scores(self, image: Image.Image) -> Dict:
        """Get category scores for the image"""
        inputs = self.processor(
            text=self.categories,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)[0]
        
        scores = {cat: float(prob) for cat, prob in zip(self.categories, probs)}
        top_category = max(scores, key=scores.get)
        
        return {
            "scores": scores,
            "top_category": top_category,
            "confidence": scores[top_category]
        }
    
    def get_risk_scores(self, image: Image.Image) -> Dict:
        """Assess content risk using CLIP"""
        inputs = self.processor(
            text=self.risk_categories,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)[0]
        
        scores = {cat: float(prob) for cat, prob in zip(self.risk_categories, probs)}
        risk_level = "high" if scores["safe content"] < 0.5 else "low"
        
        return {
            "scores": scores,
            "risk_level": risk_level,
            "safe_content_score": scores["safe content"]
        }
    
    def detect_promo_banner(self, image: Image.Image) -> Dict:
        """Detect if image contains promotional banner"""
        inputs = self.processor(
            text=self.promo_indicators,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)[0]
        
        scores = {ind: float(prob) for ind, prob in zip(self.promo_indicators, probs)}
        is_promo = scores["regular photo without banner"] < 0.5
        
        return {
            "scores": scores,
            "is_promotional": is_promo,
            "confidence": 1.0 - scores["regular photo without banner"]
        }
    
    def compare_brand_similarity(self, image1: Image.Image, image2: Image.Image) -> Dict:
        """Compare two images for brand/logo similarity"""
        inputs = self.processor(
            images=[image1, image2],
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            image_features = self.model.get_image_features(**inputs)
            # Normalize features
            image_features = image_features / image_features.norm(dim=-1, keepdim=True)
            
            # Calculate cosine similarity
            similarity = torch.mm(image_features, image_features.t())
            similarity_score = float(similarity[0, 1])
        
        return {
            "similarity_score": similarity_score,
            "is_similar": similarity_score > 0.85,
            "confidence": abs(similarity_score)
        }
    
    def compare_with_text(self, image: Image.Image, text_descriptions: List[str]) -> Dict:
        """Compare image with text descriptions (useful for brand matching)"""
        inputs = self.processor(
            text=text_descriptions,
            images=image,
            return_tensors="pt",
            padding=True
        ).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(**inputs)
            logits_per_image = outputs.logits_per_image
            probs = logits_per_image.softmax(dim=1)[0]
        
        scores = {text: float(prob) for text, prob in zip(text_descriptions, probs)}
        best_match = max(scores, key=scores.get)
        
        return {
            "scores": scores,
            "best_match": best_match,
            "confidence": scores[best_match]
        }
