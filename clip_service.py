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
                "Computer » PC & Laptop » Laptop",
                "Computer » PC & Laptop » Used Laptop",
                "Computer » PC & Laptop » PC Builder",
                "Computer » PC & Laptop » Desktop PC",
                "Computer » PC & Laptop » Mini PC",
                "Computer » PC & Laptop » Graphics Tablet",
                "Computer » PC & Laptop » Signature Pad",
                "Computer » PC & Laptop » Stylus Pen",
                "Computer » PC & Laptop » Tablet",
                "Computer » PC & Laptop » Server",
                "Computer » PC & Laptop » Server Rack",
                "Computer » PC & Laptop » Computer Repair",

                "Computer » PC Parts » Processor",
                "Computer » PC Parts » Motherboard",
                "Computer » PC Parts » RAM",
                "Computer » PC Parts » Hard Disk",
                "Computer » PC Parts » SSD",
                "Computer » PC Parts » Graphics Card",
                "Computer » PC Parts » Mouse",
                "Computer » PC Parts » Keyboard",
                "Computer » PC Parts » DVD Writer",
                "Computer » PC Parts » Computer Casing",
                "Computer » PC Parts » CPU Cooler",
                "Computer » PC Parts » Internet Modem",
                "Computer » PC Parts » Webcam",
                "Computer » PC Parts » TV Card",
                "Computer » PC Parts » Pendrive",
                "Computer » PC Parts » PC Cable",
                "Computer » PC Parts » Power Supply",
                "Computer » PC Parts » USB Hub",
                "Computer » PC Parts » Card Reader",
                "Computer » PC Parts » Blank Disk",
                "Computer » PC Parts » Sound Card",
                "Computer » PC Parts » Thermal Paste",
                "Computer » PC Parts » Mouse Pad",

                "Computer » Laptop Accessories » Laptop Battery",
                "Computer » Laptop Accessories » Laptop Charger",
                "Computer » Laptop Accessories » Laptop Bag",
                "Computer » Laptop Accessories » Laptop Cooler",
                "Computer » Laptop Accessories » Laptop Display",
                "Computer » Laptop Accessories » Laptop Keyboard",
                "Computer » Laptop Accessories » Laptop Table",

                "Computer » Networking » Router",
                "Computer » Networking » Wireless Access Point",
                "Computer » Networking » Radio Link",
                "Computer » Networking » WiFi Repeater",
                "Computer » Networking » Network Switch",
                "Computer » Networking » WiFi Adapter",
                "Computer » Networking » Network Storage",
                "Computer » Networking » Patch Panel",
                "Computer » Networking » Network Cable",
                "Computer » Networking » Crimping Tool",
                "Computer » Networking » HDMI Extender",
                "Computer » Networking » Cable Tester",
                "Computer » Networking » RJ45 Connector",
                "Computer » Networking » Splicer Machine",
                "Computer » Networking » Wireless Antenna",
                "Computer » Networking » Media Converter",
                "Computer » Networking » KVM Switch",
                "Computer » Networking » Face Plate",
                "Computer » Networking » Networking Accessories",
                "Computer » Networking » Network Support",

                "Computer » Projection » Projector",
                "Computer » Projection » Digital Whiteboard",
                "Computer » Projection » Projector Screen",
                "Computer » Projection » Projector Mount",
                "Computer » Projection » Projector Lamp",
                "Computer » Projection » Wireless Presenter",
                "Computer » Projection » Projector Repair",
                "Computer » Projection » Projector Rental",
                "Computer » Projection » Projector Accessories",

                "Computer » Monitor » Monitor",

                "Computer » Print & Scan » Photocopier",
                "Computer » Print & Scan » Printer",
                "Computer » Print & Scan » Scanner",
                "Computer » Print & Scan » Banner Printer",
                "Computer » Print & Scan » POS Printer",
                "Computer » Print & Scan » POS Machine",
                "Computer » Print & Scan » Barcode Printer",
                "Computer » Print & Scan » Barcode Scanner",
                "Computer » Print & Scan » ID Card Printer",
                "Computer » Print & Scan » Digital Duplicator",
                "Computer » Print & Scan » Cartridge",
                "Computer » Print & Scan » Thermal Paper Roll",
                "Computer » Print & Scan » PVC Card",
                "Computer » Print & Scan » Printer Paper",
                "Computer » Print & Scan » Printer Parts",
                "Computer » Print & Scan » Copier Repair",
                "Computer » Print & Scan » Printer Repair",
                "Computer » Print & Scan » Copier Parts",
                "Computer » Print & Scan » Printing Accessories",

                "Computer » Office Electronics » Paper Shredder",
                "Computer » Office Electronics » Money Counting Machine",
                "Computer » Office Electronics » Cash Register",
                "Computer » Office Electronics » Cash Drawer",
                "Computer » Office Electronics » Fake Note Detector",
                "Computer » Office Electronics » Laminating Machine",
                "Computer » Office Electronics » Spiral Binding Machine",
                "Computer » Office Electronics » Paper Cutting Machine",

                "Computer » Software » Antivirus",
                "Computer » Software » App Development",
                "Computer » Software » Business Software",
                "Computer » Software » POS Software",
                "Computer » Software » Inventory Software",
                "Computer » Software » Accounting Software",
                "Computer » Software » e-Commerce Website",
                "Computer » Software » Microsoft Office",
                "Computer » Software » Educational Software",
                "Computer » Software » Microsoft Windows",

                "Computer » Web Service » Web Hosting",
                "Computer » Web Service » Domain Name",

                "Computer » Digital Marketing » Digital Display",
                "Computer » Digital Marketing » Digital Marketing Service",
                "Computer » Digital Marketing » LED Sign Board",

                "More » Everything Else » Online Media",
                "More » Everything Else » Everything Else"
            ]

        
        # Define risk categories (NEW REQUIREMENTS)
        self.risk_categories = [
            "safe general content",
            "promotional advertisement",
            "weapons or firearms",
            "medical drugs or substances",
            "financial stock trading",
            "violent or graphic content"
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
        """
        Assess content risk using CLIP
        Returns max risk score from: promo/weapon/medical/stock categories
        Threshold: risk >= 0.70 requires escalation
        """
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
        
        # Determine action based on threshold
        requires_escalation = max_risk_score >= 0.70
        
        return {
            "scores": scores,
            "risk_scores": risk_scores,
            "max_risk": max_risk_score,
            "max_risk_category": max_risk_category,
            "safe_score": scores["safe general content"],
            "requires_escalation": requires_escalation,
            "action": "ESCALATE_TO_QWEN2B" if requires_escalation else "APPROVE"
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
