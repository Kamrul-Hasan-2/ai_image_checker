"""
Stage 0 — Body-Native Text Region Detector.

For every OCR bounding box, decides whether the text is:

  A. body_native  — physically printed on the product body
                    (labels, spec plates, model numbers, certifications)

  B. overlay      — seller-added promotional text floating on top
                    (banners, price badges, phone numbers, CTA buttons)

Uses only bounding-box geometry, pixel colour statistics, and the
keyword whitelists in utils/cv_rules.py.  No ML model required.

Why this matters
----------------
The vocabulary matcher in Stage 2 cannot whitelist text that is correct
but absent from the product title/description — e.g., "Replace Battery"
on an APC UPS or "AVR Boost" on a power strip.  Stage 0 catches these
before Stage 2 can misclassify them as suspicious.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image
from typing import Any, Dict, List, Tuple

from services.text_normalizer import normalise
from utils.cv_rules import (
    BOX_GEOMETRY,
    COLOUR,
    EDGE_ZONE_FRAC,
    NATIVE_TEXT_KEYWORDS,
    OVERLAY_SIGNAL_KEYWORDS,
    TYPOGRAPHY,
    WIDE_BOX_FRAC,
)


# ---------------------------------------------------------------------------
# GEOMETRY HELPERS
# ---------------------------------------------------------------------------

def _bbox_rect(bbox: List) -> Tuple[float, float, float, float]:
    """Return (left, top, right, bottom) from a 4-point EasyOCR polygon."""
    xs = [pt[0] for pt in bbox]
    ys = [pt[1] for pt in bbox]
    return min(xs), min(ys), max(xs), max(ys)


def _box_metrics(
    bbox: List,
    img_width: int,
    img_height: int,
) -> Dict[str, float]:
    """Compute normalised geometric features of an OCR bounding box."""
    left, top, right, bottom = _bbox_rect(bbox)
    box_w = right - left
    box_h = bottom - top
    area  = box_w * box_h

    return {
        "width_frac":   box_w / img_width  if img_width  > 0 else 0,
        "height_frac":  box_h / img_height if img_height > 0 else 0,
        "area_frac":    area  / (img_width * img_height) if img_width * img_height > 0 else 0,
        "aspect":       box_w / box_h if box_h > 0 else 0,
        "centre_y_frac": ((top + bottom) / 2) / img_height if img_height > 0 else 0.5,
        "centre_x_frac": ((left + right) / 2) / img_width  if img_width  > 0 else 0.5,
        "top_frac":     top  / img_height if img_height > 0 else 0,
        "bot_frac":     bottom / img_height if img_height > 0 else 0,
    }


# ---------------------------------------------------------------------------
# COLOUR STATISTICS INSIDE BOUNDING BOX
# ---------------------------------------------------------------------------

def _box_colour_stats(
    img_hsv: np.ndarray,
    bbox: List,
) -> Dict[str, float]:
    """
    Extract colour statistics from the HSV image region inside bbox.

    Returns mean_saturation, mean_value, pixel_std (grayscale).
    """
    left, top, right, bottom = _bbox_rect(bbox)
    y1, y2 = max(0, int(top)),  min(img_hsv.shape[0], int(bottom))
    x1, x2 = max(0, int(left)), min(img_hsv.shape[1], int(right))

    if y2 <= y1 or x2 <= x1:
        return {"mean_saturation": 0.0, "mean_value": 0.0, "pixel_std": 0.0}

    region = img_hsv[y1:y2, x1:x2]
    gray_region = cv2.cvtColor(region, cv2.COLOR_HSV2BGR)
    gray_region = cv2.cvtColor(gray_region, cv2.COLOR_BGR2GRAY)

    return {
        "mean_saturation": float(region[:, :, 1].mean()),
        "mean_value":      float(region[:, :, 2].mean()),
        "pixel_std":       float(gray_region.std()),
    }


# ---------------------------------------------------------------------------
# KEYWORD CHECKS
# ---------------------------------------------------------------------------

def _has_native_keyword(text_lower: str) -> bool:
    return any(kw in text_lower for kw in NATIVE_TEXT_KEYWORDS)


def _has_overlay_keyword(text_lower: str) -> bool:
    return any(kw in text_lower for kw in OVERLAY_SIGNAL_KEYWORDS)


# ---------------------------------------------------------------------------
# PER-BOX CLASSIFIER
# ---------------------------------------------------------------------------

def classify_box(
    text: str,
    confidence: float,
    bbox: List,
    img_width: int,
    img_height: int,
    img_hsv: np.ndarray,
    layout: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Classify a single OCR box as body_native, overlay, or ambiguous.

    Returns a classification dict:
    {
        "text":         str
        "label":        "native" | "overlay" | "ambiguous"
        "native_score": float 0–1  (higher = more native)
        "overlay_score": float 0–1 (higher = more overlay)
        "reasons":      list[str]  (why this label was chosen)
    }
    """
    text_lower = normalise(text)
    geo = _box_metrics(bbox, img_width, img_height)
    colour = _box_colour_stats(img_hsv, bbox)

    native_score = 0.0
    overlay_score = 0.0
    reasons: List[str] = []

    # ── NATIVE SIGNALS ────────────────────────────────────────────────────

    # 1. Native keyword match (strongest single signal)
    if _has_native_keyword(text_lower):
        native_score += 0.55
        reasons.append("native_keyword_match")

    # 2. Monochrome typography (low colour variation = industrial label)
    if colour["pixel_std"] < COLOUR.monochrome_std_max:
        native_score += 0.20
        reasons.append("monochrome_typography")

    # 3. Low saturation (manufacturer labels are rarely neon-coloured)
    if colour["mean_saturation"] < COLOUR.high_saturation_threshold:
        native_score += 0.15
        reasons.append("low_saturation_region")

    # 4. Reasonable box size (not a giant banner)
    if (geo["height_frac"] < BOX_GEOMETRY.max_native_height_frac
            and geo["area_frac"] < BOX_GEOMETRY.max_native_area_frac):
        native_score += 0.10
        reasons.append("small_box_size")

    # 5. Centred vertically (product labels sit on the product body, not at edges)
    edge = EDGE_ZONE_FRAC
    if edge < geo["centre_y_frac"] < (1 - edge):
        native_score += 0.10
        reasons.append("centred_vertically")

    # 6. Short text with sensible aspect ratio (like "500mAh" or "DC 12V")
    if (BOX_GEOMETRY.label_min_aspect <= geo["aspect"] <= BOX_GEOMETRY.label_max_aspect
            and len(text.split()) <= 6):
        native_score += 0.05
        reasons.append("label_aspect_ratio")

    # ── OVERLAY SIGNALS ───────────────────────────────────────────────────

    # 1. Explicit overlay keyword (strongest single signal)
    if _has_overlay_keyword(text_lower):
        overlay_score += 0.60
        reasons.append("overlay_keyword_match")

    # 2. Wide box spanning most of image width = banner strip
    if geo["width_frac"] > WIDE_BOX_FRAC:
        overlay_score += 0.30
        reasons.append("wide_banner_box")

    # 3. Positioned at the extreme edge + wide = nav-bar / footer
    at_edge = (
        geo["centre_y_frac"] < EDGE_ZONE_FRAC
        or geo["centre_y_frac"] > (1 - EDGE_ZONE_FRAC)
    )
    if at_edge and geo["width_frac"] > 0.40:
        overlay_score += 0.25
        reasons.append("wide_edge_box")

    # 4. High saturation = colourful promotional region
    if colour["mean_saturation"] > COLOUR.high_saturation_threshold:
        overlay_score += 0.20
        reasons.append("high_saturation_region")

    # 5. Very large text (large CTA font)
    if geo["height_frac"] > TYPOGRAPHY.large_font_frac:
        overlay_score += 0.15
        reasons.append("large_font_size")

    # 6. Global layout says there is overlay evidence — nudge overlay score
    if layout.get("layout_has_overlay_evidence"):
        overlay_score += 0.10
        reasons.append("global_layout_overlay_evidence")

    # 7. Corner badge (coloured blob in corner from cv_layout_analyzer)
    if layout.get("corner_badge_detected"):
        overlay_score += 0.10
        reasons.append("corner_badge_in_image")

    # ── FINAL CLASSIFICATION ──────────────────────────────────────────────
    # Cap scores at 1.0
    native_score  = min(native_score, 1.0)
    overlay_score = min(overlay_score, 1.0)

    if overlay_score > native_score + 0.10:
        label = "overlay"
    elif native_score > overlay_score + 0.10:
        label = "native"
    else:
        label = "ambiguous"

    return {
        "text":          text,
        "label":         label,
        "native_score":  round(native_score, 3),
        "overlay_score": round(overlay_score, 3),
        "reasons":       reasons,
        "geo":           geo,
        "colour":        colour,
    }


# ---------------------------------------------------------------------------
# STAGE 0 MAIN FUNCTION
# ---------------------------------------------------------------------------

def analyse_text_regions(
    ocr_result: Dict[str, Any],
    image: Image.Image,
    layout: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Classify every OCR box from Stage 1 as native or overlay.

    Args:
        ocr_result : output of services/ocr_service.extract_text()
        image      : PIL Image (RGB) used for colour analysis
        layout     : output of services/cv_layout_analyzer.analyse_layout()

    Returns
    -------
    {
        "native_boxes"   : list[dict]   — boxes classified as native
        "overlay_boxes"  : list[dict]   — boxes classified as overlay
        "ambiguous_boxes": list[dict]   — boxes that could be either
        "native_texts"   : list[str]    — text strings from native boxes
        "overlay_texts"  : list[str]    — text strings from overlay boxes
        "native_fraction": float        — fraction of boxes that are native
        "has_overlay"    : bool         — True if any overlay box found
        "classifications": list[dict]   — full per-box classification details
    }
    """
    extracted  = ocr_result.get("extracted_data", [])
    img_width  = ocr_result.get("img_width",  0)
    img_height = ocr_result.get("img_height", 0)

    if not extracted or img_width == 0 or img_height == 0:
        return {
            "native_boxes":    [],
            "overlay_boxes":   [],
            "ambiguous_boxes": [],
            "native_texts":    [],
            "overlay_texts":   [],
            "native_fraction": 0.0,
            "has_overlay":     False,
            "classifications": [],
        }

    img_bgr = cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)
    img_hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)

    native_boxes:    List[Dict] = []
    overlay_boxes:   List[Dict] = []
    ambiguous_boxes: List[Dict] = []
    classifications: List[Dict] = []

    for box in extracted:
        text       = box.get("text", "")
        confidence = box.get("confidence", 0.0)
        bbox       = box.get("bbox", [])

        if not text or not bbox or confidence < TYPOGRAPHY.min_confidence:
            continue

        cls = classify_box(
            text, confidence, bbox,
            img_width, img_height,
            img_hsv, layout,
        )
        classifications.append(cls)

        if cls["label"] == "native":
            native_boxes.append(cls)
        elif cls["label"] == "overlay":
            overlay_boxes.append(cls)
        else:
            ambiguous_boxes.append(cls)

    total = len(classifications)
    native_fraction = len(native_boxes) / total if total > 0 else 0.0

    return {
        "native_boxes":    native_boxes,
        "overlay_boxes":   overlay_boxes,
        "ambiguous_boxes": ambiguous_boxes,
        "native_texts":    [b["text"] for b in native_boxes],
        "overlay_texts":   [b["text"] for b in overlay_boxes],
        "native_fraction": round(native_fraction, 3),
        "has_overlay":     len(overlay_boxes) > 0,
        "classifications": classifications,
    }
