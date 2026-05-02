"""
Stage 0 helper — Computer-Vision Layout Analyser.

Analyses the global image layout using OpenCV to detect structural patterns
that indicate promotional overlays vs. clean product shots:

  - Banner strips at top/bottom
  - Corner price/offer badges
  - Full-width text regions
  - High-saturation coloured regions (typical of promo stickers)
  - Horizontal divider lines (common in seller info panels)

Returns a dict of layout signals consumed by native_text_region_detector.
"""

from __future__ import annotations

import cv2
import numpy as np
from PIL import Image
from typing import Dict, Any, List, Tuple


def _pil_to_bgr(image: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _region_saturation(hsv: np.ndarray, y1: int, y2: int, x1: int, x2: int) -> float:
    """Mean saturation (0–255) of a rectangular region in HSV image."""
    region = hsv[y1:y2, x1:x2, 1]
    return float(region.mean()) if region.size > 0 else 0.0


def detect_banner_strips(
    image: Image.Image,
) -> Dict[str, Any]:
    """
    Detect horizontal banner strips at the top and bottom of the image.

    A banner strip is a horizontal region that:
    - Spans >= 70% of image width
    - Has noticeably different mean brightness vs. the image centre
    - Is located in the top or bottom 15% of the image

    Returns
    -------
    {
        "has_top_banner"    : bool
        "has_bottom_banner" : bool
        "top_banner_height" : int   (pixels, 0 if not detected)
        "bot_banner_height" : int
    }
    """
    bgr = _pil_to_bgr(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    edge_zone = int(h * 0.15)
    centre_mean = float(gray[edge_zone: h - edge_zone, :].mean())

    def _strip_differs(region: np.ndarray) -> bool:
        if region.size == 0:
            return False
        m = float(region.mean())
        return abs(m - centre_mean) > 18  # brightness diff threshold

    top_region = gray[:edge_zone, :]
    bot_region = gray[h - edge_zone:, :]

    has_top = _strip_differs(top_region)
    has_bot = _strip_differs(bot_region)

    # Refine: measure how many rows of the edge zone differ significantly
    def _banner_height(region: np.ndarray) -> int:
        count = 0
        for row in region:
            if abs(float(row.mean()) - centre_mean) > 15:
                count += 1
        return count

    return {
        "has_top_banner":    has_top,
        "has_bottom_banner": has_bot,
        "top_banner_height": _banner_height(top_region) if has_top else 0,
        "bot_banner_height": _banner_height(bot_region) if has_bot else 0,
    }


def detect_coloured_regions(
    image: Image.Image,
) -> Dict[str, Any]:
    """
    Detect high-saturation coloured regions that are characteristic of
    promotional stickers, price badges, and offer banners.

    Returns
    -------
    {
        "has_coloured_overlay"  : bool
        "coloured_region_count" : int
        "corner_badge_detected" : bool   — coloured blob in any corner
    }
    """
    bgr = _pil_to_bgr(image)
    hsv = cv2.cvtColor(bgr, cv2.COLOR_BGR2HSV)
    h, w = hsv.shape[:2]

    # Threshold: pixels with saturation > 100 and value > 80 are "colourful"
    sat_mask = (hsv[:, :, 1] > 100) & (hsv[:, :, 2] > 80)
    sat_uint8 = sat_mask.astype(np.uint8) * 255

    # Morphological close to merge nearby colourful pixels into blobs
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
    closed = cv2.morphologyEx(sat_uint8, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    # Keep blobs that are at least 1% of image area
    min_area = h * w * 0.01
    large_blobs = [c for c in contours if cv2.contourArea(c) >= min_area]

    # Check if any large blob occupies a corner (top-left, top-right,
    # bottom-left, bottom-right quadrant)
    corner_size = 0.25
    corners = [
        (0, 0, int(w * corner_size), int(h * corner_size)),           # TL
        (int(w * (1 - corner_size)), 0, w, int(h * corner_size)),     # TR
        (0, int(h * (1 - corner_size)), int(w * corner_size), h),     # BL
        (int(w * (1 - corner_size)), int(h * (1 - corner_size)), w, h),  # BR
    ]
    corner_badge = False
    for c in large_blobs:
        bx, by, bw, bh = cv2.boundingRect(c)
        cx, cy = bx + bw // 2, by + bh // 2
        for (x1, y1, x2, y2) in corners:
            if x1 <= cx <= x2 and y1 <= cy <= y2:
                corner_badge = True
                break

    return {
        "has_coloured_overlay":  len(large_blobs) > 0,
        "coloured_region_count": len(large_blobs),
        "corner_badge_detected": corner_badge,
    }


def detect_horizontal_lines(image: Image.Image) -> Dict[str, Any]:
    """
    Detect strong horizontal divider lines — common in seller info panels
    that separate product image from contact/price overlay sections.

    Returns
    -------
    {
        "has_divider_lines"  : bool
        "divider_line_count" : int
    }
    """
    bgr = _pil_to_bgr(image)
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape

    # Horizontal Sobel edge detection
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 0, 1, ksize=3)
    abs_sobel = np.abs(sobelx).astype(np.uint8)

    # Threshold to binary
    _, binary = cv2.threshold(abs_sobel, 50, 255, cv2.THRESH_BINARY)

    # Look for rows where a large fraction of pixels are edge-active
    row_sums = binary.sum(axis=1) / 255
    strong_rows = int((row_sums > w * 0.6).sum())

    return {
        "has_divider_lines":  strong_rows >= 2,
        "divider_line_count": strong_rows,
    }


def analyse_layout(image: Image.Image) -> Dict[str, Any]:
    """
    Run all CV layout checks and return a merged signal dict.

    Downstream stages read this to decide how aggressively to penalise
    the text regions found by OCR.
    """
    banners  = detect_banner_strips(image)
    colours  = detect_coloured_regions(image)
    dividers = detect_horizontal_lines(image)

    # Aggregate: is there any structural overlay evidence?
    overlay_evidence = (
        banners["has_top_banner"]
        or banners["has_bottom_banner"]
        or colours["corner_badge_detected"]
        or colours["has_coloured_overlay"]
        or dividers["has_divider_lines"]
    )

    return {
        **banners,
        **colours,
        **dividers,
        "layout_has_overlay_evidence": overlay_evidence,
    }
