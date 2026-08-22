"""
Gemini-backed product-weight lookup for the /weight_checker endpoint.

Replaces the Groq text lookup used by main.py's `_check_shipping_weight`, which
is what decides whether a seller's declared shipping weight is plausible for the
product they listed. Gemini is asked, from its own knowledge, for two numbers:

  * `known_weight_kg`    — the manufacturer-published *net* product weight
  * `packaged_weight_kg` — the typical weight *with retail packaging*

The second one matters because sellers declare a *shipping* weight. Comparing a
shipping weight against a bare net weight is the main source of false flags — a
0.2 kg phone genuinely ships in a 0.5 kg box. Where Gemini can supply it, the
packaged figure gives the comparison a realistic ceiling.

Uses the REST API through `requests` (no extra dependency) and Gemini's native
structured output, so there is no markdown fence to strip and no free-text to
parse. Every failure path returns `_lookup_ok: False`, which callers must treat
as "unknown, skip the check" — never as a confirmed weight.
"""

import json
import os
from typing import Dict, Optional

import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_API_BASE = os.environ.get(
    "GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta"
).strip()
_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", 20))

_UNKNOWN = {
    "known_weight_kg": None,
    "packaged_weight_kg": None,
    "confidence": "low",
    "_lookup_ok": False,
}

# Native structured output — Gemini is constrained to this shape, so the response
# is always parseable JSON rather than prose that happens to contain JSON.
_WEIGHT_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "product_recognized": {
            "type": "BOOLEAN",
            "description": "True only if this exact model is recognized, not merely its product type",
        },
        "known_weight_kg": {
            "type": "NUMBER",
            "nullable": True,
            "description": "Manufacturer-published net weight of the device itself, in kg. Null if not confidently known.",
        },
        "packaged_weight_kg": {
            "type": "NUMBER",
            "nullable": True,
            "description": "Typical weight including retail box and accessories, in kg. Null if not confidently known.",
        },
        "confidence": {"type": "STRING", "enum": ["high", "medium", "low"]},
    },
    "required": ["product_recognized", "known_weight_kg", "confidence"],
}

_PROMPT = """You are checking whether a marketplace seller's declared shipping weight is plausible.

Product title: {title}
{context}
Report, from your own knowledge of this exact product model:

1. known_weight_kg    — the manufacturer-published NET weight of the device itself, in kilograms.
2. packaged_weight_kg — the typical weight of the retail package as shipped: the device plus its
                        box, manual, charger/cables and other in-box accessories, in kilograms.
                        This is always heavier than the net weight.

Rules:
- Set product_recognized to true ONLY if you recognize this specific model. A generic,
  no-name or ambiguous title ("X-922 Bluetooth RGB Speaker", "Chinese Safety Cap") is NOT
  recognized, even when you know roughly what such products weigh.
- If product_recognized is false, set both weights to null. Do not guess or estimate from
  the product type — a wrong number here wrongly penalises a real seller.
- Report weights in kilograms, converting from the published units if needed.
- Use confidence "high" only for a well-known model whose published spec you are sure of."""


def _endpoint() -> str:
    return f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent"


def _coerce_weight(value) -> Optional[float]:
    """A usable positive weight, or None. Rejects bools and absurd values."""
    if value is None or isinstance(value, bool):
        return None
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return None
    # Nothing sold on the site is under a gram or over a tonne; a number outside
    # that is a unit slip in the model's answer, not a real spec.
    if not (0.001 <= weight <= 1000):
        return None
    return weight


def estimate_known_product_weight_kg(
    title: str,
    category: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict:
    """
    Ask Gemini for the published weight of a specific product model.

    Returns {"known_weight_kg": float|None, "packaged_weight_kg": float|None,
             "confidence": "high"/"medium"/"low", "_lookup_ok": bool}.

    `_lookup_ok=False` means the call or parse failed — treat as unknown and skip
    the check. Signature and keys match qwen_service.estimate_known_product_weight_kg
    so the two are interchangeable.
    """
    if not GEMINI_API_KEY or not title:
        return dict(_UNKNOWN)

    context = ""
    if category:
        context += f"Category: {category}\n"
    if description:
        context += f"Description: {description[:600]}\n"

    payload = {
        "contents": [{
            "parts": [{"text": _PROMPT.format(title=title, context=context)}]
        }],
        "generationConfig": {
            "temperature": 0,
            "maxOutputTokens": 2048,
            "responseMimeType": "application/json",
            "responseSchema": _WEIGHT_SCHEMA,
        },
    }

    try:
        resp = requests.post(
            _endpoint(),
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        print(f"⚠️  Gemini weight-lookup request failed: {e}")
        return dict(_UNKNOWN)

    if resp.status_code != 200:
        # Body is truncated — it can echo the prompt back on a 400.
        print(f"⚠️  Gemini weight-lookup HTTP {resp.status_code}: {resp.text[:300]}")
        return dict(_UNKNOWN)

    try:
        body = resp.json()
        parts = body["candidates"][0]["content"]["parts"]
        raw = "".join(p.get("text", "") for p in parts)
        parsed = json.loads(raw)
    except (ValueError, KeyError, IndexError, TypeError) as e:
        print(f"⚠️  Gemini weight-lookup unparseable response: {e}")
        return dict(_UNKNOWN)

    # An unrecognized model must not contribute a weight, whatever it filled in.
    if not parsed.get("product_recognized"):
        return {
            "known_weight_kg": None,
            "packaged_weight_kg": None,
            "confidence": parsed.get("confidence", "low"),
            "_lookup_ok": True,
        }

    net      = _coerce_weight(parsed.get("known_weight_kg"))
    packaged = _coerce_weight(parsed.get("packaged_weight_kg"))

    # Packaging can only add weight. A packaged figure below the net one is a
    # model slip — drop it rather than let it tighten the ceiling.
    if packaged is not None and net is not None and packaged < net:
        packaged = None

    return {
        "known_weight_kg": net,
        "packaged_weight_kg": packaged,
        "confidence": parsed.get("confidence", "low"),
        "_lookup_ok": True,
    }
