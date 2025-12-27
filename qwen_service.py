"""
Qwen2-VL Service for detailed image moderation:
- Final moderation decision
- Detailed explanations
- Dispute resolution with reasoning
"""

import torch
from transformers import Qwen2VLForConditionalGeneration, AutoProcessor
from PIL import Image
from typing import Dict, Optional
import json


class Qwen2VLService:
    def __init__(self, model_name: str = "Qwen/Qwen2-VL-7B-Instruct"):
        """Initialize Qwen2-VL model and processor"""
        print(f"Loading Qwen2-VL model: {model_name}")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Load model with appropriate settings
        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.float16 if self.device == "cuda" else torch.float32,
            device_map="auto" if self.device == "cuda" else None,
            trust_remote_code=True
        )
        
        if self.device == "cpu":
            self.model = self.model.to(self.device)
        
        self.processor = AutoProcessor.from_pretrained(
            model_name,
            trust_remote_code=True
        )
        
        print(f"Qwen2-VL model loaded on {self.device}")
    
    def moderate_image(self, image: Image.Image, clip_analysis: Optional[Dict] = None) -> Dict:
        """
        Final moderation decision with detailed explanation
        
        Args:
            image: PIL Image to moderate
            clip_analysis: Optional CLIP analysis results for context
        """
        # Prepare moderation prompt
        context = ""
        if clip_analysis:
            risk_level = clip_analysis.get("risk_analysis", {}).get("risk_level", "unknown")
            top_category = clip_analysis.get("category_analysis", {}).get("top_category", "unknown")
            context = f"\nPreliminary analysis suggests: Category={top_category}, Risk={risk_level}."
        
        prompt = f"""Analyze this image for content moderation. Provide:
1. A clear APPROVE or REJECT decision
2. Detailed explanation of your decision
3. List any policy violations or concerns
4. Confidence level (0-100){context}

Respond in JSON format:
{{
    "decision": "APPROVE/REJECT",
    "confidence": 85,
    "explanation": "detailed explanation here",
    "violations": ["list of violations if any"],
    "categories_detected": ["category1", "category2"],
    "recommended_action": "action recommendation"
}}"""
        
        # Prepare conversation format for Qwen2-VL
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
        
        # Process and generate
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.processor(
            text=[text],
            images=[image],
            return_tensors="pt",
            padding=True
        )
        
        # Move inputs to device
        inputs = {k: v.to(self.device) if isinstance(v, torch.Tensor) else v 
                 for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                top_p=0.9
            )
        
        response = self.processor.decode(outputs[0], skip_special_tokens=True)
        
        # Parse response
        try:
            # Extract JSON from response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
            else:
                # Fallback if JSON parsing fails
                result = {
                    "decision": "REJECT" if "reject" in response.lower() else "APPROVE",
                    "confidence": 50,
                    "explanation": response,
                    "violations": [],
                    "categories_detected": [],
                    "recommended_action": "manual review recommended"
                }
        except json.JSONDecodeError:
            result = {
                "decision": "REJECT",
                "confidence": 50,
                "explanation": response,
                "violations": ["parsing_error"],
                "categories_detected": [],
                "recommended_action": "manual review required"
            }
        
        return result
    
    def explain_decision(self, image: Image.Image, specific_question: str) -> Dict:
        """
        Provide detailed explanation for a specific question about the image
        """
        prompt = f"""Question about this image: {specific_question}

Provide a detailed, factual explanation addressing the question. Be specific and thorough."""
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
        
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.processor(
            text=[text],
            images=[image],
            return_tensors="pt",
            padding=True
        )
        
        inputs = {k: v.to(self.device) if isinstance(v, torch.Tensor) else v 
                 for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                top_p=0.9
            )
        
        explanation = self.processor.decode(outputs[0], skip_special_tokens=True)
        
        return {
            "question": specific_question,
            "explanation": explanation
        }
    
    def resolve_dispute(
        self,
        image: Image.Image,
        initial_decision: str,
        dispute_reason: str,
        clip_analysis: Optional[Dict] = None
    ) -> Dict:
        """
        Review a disputed moderation decision
        """
        context = ""
        if clip_analysis:
            context = f"\nCLIP Analysis Context: {json.dumps(clip_analysis, indent=2)}"
        
        prompt = f"""This image was initially {initial_decision} by our system.
User dispute reason: {dispute_reason}{context}

Please review this dispute and provide:
1. Whether to UPHOLD or OVERTURN the original decision
2. Final decision (APPROVE or REJECT)
3. Detailed reasoning for the dispute resolution
4. Any additional recommendations

Respond in JSON format:
{{
    "dispute_resolution": "UPHOLD/OVERTURN",
    "final_decision": "APPROVE/REJECT",
    "confidence": 85,
    "reasoning": "detailed reasoning",
    "additional_recommendations": "any recommendations"
}}"""
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
        
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.processor(
            text=[text],
            images=[image],
            return_tensors="pt",
            padding=True
        )
        
        inputs = {k: v.to(self.device) if isinstance(v, torch.Tensor) else v 
                 for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=512,
                temperature=0.7,
                top_p=0.9
            )
        
        response = self.processor.decode(outputs[0], skip_special_tokens=True)
        
        # Parse response
        try:
            json_start = response.find('{')
            json_end = response.rfind('}') + 1
            if json_start != -1 and json_end > json_start:
                result = json.loads(response[json_start:json_end])
            else:
                result = {
                    "dispute_resolution": "OVERTURN",
                    "final_decision": "APPROVE" if initial_decision == "REJECT" else "REJECT",
                    "confidence": 50,
                    "reasoning": response,
                    "additional_recommendations": "manual review recommended"
                }
        except json.JSONDecodeError:
            result = {
                "dispute_resolution": "OVERTURN",
                "final_decision": "APPROVE",
                "confidence": 50,
                "reasoning": response,
                "additional_recommendations": "manual review required due to parsing error"
            }
        
        return result
    
    def generate_description(self, image: Image.Image) -> str:
        """Generate a detailed description of the image"""
        prompt = "Describe this image in detail. Include what you see, the setting, any text present, and notable features."
        
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt}
                ]
            }
        ]
        
        text = self.processor.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        inputs = self.processor(
            text=[text],
            images=[image],
            return_tensors="pt",
            padding=True
        )
        
        inputs = {k: v.to(self.device) if isinstance(v, torch.Tensor) else v 
                 for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=256,
                temperature=0.7,
                top_p=0.9
            )
        
        description = self.processor.decode(outputs[0], skip_special_tokens=True)
        
        return description
