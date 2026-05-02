"""
Stage 3 — Promotional Text Pattern Engine.

Operates ONLY on:
  - overlay_texts from Stage 0 (explicit overlay classification)
  - unmatched_tokens from Stage 2 (not in product vocabulary)

This prevents false positives from manufacturer-printed text
(model numbers, spec labels, certifications) that is legitimately
on the product body but not mentioned in the product title/description.
"""

from __future__ import annotations

from typing import Any, Dict, List, Set, Tuple

from utils.regex_patterns import ALL_PATTERNS, PATTERN_WEIGHTS


def scan_text(text: str) -> List[Dict[str, Any]]:
    """
    Run all promotional patterns against `text`.
    Returns one dict per unique (type, matched_string) hit.
    """
    seen: Set[Tuple[str, str]] = set()
    hits: List[Dict] = []

    for label, pattern, _ in ALL_PATTERNS:
        for m in pattern.finditer(text):
            key = (label, m.group().strip().lower())
            if key not in seen:
                seen.add(key)
                hits.append({
                    "type":    label,
                    "matched": m.group().strip(),
                    "span":    m.span(),
                })
    return hits


def detect(
    overlay_texts: List[str],
    unmatched_tokens: List[str],
    full_ocr_text: str,
) -> Dict[str, Any]:
    """
    Run the promotional pattern engine on the suspicious text surfaces.

    Scan order (most targeted → broadest):
    1. Overlay box texts (Stage 0 output) — highest precision
    2. Unmatched tokens joined as a string (Stage 2 output)
    3. Full raw OCR text — catches multi-word patterns that span boxes

    Args:
        overlay_texts    : text strings from boxes classified as overlay
        unmatched_tokens : tokens not matched to product vocabulary
        full_ocr_text    : complete joined OCR text (for multi-word patterns)

    Returns
    -------
    {
        "promotional_flags" : list[dict]  — each hit: {type, matched, span}
        "fired_types"       : list[str]   — unique pattern types that fired
        "raw_score"         : int         — sum of weights before confidence engine
    }
    """
    all_hits: List[Dict] = []

    # Surface 1: overlay texts (highest precision)
    for txt in overlay_texts:
        all_hits.extend(scan_text(txt))

    # Surface 2: unmatched token stream
    if unmatched_tokens:
        all_hits.extend(scan_text(" ".join(unmatched_tokens)))

    # Surface 3: full OCR text (catches multi-word patterns spanning boxes)
    all_hits.extend(scan_text(full_ocr_text))

    # Deduplicate across all three surfaces by (type, matched string)
    seen: Set[Tuple[str, str]] = set()
    unique_hits: List[Dict] = []
    for h in all_hits:
        key = (h["type"], h["matched"].lower())
        if key not in seen:
            seen.add(key)
            unique_hits.append(h)

    fired_types = sorted({h["type"] for h in unique_hits})
    raw_score   = sum(PATTERN_WEIGHTS.get(t, 10) for t in fired_types)

    return {
        "promotional_flags": unique_hits,
        "fired_types":       fired_types,
        "raw_score":         raw_score,
    }
