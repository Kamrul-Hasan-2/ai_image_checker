"""
Gemini-backed product-weight lookup for the /weight_checker endpoint.

Replaces the Groq text lookup used by main.py's `_check_shipping_weight`, which
is what decides whether a seller's declared shipping weight is plausible for the
product they listed. Gemini is asked, from its own knowledge, for three numbers:

  * `known_weight_kg`    — the manufacturer-published *net* product weight
  * `packaged_weight_kg` — the typical weight *with retail packaging*
  * `typical_weight_kg`  — the typical weight for this *kind* of product

The packaged figure matters because sellers declare a *shipping* weight. Comparing
that against a bare net weight is the main source of false flags — a 0.2 kg phone
genuinely ships in a 0.5 kg box. Where Gemini can supply it, the packaged weight
gives the comparison a realistic ceiling.

The first two decide the verdict, and are filled only for a model Gemini actually
recognizes. The third is advisory: it is reported back as "what we think this
weighs" even for generic listings, so a flagged seller has a number to correct
towards — but it never feeds the flagging decision itself.

Uses the REST API through `requests` (no extra dependency) and Gemini's native
structured output, so there is no markdown fence to strip and no free-text to
parse. Successful answers are cached per product so a listing checked twice gets
the same numbers twice. Every failure path returns `_lookup_ok: False`, which
callers must treat as "unknown, skip the check" — never as a confirmed weight —
and is deliberately not cached.
"""

import json
import os
import threading
import time
from typing import Dict, Optional, Tuple

import requests

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash").strip()
GEMINI_API_BASE = os.environ.get(
    "GEMINI_API_BASE", "https://generativelanguage.googleapis.com/v1beta"
).strip()
_TIMEOUT = int(os.environ.get("GEMINI_TIMEOUT_SECONDS", 20))

# Net weight is a published spec and comes back identical every time; the
# packaged figure is an estimate and moves between calls (a Galaxy S24 Ultra
# measured 0.35-0.382 kg across five runs, a camcorder 4.5-6.35 kg). Since the
# result is reported to a seller as "what we think this weighs", the same
# listing has to produce the same number twice — so answers are cached per
# product rather than re-asked on every save.
_CACHE_TTL = int(os.environ.get("GEMINI_WEIGHT_CACHE_TTL_SECONDS", 24 * 3600))
_CACHE_MAX_ENTRIES = 2048

_cache_lock = threading.Lock()
_cache: Dict[Tuple[str, str], Tuple[float, Dict]] = {}

_UNKNOWN = {
    "known_weight_kg": None,
    "packaged_weight_kg": None,
    "typical_weight_kg": None,
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
        "typical_weight_kg": {
            "type": "NUMBER",
            "nullable": True,
            "description": "Typical packaged weight for this KIND of product, in kg, even when the exact model is unknown. Advisory only.",
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
3. typical_weight_kg  — the typical packaged weight for this KIND of product, in kilograms.
                        Fill this in even when you do not recognize the exact model. It is
                        advisory only — it is shown to a human, never used to decide anything.

Rules:
- Set product_recognized to true ONLY if you recognize this specific model. A generic,
  no-name or ambiguous title ("X-922 Bluetooth RGB Speaker", "Chinese Safety Cap") is NOT
  recognized, even when you know roughly what such products weigh.
- If product_recognized is false, set known_weight_kg and packaged_weight_kg to null. Do
  not guess or estimate them from the product type — a wrong number there wrongly
  penalises a real seller. Still fill in typical_weight_kg: it informs, it never accuses.
- Report weights in kilograms, converting from the published units if needed.
- Use confidence "high" only for a well-known model whose published spec you are sure of."""


def _endpoint() -> str:
    return f"{GEMINI_API_BASE}/models/{GEMINI_MODEL}:generateContent"


def _cache_key(title: str, category: Optional[str]) -> Tuple[str, str]:
    return (" ".join(title.lower().split()), (category or "").lower().strip())


def _cache_get(key: Tuple[str, str]) -> Optional[Dict]:
    with _cache_lock:
        entry = _cache.get(key)
    if not entry:
        return None
    stored_at, value = entry
    if (time.time() - stored_at) > _CACHE_TTL:
        return None
    return dict(value)


def _cache_put(key: Tuple[str, str], value: Dict) -> None:
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            oldest = sorted(_cache, key=lambda k: _cache[k][0])[: _CACHE_MAX_ENTRIES // 2]
            for stale in oldest:
                _cache.pop(stale, None)
        _cache[key] = (time.time(), dict(value))


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
             "typical_weight_kg": float|None, "confidence": "high"/"medium"/"low",
             "_lookup_ok": bool}.

    `_lookup_ok=False` means the call or parse failed — treat as unknown and skip
    the check. Signature and keys match qwen_service.estimate_known_product_weight_kg
    so the two are interchangeable.
    """
    if not GEMINI_API_KEY or not title:
        return dict(_UNKNOWN)

    key = _cache_key(title, category)
    cached = _cache_get(key)
    if cached is not None:
        return cached

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

    typical = _coerce_weight(parsed.get("typical_weight_kg"))

    # An unrecognized model must not contribute a weight to the decision, whatever
    # it filled in. `typical` survives because nothing is decided from it — it is
    # only shown to a human alongside the verdict.
    if not parsed.get("product_recognized"):
        result = {
            "known_weight_kg": None,
            "packaged_weight_kg": None,
            "typical_weight_kg": typical,
            "confidence": parsed.get("confidence", "low"),
            "_lookup_ok": True,
        }
        _cache_put(key, result)
        return result

    net      = _coerce_weight(parsed.get("known_weight_kg"))
    packaged = _coerce_weight(parsed.get("packaged_weight_kg"))

    # Packaging can only add weight. A packaged figure below the net one is a
    # model slip — drop it rather than let it tighten the ceiling.
    if packaged is not None and net is not None and packaged < net:
        packaged = None

    result = {
        "known_weight_kg": net,
        "packaged_weight_kg": packaged,
        "typical_weight_kg": typical,
        "confidence": parsed.get("confidence", "low"),
        "_lookup_ok": True,
    }
    # Only successful lookups are cached — a transport failure must stay retryable.
    _cache_put(key, result)
    return result
