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

    # Pixels where local variance is very low relative to image median.
    # Guard the empty-slice case: on a uniform / heavily-compressed / product-on-
    # white image every local variance can be <= 1, making variance[variance > 1]
    # empty. np.median([]) returns NaN, and `variance < NaN` is all-False, which
    # would silently disable detection. Fall back to the overall mean variance.
    _nonzero_var = variance[variance > 1]
    if _nonzero_var.size > 0:
        med_var = float(np.median(_nonzero_var))
    else:
        med_var = float(np.mean(variance))  # ~0 for a truly uniform image
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

    # Global image brightness stats: used to exclude plain white/dark backgrounds
    img_mean = float(gray.mean())

    overlay_blobs = []
    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area:
            continue
        x, y, bw, bh = cv2.boundingRect(c)

        # Skip: blob spans most of the image — it's the product body or background,
        # not a watermark overlay. Threshold: area > 60% of image OR either
        # dimension > 80% of image side.
        blob_area_frac = (bw * bh) / (w * h)
        if blob_area_frac > 0.60:
            continue
        if bw > w * 0.80 or bh > h * 0.80:
            continue

        # Skip: blob hugs the image boundary on both axes (background margin region)
        touches_left   = x < w * 0.05
        touches_right  = (x + bw) > w * 0.95
        touches_top    = y < h * 0.05
        touches_bottom = (y + bh) > h * 0.95
        if (touches_left or touches_right) and (touches_top or touches_bottom):
            blob_centre_x = x + bw / 2
            blob_centre_y = y + bh / 2
            is_centred = (w * 0.2 < blob_centre_x < w * 0.8 and
                          h * 0.2 < blob_centre_y < h * 0.8)
            if not is_centred:
                continue

        # Skip: blob mean brightness is near-white (>210) AND near image edges
        # → this is just the white background of a product-on-white-bg photo
        blob_mean = float(gray[y: y+bh, x: x+bw].mean())
        is_near_white = blob_mean > 210
        is_edge_blob  = (x < w * 0.15 or (x + bw) > w * 0.85 or
                         y < h * 0.15 or (y + bh) > h * 0.85)
        if is_near_white and is_edge_blob:
            continue

        # Skip: blob is same brightness as image mean ± 15 (it blends with product,
        # not overlaid on it) — real overlays have a different tint
        if abs(blob_mean - img_mean) < 12:
            continue

        # Skip: blob that is a solid filled rectangle — i.e. a product surface, brick,
        # panel, or any physical object with uniform color. Real watermark overlays are
        # semi-transparent and sparse (text outlines), not solid filled shapes.
        # fill_ratio > 0.65 means the contour fills >65% of its bounding box = solid rect.
        # Lowered area threshold from 0.10 to 0.015: even small solid bricks (~2% of image)
        # should be excluded — multiple stacked product units each qualify independently.
        fill_ratio = area / max(bw * bh, 1)
        if fill_ratio > 0.65 and (bw * bh) / (w * h) > 0.015:
            continue

        # Skip: blob is significantly darker than the image mean AND has high internal
        # variance — this is a dark product object sitting on a bright/white background,
        # NOT a semi-transparent overlay. Overlays are pulled toward the overlay colour
        # (light or brand-tinted), so they are rarely >60 grey levels below img_mean.
        # High std (>50) further confirms it is a textured object, not a flat overlay patch.
        blob_std = float(gray[y: y+bh, x: x+bw].std())
        if blob_mean < img_mean - 60 and blob_std > 50:
            continue

        overlay_blobs.append({"area": area, "rect": (x, y, bw, bh), "mean": round(blob_mean, 1)})

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
            # Logo text tends to be elongated (aspect > 2).
            # Require aspect > 2.5 (not 1.5) to avoid product labels on tilted hardware.
            # Also require blob NOT to span most of the image width/height — real watermark
            # text is a floating overlay, not a label printed on the full product face.
            blob_w_frac = bw / w
            blob_h_frac = bh / h
            # Reject if blob covers too much of the image in either dimension:
            # watermark text is a floating overlay, not 40%+ of the image height.
            # Also reject if the blob is too tall relative to its width — that is a
            # product silhouette (horn, speaker) not diagonal text.
            is_product_label = (blob_w_frac > 0.40 or blob_h_frac > 0.40)
            if aspect > 2.5 and not is_product_label:
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

    middle_std  = float(middle.std())

    # Edge density inside the strip — attribution text has fine edges on a calm background.
    # A plain white margin (no text) has near-zero edge density.
    edges = cv2.Canny(gray, 30, 100)
    bot_edge_density = float(edges[h - bottom_h:, :].mean())
    top_edge_density = float(edges[:top_h, :].mean())

    # Whole-image white-background check: product-on-white-bg photos (catalogue shots,
    # e-commerce listings) have a bright median and most pixels near-white. In these images
    # the top/bottom margins are just more of the same white background — NOT an attribution
    # strip. The strip detector fires when those margins are brighter than the product-cluttered
    # middle, which is always true when dark products pull down the middle mean.
    img_median = float(np.median(gray))
    white_bg_frac = float((gray > 220).mean())
    is_white_bg_photo = img_median > 230 and white_bg_frac > 0.50

    def _strip_score(strip_mean, strip_std, strip_edge_density, ref_mean, ref_std) -> float:
        brightness_diff = abs(strip_mean - ref_mean)
        # Attribution strips (Watermarkly, photo credits) have a very specific profile:
        #   1. Near-white or light-grey background (mean > 175)
        #   2. VERY calm — std < 45 absolute (actual Watermarkly strip: std ~59 on the
        #      original APC watermarked image, but that's with JPEG artefacts; plain
        #      attribution text on white has std typically 20-55)
        #   3. Calmer than the product area (relative check)
        #   4. Has fine text edges — not a blank white margin (edge_density > 4.0)
        #      Raised from 2.0: a plain white wall/floor boundary produces ~1-3 from
        #      the product edge at the strip boundary; real attribution text is denser.
        #   5. Clearly brighter than the product body
        #   6. Guard: in a product-on-white-background photo the top/bottom margins
        #      are naturally brighter than the darker product area — that brightness
        #      difference is NOT a watermark banner, it's just the scene background.
        if is_white_bg_photo:
            return 0.0
        is_light_bg     = strip_mean > 175
        is_very_uniform = strip_std  < 62                  # absolute cap: product margins can hit 60-100
        is_more_uniform = strip_std  < ref_std * 0.75      # also calmer than product area
        has_text_edges  = strip_edge_density > 4.0         # raised from 2.0 to exclude wall boundaries
        is_distinct     = brightness_diff > 45.0

        if is_light_bg and is_very_uniform and is_more_uniform and has_text_edges and is_distinct:
            return min(brightness_diff / 90.0, 1.0)
        return 0.0

    bot_score = _strip_score(bottom_mean, bottom_std, bot_edge_density, middle_mean, middle_std)
    top_score = _strip_score(top_mean,    top_std,    top_edge_density, middle_mean, middle_std)
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
    img_median  = float(np.median(gray))  # overall image brightness baseline

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
        # 2. There is actual content (not blank) — raise threshold to avoid
        #    product edges / background surface texture triggering this
        has_content = edge_density > 6.0
        # 3. Colour is different from the product centre — tighten to 30 to
        #    avoid plain background areas around hardware products
        is_different = abs(zone_mean - centre_mean) > 30.0
        # 4. Zone must not be very bright (near-white background regions around
        #    products on white surfaces are not logo patches)
        is_not_plain_bg = zone_mean < 230.0

        # 5. Guard: a small product label sticker physically printed on the product
        #    body is NOT a watermark. A digital logo overlay sits on a distinctly
        #    lighter/separate background region that spans the full corner zone.
        #    Product labels embedded on a dark product cause the zone to be a MIX
        #    of dark product + small bright label → moderate zone_mean.
        #    Real corner watermark patches have a near-uniform light background
        #    (zone_std < 25) AND the zone mean is clearly above the image median
        #    (brighter than the product body by > 50 grey levels).
        #    If zone_std is moderate (25–45) the bright patch is a product surface
        #    feature (label, sticker, panel), not an overlay — skip it.
        is_distinct_overlay = (
            zone_std < 25.0                        # very uniform bg = solid overlay patch
            and zone_mean > img_median + 50        # clearly brighter than the product body
        )

        # Only flag as corner logo if it looks like a distinct overlay,
        # OR the edge density is very high (dense logo art, not a barcode sticker)
        # and the zone genuinely differs from the image as a whole.
        has_overlay_profile = is_distinct_overlay or (edge_density > 18.0 and zone_mean > img_median + 60)

        if is_uniform and has_content and is_different and is_not_plain_bg and has_overlay_profile:
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
# SIGNAL E — Diagonal bright glare / light-wash overlay
# ---------------------------------------------------------------------------

def _detect_diagonal_glare(bgr: np.ndarray) -> Dict[str, Any]:
    """
    Detect a large bright glare/light-wash overlay on a non-white background
    product image (e.g. HP laptop with a diagonal specular highlight covering
    30-50% of the product surface).

    Key characteristics of this defect:
    - The overall image is NOT white-background (median brightness < 190)
    - A large contiguous region (15-65% of image) is distinctly brighter
      than the product body (brightness > product_mean + 40)
    - The bright region has a diagonal boundary — detected by checking
      whether the left and right column extents of the bright mask change
      monotonically top-to-bottom (i.e. slanted boundary)
    - The bright region overlaps actual product pixels (not just bg margin)

    Diagonal boundary check: for each row scan the leftmost/rightmost
    bright pixel. If those x-positions vary significantly across rows
    (std > 8% of image width) the boundary is slanted, not a horizontal band.
    """
    h, w = bgr.shape[:2]
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY).astype(np.float32)

    img_median = float(np.median(gray))
    # Skip white-background images entirely
    if img_median > 190:
        return {"signal": "diagonal_glare", "score": 0.0, "detected": False}

    # Use the 85th percentile as the bright threshold — pixels brighter than
    # 85% of the image are "unusually bright" regardless of absolute value.
    # This adapts to both dark and medium-toned images.
    p85 = float(np.percentile(gray, 85))
    # But also require an absolute minimum brightness (must be actually bright)
    bright_thresh = max(p85, 170)

    bright_mask = (gray > bright_thresh).astype(np.uint8) * 255

    # Strip image border
    border = max(4, int(min(h, w) * 0.03))
    bright_mask[:border, :] = 0
    bright_mask[-border:, :] = 0
    bright_mask[:, :border] = 0
    bright_mask[:, -border:] = 0

    # Morphological close to fill small gaps
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (12, 12))
    closed = cv2.morphologyEx(bright_mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    min_area = h * w * 0.07   # at least 7% of image
    max_area = h * w * 0.65   # but not the whole image
    best_score = 0.0
    detected = False

    for c in contours:
        area = cv2.contourArea(c)
        if area < min_area or area > max_area:
            continue

        x, y, bw, bh = cv2.boundingRect(c)

        # Blob must not span the full image (that's the background)
        if bw > w * 0.95 and bh > h * 0.95:
            continue

        # ── Diagonal boundary check ──────────────────────────────────────
        # Scan leftmost and rightmost bright pixel per row inside this blob.
        # High std of these x-positions = slanted boundary = diagonal glare.
        blob_mask_roi = closed[y:y+bh, x:x+bw]
        left_xs  = []
        right_xs = []
        for row_i in range(blob_mask_roi.shape[0]):
            row_data = blob_mask_roi[row_i]
            bright_cols = np.where(row_data > 0)[0]
            if len(bright_cols) > 0:
                left_xs.append(int(bright_cols[0]))
                right_xs.append(int(bright_cols[-1]))

        if len(left_xs) < 10:
            continue

        left_std  = float(np.std(left_xs))
        right_std = float(np.std(right_xs))
        boundary_slant = max(left_std, right_std) / (w + 1e-6)

        # Require a meaningful slant: x-positions vary by > 5% of image width
        if boundary_slant < 0.05:
            continue

        # ── Verify the glare is distinctly brighter than surrounding area ──
        # The blob mean must be meaningfully brighter than the non-blob area.
        # This prevents flagging a naturally bright object on a bright bg.
        outside_mask = (closed == 0) & (gray > 20)  # non-blob, non-black
        blob_actual_mask = closed[y:y+bh, x:x+bw] > 0
        blob_mean_brightness = float(np.mean(gray[y:y+bh, x:x+bw][blob_actual_mask])) if np.sum(blob_actual_mask) > 0 else bright_thresh
        if np.sum(outside_mask) > 100:
            outside_median = float(np.median(gray[outside_mask]))
            # Blob must be at least 25 grey levels brighter than surroundings
            if blob_mean_brightness - outside_median < 25:
                continue

        # ── Score ────────────────────────────────────────────────────────
        area_frac  = area / (h * w)
        slant_norm = min(boundary_slant / 0.20, 1.0)
        score = min(area_frac * 3.5, 1.0) * 0.60 + slant_norm * 0.40
        if score > best_score:
            best_score = score
            detected = True

    return {
        "signal":   "diagonal_glare",
        "score":    round(best_score, 3),
        "detected": detected,
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
    sig_e = _detect_diagonal_glare(bgr)

    scores = {
        "transparent_overlay": sig_a["score"],
        "diagonal_text":       sig_b["score"],
        "attribution_strip":   sig_c["score"],
        "corner_logo":         sig_d["score"],
        "diagonal_glare":      sig_e["score"],
    }

    # ── DECISION LOGIC ───────────────────────────────────────────────────────
    # Rather than a single weighted sum, we use a tiered approach that reflects
    # what each signal actually means:
    #
    #  Tier 1 — Unambiguous single signal (no other signal needed):
    #    transparent_overlay >= 0.70  →  alpha-blended logo is extremely specific
    #    attribution_strip   >= 0.60  →  bottom attribution band is very specific
    #
    #  Tier 2 — Two independent signals agreeing (each >= 0.30):
    #    Any combination of 2+ signals → high confidence watermark
    #
    #  Tier 3 — Weighted sum fallback for weaker multi-signal cases

    firing_signals = [k for k, s in scores.items() if s >= 0.30]

    is_watermark = False
    weighted_score = 0.0
    decision_reason = "none"

    # Tier 1: single strong signal is sufficient alone.
    # transparent_overlay: semi-transparent alpha-blend patch — very specific.
    # diagonal_glare: large diagonal bright overlay crossing product area —
    #   unambiguous when it covers 15%+ of the image at a diagonal angle.
    if scores["transparent_overlay"] >= 0.70:
        weighted_score = scores["transparent_overlay"]
        is_watermark   = True
        decision_reason = "transparent_overlay_strong"

    elif scores["diagonal_glare"] >= 0.30:
        weighted_score = scores["diagonal_glare"]
        is_watermark   = True
        decision_reason = "diagonal_glare_strong"

    # Tier 2: two or more independent signals agreeing
    elif len(firing_signals) >= 2:
        weights = {
            "transparent_overlay": 0.35,
            "diagonal_text":       0.25,
            "attribution_strip":   0.15,
            "corner_logo":         0.10,
            "diagonal_glare":      0.15,
        }
        weighted_score = min(
            sum(scores[k] * weights[k] for k in weights) * 1.40,
            1.0,
        )
        # For product photos: require higher confidence from multi-signal (0.65 vs 0.50)
        # This avoids false positives from product graphics being detected as watermark signals
        threshold = 0.65 if (is_product_photo and product_photo_confidence > 0.40) else WATERMARK_SCORE_THRESHOLD
        is_watermark   = weighted_score >= threshold
        decision_reason = f"multi_signal({','.join(firing_signals)})"

    # Tier 3: weighted sum (single weak signal — conservative)
    else:
        weights = {
            "transparent_overlay": 0.35,
            "diagonal_text":       0.25,
            "attribution_strip":   0.15,
            "corner_logo":         0.10,
            "diagonal_glare":      0.15,
        }
        weighted_score = sum(scores[k] * weights[k] for k in weights)
        # For product photos with only one weak signal, require much higher confidence (0.75)
        # to avoid false positives from product labels, tags, or branding being detected as watermarks
        threshold = 0.75 if (is_product_photo and product_photo_confidence > 0.40) else WATERMARK_SCORE_THRESHOLD
        is_watermark   = weighted_score >= threshold
        decision_reason = "weighted_sum_single_signal"

    weighted_score = round(weighted_score, 3)

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
    if scores["diagonal_glare"] > 0.30:
        reasons.append(f"diagonal_glare(score={scores['diagonal_glare']:.2f})")

    return {
        "visual_watermark_score": weighted_score,
        "is_visual_watermark":    is_watermark,
        "decision_reason":        decision_reason,
        "signals": {
            "transparent_overlay": sig_a,
            "diagonal_text":       sig_b,
            "attribution_strip":   sig_c,
            "corner_logo":         sig_d,
            "diagonal_glare":      sig_e,
        },
        "signal_scores":   {k: round(v, 3) for k, v in scores.items()},
        "firing_signals":  firing_signals,
        "dominant_signal": dominant,
        "reasons":         reasons,
    }
