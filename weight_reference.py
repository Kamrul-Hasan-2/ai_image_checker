"""
Category-level shipping-weight sanity bounds.

Fallback layer for the shipping_weight check in main.py / modal_handler.py: used
only when the AI model doesn't have confident knowledge of the *specific*
product's published weight (generic/no-name listings like "X-922 Bluetooth RGB
Speaker" that aren't a recognizable branded model, so the per-model lookup
returns nothing). Without this, such listings would never get checked at all —
this catches obviously implausible values (unit mistakes, inflated shipping
weight) even when the exact model is unknown.

These are deliberately generous upper bounds — "plausible ceiling for this kind
of product", not a tight expected range. Tune per real listing data.
"""

import re
from typing import Optional

# category keyword (matched as a whole word, case-insensitive) -> max plausible kg
CATEGORY_MAX_WEIGHT_KG = {
    "mobile": 0.5, "smartphone": 0.5, "phone": 0.5,
    "laptop": 4.0, "notebook": 4.0, "ultrabook": 3.0, "chromebook": 3.0,
    "tablet": 1.5,
    "speaker": 15.0, "soundbar": 15.0,
    "headphone": 1.0, "headset": 1.0, "earbud": 0.2, "earphone": 0.2,
    "power bank": 1.5, "powerbank": 1.5,
    "router": 2.0, "modem": 2.0,
    "keyboard": 2.0, "mouse": 0.5,
    "monitor": 15.0,
    "tv": 40.0, "television": 40.0,
    "printer": 25.0, "scanner": 15.0,
    "camera": 2.0, "webcam": 0.5,
    "ups": 40.0, "generator": 200.0,
    "refrigerator": 150.0, "fridge": 150.0,
    "air conditioner": 80.0,
    "washing machine": 100.0,
    "microwave": 30.0, "oven": 40.0,
    "fan": 10.0,
    "ssd": 0.2, "hdd": 1.0, "ram": 0.1,
    "graphics card": 3.0, "motherboard": 2.0,
    "power supply": 3.0, "psu": 3.0,
    "smartwatch": 0.15, "watch": 0.3,
}


def plausible_max_weight_kg(category: Optional[str]) -> Optional[float]:
    """
    Best-match plausible max weight (kg) for a free-text category, or None if
    the category isn't recognized (caller should skip the check, not guess).
    """
    if not category:
        return None
    cat = category.lower()
    best = None
    for keyword, max_kg in CATEGORY_MAX_WEIGHT_KG.items():
        if re.search(r"\b" + re.escape(keyword) + r"\b", cat):
            # Prefer the most specific (longest keyword) match.
            if best is None or len(keyword) > len(best[0]):
                best = (keyword, max_kg)
    return best[1] if best else None
