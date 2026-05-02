"""
Dynamic Visual Watermark Detector
==================================
Detects watermarks WITHOUT relying on any keyword list.

Watermarks are detected by what they LOOK LIKE visually, not what they say.
This catches any unknown marketplace logo, seller stamp, or attribution strip
regardless of the brand name or language.

Four independent visual signals:

  Signal A — Semi-transparent overlay regions
    Watermarks are typically rendered at 30-70% opacity over the product.
    We detect this by finding regions where pixel values are pulled toward a
    fixed colour (usually white, orange, green, or grey) uniformly across a
    contiguous area, creating a "washed-out" blended patch.

  Signal B — Diagonal or rotated large text
    Logo watermarks (BDStall, Shutterstock) are usually rendered diagonally
    at 30–60 degrees. We detect unusual text angle clusters in the image
    using connected-component analysis on edge-detected regions.

  Signal C — Bottom strip attribution band
    Attribution lines ("Processed using Watermarkly", "Photo by X") are
    always in a narrow horizontal strip at the very bottom of the image
    (bottom 5–8%) that is distinctly different in brightness or hue from
    the product area above it.

  Signal D — Corner / edge logo patches
    Marketplace logos (Daraz, Bikroy, unknown) are almost always placed in
    a corner or along an edge. We detect rectangular regions in the four
    corners and top/bottom edges that have uniform background colour and
    contain high-contrast pixels (text or logo art) different from the
    product body.

Each signal is scored 0.0–1.0. Final watermark_score = weighted combination.
Threshold >= 0.55 → is_watermark = True.

No OCR, no keywords, no ML model. Pure OpenCV.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, List, Tuple


# ---------------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------------

# How much of the image border to examine for corner/edge logo patches
_CORNER_FRAC   = 0.18   # 18% of width/height for corner zones
_BOTTOM_FRAC   = 0.08   # bottom 8% of image = attribution strip zone
_TOP_FRAC      = 0.06   # top 6% for top-strip logos

# Minimum blob area (as fraction of image) to count as a watermark region
_MIN_BLOB_FRAC = 0.008  # 0.8% of image area

# Transparency detection: how uniform must the alpha-blend look
_BLEND_STD_MAX = 35.0   # pixel std inside suspected blend region

# Diagonal text angle range (degrees from horizontal)
_DIAG_ANGLE_MIN = 20
_DIAG_ANGLE_MAX = 70

# Final threshold
WATERMARK_SCORE_THRESHOLD = 0.50


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _to_bgr(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _region_stats(bgr: np.ndarray, y1: int, y2: int, x1: int, x2: int) -> Dict:
    """Mean and std of a BGR region."""
    region = bgr[y1:y2, x1:x2]
    if region.size == 0:
        return {"mean": 0.0, "std": 0.0, "pixels": 0}
    gray = cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)
    return {
        "mean": float(gray.mean()),
        "std":  float(gray.std()),
        "pixels": gray.size,
    }


# ---------------------------------------------------------------------------
# SIGNAL A — Semi-transparent overlay (alpha-blend patch detection)
# ---------------------------------------------------------------------------

def _detect_transparent_overlay(bgr: np.ndarray) -> Dict[str, Any]:
    """
    Find regions that look like they were alpha-blended over the product.

    A transparent overlay creates a zone where:
    - Pixel variance is LOWER than surrounding product area
      (the overlay pulls all pixels toward its own colour)
    - The zone is large enough to be a logo / text block (not noise)
    - The zone colour is distinctly different from the product's dominant colour

    We use a sliding-window variance map: low-variance windows that are
    significantly less varied than the image median = blend candidates.
    """
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)

    # Local variance via box filter trick: E[X²] - (E[X])²
    win = 24
    mean_sq  = cv2.blur(gray ** 2, (win, win))
    sq_mean  = cv2.blur(gray, (win, win)) ** 2
    variance = np.maximum(mean_sq - sq_mean, 0)

    # Pixels where local variance is very low relative to image median
    med_var = float(np.median(variance[variance > 1]))  # skip near-zero pixels
    low_var_mask = (variance < med_var * 0.25).astype(np.uint8) * 255

    # Remove the image border itself (which is naturally low-variance)
    border = int(min(h, w) * 0.04)
    low_var_mask[:border, :] = 0
    low_var_mask[-border:, :] = 0
    low_var_mask[:, :border] = 0
    low_var_mask[:, -border:] = 0

    # Find connected blobs in the low-variance map
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (20, 20))
    closed = cv2.morphologyEx(low_var_mask, cv2.MORPH_CLOSE, kernel)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = h * w * _MIN_BLOB_FRAC
    overlay_blobs = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, bw, bh = cv2.boundingRect(c)
        # The blob must not span the entire image (that's just a uniform background)
        if bw > w * 0.85 and bh > h * 0.85:
            continue
        overlay_blobs.append({"area": area, "rect": (x, y, bw, bh)})

    has_overlay = len(overlay_blobs) > 0
    # Score: number of blobs, capped, scaled to 0-1
    score = min(len(overlay_blobs) / 3.0, 1.0) if has_overlay else 0.0

    return {
        "signal": "transparent_overlay",
        "score":  round(score, 3),
        "blob_count": len(overlay_blobs),
        "blobs": overlay_blobs[:4],
    }


# ---------------------------------------------------------------------------
# SIGNAL B — Diagonal / rotated large text blob
# ---------------------------------------------------------------------------

def _detect_diagonal_text(bgr: np.ndarray) -> Dict[str, Any]:
    """
    Detect large text rendered at a diagonal angle (typical of logo watermarks).

    Approach:
    1. Find large contiguous high-contrast blobs (text / logo candidates)
    2. Fit a minimum bounding rectangle to each blob
    3. Check if the rectangle angle is in the diagonal range (20°–70°)
    4. Check if the blob is large enough to be a logo (not a product label)
    """
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Adaptive threshold to find text/logo pixels
    binary = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV,
        blockSize=31,
        C=8,
    )

    # Dilate to join nearby text pixels into blobs
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (12, 12))
    dilated = cv2.dilate(binary, kernel, iterations=2)

    contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = h * w * 0.015   # must be at least 1.5% of image
    diagonal_blobs = []

    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        if len(c) < 5:
            continue

        # Minimum area bounding rectangle gives the angle
        rect = cv2.minAreaRect(c)
        angle = abs(rect[2])  # 0–90 degrees

        # OpenCV returns angle in [-90, 0]; convert to 0–90
        if angle > 45:
            angle = 90 - angle

        # Is this blob rotated into the diagonal range?
        if _DIAG_ANGLE_MIN <= angle <= _DIAG_ANGLE_MAX:
            bw, bh = rect[1]
            aspect = max(bw, bh) / (min(bw, bh) + 1)
            # Logo text tends to be elongated (aspect > 2)
            if aspect > 1.5:
                diagonal_blobs.append({
                    "area":   float(area),
                    "angle":  round(float(angle), 1),
                    "aspect": round(float(aspect), 2),
                })

    has_diagonal = len(diagonal_blobs) > 0
    score = min(len(diagonal_blobs) / 2.0, 1.0) if has_diagonal else 0.0

    return {
        "signal": "diagonal_text",
        "score":  round(score, 3),
        "diagonal_blob_count": len(diagonal_blobs),
        "blobs": diagonal_blobs[:3],
    }


# ---------------------------------------------------------------------------
# SIGNAL C — Bottom strip attribution band
# ---------------------------------------------------------------------------

def _detect_bottom_strip(bgr: np.ndarray) -> Dict[str, Any]:
    """
    Detect a narrow horizontal strip at the very bottom of the image that is
    visually distinct from the product area above.

    Attribution lines ("Processed using Watermarkly", "Photo by X") are always:
    - In the bottom 5–10% of the image
    - On a uniform background (white or light grey)
    - Contain high-contrast fine text (small standard deviation within the strip,
      but measurable edge density)
    - Noticeably different mean brightness than the product area above

    Also checks the TOP strip for top-placed logo banners.
    """
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    bottom_h = max(int(h * _BOTTOM_FRAC), 10)
    top_h    = max(int(h * _TOP_FRAC), 8)
    middle_h = h - bottom_h - top_h

    if middle_h <= 0:
        return {"signal": "bottom_strip", "score": 0.0}

    bottom_strip = gray[h - bottom_h:, :]
    top_strip    = gray[:top_h, :]
    middle       = gray[top_h: h - bottom_h, :]

    bottom_mean = float(bottom_strip.mean())
    top_mean    = float(top_strip.mean())
    middle_mean = float(middle.mean())
    bottom_std  = float(bottom_strip.std())
    top_std     = float(top_strip.std())

    # A strip is suspicious if:
    # 1. Its mean brightness differs from the product middle by > 25 points
    # 2. Its std is LOW (uniform background) — the text is small
    # 3. It has some edge content (not completely blank)

    def _strip_score(strip_mean, strip_std, ref_mean) -> float:
        brightness_diff = abs(strip_mean - ref_mean)
        is_uniform  = strip_std < 40.0           # background is uniform
        has_content = strip_std > 5.0            # not blank white
        is_distinct = brightness_diff > 20.0     # different from product

        if is_uniform and has_content and is_distinct:
            # Score proportional to how distinct the strip is
            return min(brightness_diff / 80.0, 1.0)
        return 0.0

    bot_score = _strip_score(bottom_mean, bottom_std, middle_mean)
    top_score = _strip_score(top_mean,    top_std,    middle_mean)
    score     = max(bot_score, top_score)

    return {
        "signal":       "attribution_strip",
        "score":        round(score, 3),
        "bottom_mean":  round(bottom_mean, 1),
        "bottom_std":   round(bottom_std, 1),
        "top_mean":     round(top_mean, 1),
        "middle_mean":  round(middle_mean, 1),
        "bot_score":    round(bot_score, 3),
        "top_score":    round(top_score, 3),
    }


# ---------------------------------------------------------------------------
# SIGNAL D — Corner / edge logo patch
# ---------------------------------------------------------------------------

def _detect_corner_logo(bgr: np.ndarray) -> Dict[str, Any]:
    """
    Detect a rectangular logo patch in the four corners or along the top/bottom
    edges of the image.

    A corner logo patch has:
    - Uniform background colour (std < 30) — marketplace logos are on solid bg
    - High internal contrast (edge density) — there IS a logo drawn on it
    - Distinctly different colour from the surrounding product area

    We examine 5 zones: TL, TR, BL, BR corners + full top-strip.
    """
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(gray, 50, 150)

    cz = int(min(h, w) * _CORNER_FRAC)  # corner zone size
    tz = int(h * _TOP_FRAC)             # top strip height

    zones = {
        "top_left":     (0,      cz,      0,      cz),
        "top_right":    (0,      cz,      w - cz, w),
        "bot_left":     (h - cz, h,       0,      cz),
        "bot_right":    (h - cz, h,       w - cz, w),
        "top_strip":    (0,      tz,      0,      w),
    }

    # Get product centre stats (reference for "different from product")
    cx1, cx2 = int(w * 0.25), int(w * 0.75)
    cy1, cy2 = int(h * 0.25), int(h * 0.75)
    centre_mean = float(gray[cy1:cy2, cx1:cx2].mean())
    centre_std  = float(gray[cy1:cy2, cx1:cx2].std())

    logo_zones: List[str] = []
    zone_scores: Dict[str, float] = {}

    for name, (y1, y2, x1, x2) in zones.items():
        if y2 <= y1 or x2 <= x1:
            continue

        zone_gray  = gray[y1:y2, x1:x2]
        zone_edges = edges[y1:y2, x1:x2]

        zone_mean = float(zone_gray.mean())
        zone_std  = float(zone_gray.std())
        edge_density = float(zone_edges.mean())  # 0–255 mean of binary edge map

        # Conditions for a logo patch:
        # 1. Background is relatively uniform (std < product centre std × 0.7)
        is_uniform = zone_std < min(centre_std * 0.70, 45.0)
        # 2. There is actual content (not blank)
        has_content = edge_density > 3.0
        # 3. Colour is different from the product centre
        is_different = abs(zone_mean - centre_mean) > 18.0

        if is_uniform and has_content and is_different:
            logo_zones.append(name)
            # Score: edge density (more logo pixels = higher confidence) scaled 0-1
            zone_scores[name] = min(edge_density / 25.0, 1.0)

    score = max(zone_scores.values()) if zone_scores else 0.0

    return {
        "signal":      "corner_logo",
        "score":       round(score, 3),
        "logo_zones":  logo_zones,
        "zone_scores": {k: round(v, 3) for k, v in zone_scores.items()},
    }


# ---------------------------------------------------------------------------
# MAIN PUBLIC FUNCTION
# ---------------------------------------------------------------------------

def detect_watermark_visual(
    image: Image.Image,
    is_product_photo: bool = False,
    product_photo_confidence: float = 0.0,
) -> Dict[str, Any]:
    """
    Dynamically detect watermarks using visual signals only — no keywords.

    Args:
        image                   : PIL RGB image
        is_product_photo        : CLIP product photo verdict
        product_photo_confidence: CLIP confidence score

    Returns
    -------
    {
        "visual_watermark_score"   : float 0.0–1.0
        "is_visual_watermark"      : bool
        "signals"                  : dict  — per-signal details
        "dominant_signal"          : str   — which signal drove the decision
        "reasons"                  : list[str]
    }
    """
    bgr = _to_bgr(image)

    sig_a = _detect_transparent_overlay(bgr)
    sig_b = _detect_diagonal_text(bgr)
    sig_c = _detect_bottom_strip(bgr)
    sig_d = _detect_corner_logo(bgr)

    # ── WEIGHTED COMBINATION ─────────────────────────────────────────────────
    # Weights reflect how reliable each signal is:
    # - Diagonal text (B) is the most specific to logo watermarks
    # - Bottom strip (C) is the most specific to attribution watermarks
    # - Transparent overlay (A) is broad but reliable
    # - Corner logo (D) is useful but can fire on product packaging corners
    weights = {
        "transparent_overlay": 0.25,
        "diagonal_text":       0.35,
        "attribution_strip":   0.25,
        "corner_logo":         0.15,
    }
    scores = {
        "transparent_overlay": sig_a["score"],
        "diagonal_text":       sig_b["score"],
        "attribution_strip":   sig_c["score"],
        "corner_logo":         sig_d["score"],
    }

    weighted_score = sum(scores[k] * weights[k] for k in weights)

    # Boost: if two or more independent signals fire, confidence is higher
    firing_signals = [k for k, s in scores.items() if s > 0.30]
    if len(firing_signals) >= 2:
        # Two independent signals agreeing is much stronger than one alone
        weighted_score = min(weighted_score * 1.35, 1.0)

    # For confirmed product photos, raise the bar slightly to avoid flagging
    # product packaging graphics (colourful boxes, diagonal brand text on box)
    threshold = WATERMARK_SCORE_THRESHOLD
    if is_product_photo and product_photo_confidence > 0.55:
        threshold = 0.58

    is_watermark = weighted_score >= threshold

    # Dominant signal = highest individual score
    dominant = max(scores, key=lambda k: scores[k])

    reasons = []
    if scores["diagonal_text"] > 0.30:
        reasons.append(f"diagonal_logo_text(score={scores['diagonal_text']:.2f}, blobs={sig_b['diagonal_blob_count']})")
    if scores["transparent_overlay"] > 0.30:
        reasons.append(f"transparent_overlay(score={scores['transparent_overlay']:.2f}, blobs={sig_a['blob_count']})")
    if scores["attribution_strip"] > 0.30:
        reasons.append(f"attribution_strip(score={scores['attribution_strip']:.2f})")
    if scores["corner_logo"] > 0.30:
        reasons.append(f"corner_logo(zones={sig_d['logo_zones']})")

    return {
        "visual_watermark_score": round(weighted_score, 3),
        "is_visual_watermark":    is_watermark,
        "signals": {
            "transparent_overlay": sig_a,
            "diagonal_text":       sig_b,
            "attribution_strip":   sig_c,
            "corner_logo":         sig_d,
        },
        "signal_scores":   {k: round(v, 3) for k, v in scores.items()},
        "firing_signals":  firing_signals,
        "dominant_signal": dominant,
        "reasons":         reasons,
    }
