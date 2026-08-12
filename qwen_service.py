"""
Qwen2-VL Service for detailed image moderation.

Two backends controlled by .env flags:
  USE_QWEN2VL=True   → local Qwen2-VL-2B model (GPU required)
  GROQ_API_KEY=...   → cloud Groq API with a vision-capable model (default: qwen3.6-27b)

When USE_QWEN2VL=False the local model is never loaded.
Groq is always available as a vision-capable path when a key is set.
"""

import os
import json
import base64
import io
from typing import Dict, Optional
from PIL import Image


# ---------------------------------------------------------------------------
# Read flags once at import time
# ---------------------------------------------------------------------------
def _env_bool(key: str, default: bool = False) -> bool:
    val = os.environ.get(key, str(default)).strip().lower()
    return val in ("1", "true", "yes")

USE_QWEN2VL  = _env_bool("USE_QWEN2VL", False)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY", "").strip()
# Llama 4 Scout was shut down by Groq on 2026-07-17. Default to Qwen 3.6 27B —
# the vision-capable replacement Groq recommends (the other option, gpt-oss-120b,
# is text-only and cannot see the image).
GROQ_MODEL   = os.environ.get("GROQ_MODEL", "qwen/qwen3.6-27b").strip()
# Plain-text lookups (e.g. known product weight) don't need a vision model —
# use a production-grade text model instead of the vision preview model.
GROQ_TEXT_MODEL = os.environ.get("GROQ_TEXT_MODEL", "llama-3.3-70b-versatile").strip()


# ---------------------------------------------------------------------------
# Groq client (lazy-initialised)
# ---------------------------------------------------------------------------
_groq_client = None

def _get_groq_client():
    global _groq_client
    if _groq_client is None:
        try:
            from groq import Groq
            _groq_client = Groq(api_key=GROQ_API_KEY)
        except ImportError:
            raise RuntimeError("groq package not installed. Run: pip install groq")
    return _groq_client



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _image_to_base64(image: Image.Image) -> str:
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=85)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


# ---------------------------------------------------------------------------
# Known product weight lookup (text-only — no image involved)
# ---------------------------------------------------------------------------
def estimate_known_product_weight_kg(
    title: str,
    category: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict:
    """
    Ask Groq for the manufacturer-published net product weight (kg) of a specific
    product model, from the model's own knowledge — no browsing, no external
    database. Used to sanity-check a seller-submitted shipping_weight.

    Returns {"known_weight_kg": float|None, "confidence": "high"/"medium"/"low", "_lookup_ok": bool}.
    _lookup_ok=False means the call/parse failed — callers must treat that as
    "unknown" and skip the check, never as a confirmed weight.
    """
    if not GROQ_API_KEY:
        return {"known_weight_kg": None, "confidence": "low", "_lookup_ok": False}

    context = f"Category: {category}\n" if category else ""
    if description:
        context += f"Description: {description}\n"

    prompt = f"""What is the manufacturer-published net product weight, in kilograms, of this exact product model (the device itself, NOT the shipping/box weight)?

Product title: {title}
{context}
If you know this specific model's published weight with reasonable confidence, return it. If the title is generic, ambiguous, or you don't reliably know the specific model's weight, return null for known_weight_kg — do not guess.

Respond ONLY with JSON (no markdown):
{{"known_weight_kg": 1.53, "confidence": "high/medium/low"}}"""

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model=GROQ_TEXT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=150,
            temperature=0.1,
        )
        raw = response.choices[0].message.content or ""
    except Exception as e:
        print(f"⚠️  Groq weight-lookup error: {e}")
        return {"known_weight_kg": None, "confidence": "low", "_lookup_ok": False}

    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        j_start = raw.find("{")
        j_end   = raw.rfind("}") + 1
        parsed = json.loads(raw[j_start:j_end]) if j_start != -1 else {}
    except json.JSONDecodeError:
        return {"known_weight_kg": None, "confidence": "low", "_lookup_ok": False}

    weight = parsed.get("known_weight_kg")
    if not isinstance(weight, (int, float)) or weight <= 0:
        weight = None

    return {
        "known_weight_kg": weight,
        "confidence": parsed.get("confidence", "low"),
        "_lookup_ok": True,
    }


# ---------------------------------------------------------------------------
# Groq-based moderation (vision via base64 — requires a vision-capable model)
# ---------------------------------------------------------------------------
def _groq_moderate(image: Image.Image, clip_analysis: Optional[Dict] = None) -> Dict:
    """Call Groq with a vision-capable model (Llama 4 Scout by default) for image moderation."""
    client = _get_groq_client()

    context = ""
    if clip_analysis:
        risk_level   = clip_analysis.get("risk_analysis", {}).get("risk_level", "unknown")
        top_category = clip_analysis.get("category_analysis", {}).get("top_category", "unknown")
        context = f"\nPreliminary analysis: Category={top_category}, Risk={risk_level}."

    img_b64 = _image_to_base64(image)

    prompt = f"""Analyze this product image for e-commerce content moderation.{context}

Check for:
1. Promotional/advertising overlays (prices, discounts, SALE text, brand watermarks)
2. Watermarks from websites (bikroy, daraz, shutterstock, bdstall, etc.)
3. Illegal content (real weapons, drugs, explicit adult content)
4. Image quality issues (blurry, screenshot, AI-generated artifacts)

Respond ONLY with valid JSON (no markdown):
{{
    "decision": "BLOCK/APPROVE/MANUAL_REVIEW",
    "confidence": 85,
    "explanation": "brief explanation",
    "violations": [],
    "is_promotional": false,
    "is_ai_generated": false,
    "has_watermark": false,
    "categories_detected": [],
    "recommended_action": "approve/block/review"
}}"""

    try:
        response = client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"},
                        },
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            max_tokens=512,
            temperature=0.3,
        )
        raw = response.choices[0].message.content or ""
    except Exception as e:
        raw = f'{{"decision":"APPROVE","confidence":50,"explanation":"Groq error: {str(e)[:100]}","violations":[],"is_promotional":false,"is_ai_generated":false,"has_watermark":false,"categories_detected":[],"recommended_action":"approve","_moderation_ok":false}}'

    # Parse JSON
    try:
        if "```json" in raw:
            raw = raw.split("```json")[1].split("```")[0].strip()
        elif "```" in raw:
            raw = raw.split("```")[1].split("```")[0].strip()
        j_start = raw.find("{")
        j_end   = raw.rfind("}") + 1
        return json.loads(raw[j_start:j_end]) if j_start != -1 else _fallback_result(raw)
    except json.JSONDecodeError:
        return _fallback_result(raw)


def _fallback_result(text: str) -> Dict:
    return {
        "decision": "APPROVE",
        "confidence": 50,
        "explanation": text[:200],
        "violations": [],
        "is_promotional": False,
        "is_ai_generated": False,
        "has_watermark": False,
        "categories_detected": [],
        "recommended_action": "manual review recommended",
        "_moderation_ok": False,  # the model call/parse failed — these fields are guesses, not a real verdict
    }


# ---------------------------------------------------------------------------
# Local Qwen2-VL service class
# ---------------------------------------------------------------------------
class Qwen2VLService:
    """
    Wraps the local Qwen2-VL model.
    Only instantiate when USE_QWEN2VL=True.
    """

    def __init__(self, model_name: str = "Qwen/Qwen2-VL-2B-Instruct"):
        if not USE_QWEN2VL:
            raise RuntimeError(
                "Qwen2-VL is disabled (USE_QWEN2VL=False in .env). "
                "Use GroqQwenService instead."
            )
        import torch
        from transformers import Qwen2VLForConditionalGeneration, AutoProcessor

        print(f"Loading Qwen2-VL model: {model_name}")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._torch = torch

        self.model = Qwen2VLForConditionalGeneration.from_pretrained(
            model_name,
            torch_dtype=torch.bfloat16 if self.device == "cuda" else torch.float32,
            device_map="cuda" if self.device == "cuda" else None,
            trust_remote_code=True,
        )
        if self.device == "cpu":
            self.model = self.model.to(self.device)

        self.processor = AutoProcessor.from_pretrained(model_name, trust_remote_code=True)
        print(f"Qwen2-VL model loaded on {self.device}")

    # ------------------------------------------------------------------
    def _run(self, messages, max_new_tokens: int = 512) -> str:
        text = self.processor.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True
        )
        images = [
            c["image"]
            for msg in messages
            for c in msg["content"]
            if isinstance(c, dict) and c.get("type") == "image"
        ]
        inputs = self.processor(
            text=[text], images=images, return_tensors="pt", padding=True
        )
        inputs = {
            k: v.to(self.device) if isinstance(v, self._torch.Tensor) else v
            for k, v in inputs.items()
        }
        with self._torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_new_tokens,
                temperature=0.7,
                top_p=0.9,
            )
        return self.processor.decode(outputs[0], skip_special_tokens=True)

    # ------------------------------------------------------------------
    def moderate_image(self, image: Image.Image, clip_analysis: Optional[Dict] = None) -> Dict:
        context = ""
        if clip_analysis:
            risk_level   = clip_analysis.get("risk_analysis", {}).get("risk_level", "unknown")
            top_category = clip_analysis.get("category_analysis", {}).get("top_category", "unknown")
            context = f"\nPreliminary analysis suggests: Category={top_category}, Risk={risk_level}."

        prompt = f"""Analyze this image for content moderation. Focus on:
1. Is this a PROMOTIONAL/ADVERTISING post? Look for: prices, discounts, "SALE", "EMI", warranty terms, brand names overlaid on products, or marketing text. NOTE: E-commerce product pages with prices ARE promotional but NOT AI-generated.

2. Is this an AI-generated or manipulated image? Carefully check for these AI indicators:
   VISUAL ARTIFACTS:
   - Unnatural smoothness or plastic-like skin texture
   - Warped or asymmetric facial features (eyes, ears, teeth)
   - Inconsistent lighting or shadows across the image
   - Blurred or melted backgrounds, especially around edges
   - Repetitive patterns that look algorithmic
   - Text that is gibberish, warped, or impossible to read
   - Impossible anatomy (extra fingers, missing limbs, wrong proportions)
   - Floating or disconnected body parts
   - Unrealistic reflections or physics

   NOT AI-GENERATED:
   - Professional product photos from e-commerce sites (Haier, Samsung, LG, etc.)
   - Real photographs with compression artifacts or JPEG noise
   - Images with genuine watermarks from real websites
   - Screenshots of real websites or apps
   - Photos of real physical products, even if promotional

3. Does it contain watermarks from websites (bikroy, daraz, shutterstock)?
4. Does it show ACTUAL illegal items? ONLY flag: real guns/weapons, drugs/narcotics, explicit adult content. DO NOT flag normal products like electronics, inverters, UPS, generators, power supplies, etc.
5. Is the image blurry or a screenshot?{context}

Respond in JSON format:
{{
    "decision": "BLOCK/APPROVE/MANUAL_REVIEW",
    "confidence": 85,
    "explanation": "detailed explanation here",
    "violations": ["promotional_content", "watermark", "illegal_content", "ai_generated"],
    "is_promotional": true,
    "is_ai_generated": false,
    "ai_artifacts_detected": [],
    "has_watermark": false,
    "categories_detected": [],
    "recommended_action": "action recommendation"
}}"""

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]

        response = self._run(messages, max_new_tokens=512)

        try:
            assistant_marker = "assistant\n"
            body = response.split(assistant_marker)[-1].strip() if assistant_marker in response else response
            if "```json" in body:
                body = body.split("```json")[1].split("```")[0].strip()
            elif "```" in body:
                body = body.split("```")[1].split("```")[0].strip()
            j_start = body.find("{")
            j_end   = body.rfind("}") + 1
            return json.loads(body[j_start:j_end]) if j_start != -1 else _fallback_result(body)
        except json.JSONDecodeError as e:
            return _fallback_result(f"JSON error: {e}. Response: {response[:200]}")

    # ------------------------------------------------------------------
    def explain_decision(self, image: Image.Image, specific_question: str) -> Dict:
        prompt = f"""Question about this image: {specific_question}

Provide a detailed, factual explanation addressing the question. Be specific and thorough."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        explanation = self._run(messages, max_new_tokens=512)
        return {"question": specific_question, "explanation": explanation}

    # ------------------------------------------------------------------
    def resolve_dispute(
        self,
        image: Image.Image,
        initial_decision: str,
        dispute_reason: str,
        clip_analysis: Optional[Dict] = None,
    ) -> Dict:
        context = f"\nCLIP Analysis Context: {json.dumps(clip_analysis, indent=2)}" if clip_analysis else ""
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
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        response = self._run(messages, max_new_tokens=512)
        try:
            j_start = response.find("{")
            j_end   = response.rfind("}") + 1
            return json.loads(response[j_start:j_end]) if j_start != -1 else {
                "dispute_resolution": "UPHOLD",
                "final_decision": initial_decision,
                "confidence": 50,
                "reasoning": response,
                "additional_recommendations": "manual review recommended",
            }
        except json.JSONDecodeError:
            return {
                "dispute_resolution": "UPHOLD",
                "final_decision": initial_decision,
                "confidence": 50,
                "reasoning": response,
                "additional_recommendations": "manual review required",
            }

    # ------------------------------------------------------------------
    def generate_description(self, image: Image.Image) -> str:
        prompt = "Describe this image in detail. Include what you see, the setting, any text present, and notable features."
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        return self._run(messages, max_new_tokens=256)


# ---------------------------------------------------------------------------
# Unified public helper used by main.py / modal_handler.py
# ---------------------------------------------------------------------------
def get_qwen_service():
    """
    Returns the appropriate Qwen backend based on .env flags:
      USE_QWEN2VL=True  → local Qwen2VLService (GPU)
      USE_QWEN2VL=False → None (caller uses groq_moderate_image directly)
    """
    if USE_QWEN2VL:
        return Qwen2VLService(model_name="Qwen/Qwen2-VL-2B-Instruct")
    return None


def groq_moderate_image(image: Image.Image, clip_analysis: Optional[Dict] = None) -> Dict:
    """
    Public entry point for Groq-based moderation.
    Returns a zeroed-out result if no GROQ_API_KEY is configured.
    """
    if not GROQ_API_KEY:
        return {
            "decision": "APPROVE",
            "confidence": 0,
            "explanation": "Groq API key not configured",
            "violations": [],
            "is_promotional": False,
            "is_ai_generated": False,
            "has_watermark": False,
            "categories_detected": [],
            "recommended_action": "approve",
            "_moderation_ok": False,  # no key configured — this is not a real verdict
        }
    return _groq_moderate(image, clip_analysis)
