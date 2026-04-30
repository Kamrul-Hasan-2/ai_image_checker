"""
Screenshot Detection Module
Detects website/app screenshots uploaded as product images.

Plugs into main.py after OCR and CLIP steps. Uses already-computed
ocr_result fields — no redundant inference calls.

Detection targets (BD marketplace context):
  - Facebook Marketplace / Facebook post screenshots
  - WhatsApp chat screenshots with product listings
  - Daraz / Bikroy / Shajgoj product page screenshots
  - Mobile app UI screenshots
"""

import re
from typing import Dict, List, Any


# ── HARD KEYWORDS ─────────────────────────────────────────────────────────────
# UI-exclusive terms that cannot appear on physical product packaging.
# Each hit contributes 0.6 to screenshot_score, capped at 0.7 total.
# IMPORTANT: checked against lowercased OCR text.

_HARD_UI_KEYWORDS = [
    # Stock / listing status — unambiguous website UI
    "out of stock", "in stock", "out of stock", "low stock",
    "add to cart", "add to bag", "buy now", "shop now", "checkout",
    "view details", "see more", "load more",
    "free delivery", "free shipping", "home delivery",
    "login", "log in", "sign in", "sign up", "register", "create account",
    "forgot password", "reset password",
    "my account", "my orders", "my wishlist", "my cart",
    "filter by", "sort by", "search results", "items found",
    "write a review", "customer reviews", "ratings & reviews",
    "product description", "specifications", "in the box",
    "seller:", "sold by", "fulfilled by", "ships from",
    "add to wishlist", "save for later",
    "continue shopping", "proceed to checkout",
    # Webpage metadata fields — only appear on product listing pages
    "updated:", "updated :", "last updated",
    # BD-specific marketplace UI
    "bikroy.com", "daraz.com.bd", "shajgoj.com", "chaldal.com",
    "ajkerdeal.com", "othoba.com", "bdshop.com",
    # Facebook / social media UI
    "marketplace", "see all", "see less",
    "sponsored", "suggested for you",
    "message seller",
    # Bengali UI terms
    "কিনুন", "কার্টে যোগ করুন", "অর্ডার করুন",
    "ডেলিভারি", "ফ্রি ডেলিভারি", "স্টক নেই",
    "লগইন", "সাইন ইন", "নিবন্ধন",
]

# ── SOFT KEYWORDS ─────────────────────────────────────────────────────────────
# Moderate signals. Each hit adds 0.08, capped at 0.25 total.

_SOFT_UI_KEYWORDS = [
    "www.", "http://", "https://", ".com", ".com.bd", ".net", ".org",
    "id:", "sku:", "status:", "availability:",
    "rating:", "reviews:", "questions:",
    "breadcrumb", "category:", "subcategory:",
    "page 1", "page 2", "next page", "previous",
    "items per page", "showing",
]

# ── NEAR-CERTAIN COMBOS ───────────────────────────────────────────────────────
# Two or more of these in the same image = almost certain webpage screenshot.
# Each is individually ambiguous; together they are decisive.
_COMBO_FIELDS = ["id:", "status:", "updated:", "sku:", "availability:"]

# Breadcrumb regex: matches "Word > Word > Word" or "Word » Word » Word"
# Handles OCR spacing like "Security and Industry > Meter & Scale > Weight Machine"
_BREADCRUMB_RE = re.compile(
    r'\b[\w][\w &]{1,30}\s*[>»›]\s*[\w][\w &]{1,30}\s*[>»›]\s*[\w][\w &]{1,30}\b'
)

# URL-in-text regex: catches partial URLs OCR extracts from address bars
_URL_RE = re.compile(
    r'(https?://|www\.)\s*[\w\-\.]+\s*\.\s*(com|net|org|bd|io|co)',
    re.IGNORECASE
)


def analyse_text_layout(
    ocr_boxes: List[Dict[str, Any]],
    img_width: int,
    img_height: int,
) -> Dict[str, Any]:
    """
    Decide whether OCR text looks like UI/screenshot text or product text,
    using only bounding-box position and size — no ML, no external libraries.

    Rules (plain English):
      1. UI text is wide  → box covers > 50% of image width
      2. UI text is edge  → box centre sits in top or bottom 15% of image
      3. Product text is centred → box centre sits in middle 70% of image

    A box that is BOTH wide AND near an edge is almost certainly a nav bar,
    header, or footer — never a brand name printed on a physical product.

    Args:
        ocr_boxes  : list of {"text": str, "bbox": [[x,y],[x,y],[x,y],[x,y]]}
                     (EasyOCR polygon format — 4 corner points)
        img_width  : image width  in pixels
        img_height : image height in pixels

    Returns:
        dict with:
            is_ui_layout   (bool)  – True means screenshot-like layout
            ui_box_count   (int)   – how many boxes triggered the rule
            total_boxes    (int)   – total boxes examined
            layout_score   (float) – 0.0–1.0, fraction of boxes that look like UI
    """

    # Safety: skip if image dimensions are unknown or no boxes present
    if not ocr_boxes or img_width <= 0 or img_height <= 0:
        return {"is_ui_layout": False, "ui_box_count": 0,
                "total_boxes": 0, "layout_score": 0.0}

    # Threshold constants — see Section 4 for why these values are chosen
    EDGE_ZONE   = 0.15   # top or bottom 15% of image height = "edge zone"
    WIDE_RATIO  = 0.50   # box wider than 50% of image width = "wide text"
    UI_FRACTION = 0.35   # if >35% of all boxes are UI-like → flag layout

    ui_box_count = 0     # boxes that look like UI (wide AND near edge)
    centre_box_count = 0 # boxes that look like product text (centred)

    for box in ocr_boxes:
        bbox = box.get("bbox", [])
        if not bbox or len(bbox) < 2:
            continue

        # EasyOCR gives 4 corner points [[x,y], [x,y], [x,y], [x,y]]
        # Extract the bounding rectangle from those corners
        xs = [pt[0] for pt in bbox]
        ys = [pt[1] for pt in bbox]
        box_left   = min(xs)
        box_right  = max(xs)
        box_top    = min(ys)
        box_bottom = max(ys)

        box_width  = box_right - box_left
        box_centre_y = (box_top + box_bottom) / 2   # vertical centre of this box

        # Rule 1: is this box wide? (covers more than 50% of image width)
        is_wide = (box_width / img_width) > WIDE_RATIO

        # Rule 2: is this box near the top or bottom edge?
        near_top    = box_centre_y < img_height * EDGE_ZONE
        near_bottom = box_centre_y > img_height * (1.0 - EDGE_ZONE)
        is_near_edge = near_top or near_bottom

        # A box that is wide AND near an edge = UI chrome (nav bar, footer, etc.)
        if is_wide and is_near_edge:
            ui_box_count += 1

        # Track centred boxes for context (product text is usually centred)
        is_centred_vertically = (
            img_height * 0.15 < box_centre_y < img_height * 0.85
        )
        if is_centred_vertically and not is_wide:
            centre_box_count += 1

    total_boxes  = len(ocr_boxes)
    layout_score = ui_box_count / total_boxes if total_boxes > 0 else 0.0

    # Flag as UI layout if enough boxes trigger the rule
    is_ui_layout = layout_score >= UI_FRACTION

    return {
        "is_ui_layout":    is_ui_layout,
        "ui_box_count":    ui_box_count,
        "centre_box_count": centre_box_count,
        "total_boxes":     total_boxes,
        "layout_score":    round(layout_score, 3),
    }


def compute_screenshot_score(
    ocr_result: Dict,
    clip_product_check: Dict,
    img_width: int = 0,
    img_height: int = 0,
) -> Dict:
    """
    Compute a screenshot likelihood score using already-computed pipeline outputs.
    No new model inference — uses fields from ocr_service and clip_service.

    Args:
        ocr_result:        Output of OCRService.extract_text()
        clip_product_check: Output of CLIPService.detect_product_photo()

    Returns:
        Dict with:
            screenshot_score  (float 0.0–1.0)
            is_screenshot     (bool, score >= 0.70)
            flag_for_review   (bool, score 0.40–0.69)
            reasons           (list[str])  — for debug logging
    """
    score = 0.0
    reasons = []

    full_text: str = ocr_result.get("full_text", "").lower()
    ocr_box_count: int = ocr_result.get("text_count", 0)
    original_text: str = ocr_result.get("full_text", "")  # case-preserved for regex

    # ── EARLY SIGNALS: check hard keywords and combo fields FIRST ────────────
    # This lets us detect screenshot before applying the CLIP sensitivity guard.
    # CLIP often misclassifies webpage screenshots as product photos (it sees
    # the product in the image, not the surrounding UI chrome).

    # Hard keyword check
    hard_hits = [kw for kw in _HARD_UI_KEYWORDS if kw in full_text]

    # Combo field check: "ID: + Status:" or "ID: + Updated:" = webpage metadata
    combo_hits = [f for f in _COMBO_FIELDS if f in full_text]
    has_combo = len(combo_hits) >= 2

    # Breadcrumb check
    has_breadcrumb = bool(_BREADCRUMB_RE.search(original_text))

    # ── GUARD: only reduce sensitivity if CLIP is confident AND no strong
    # screenshot signals are already present.
    # Rationale: CLIP sees the product object (scale, phone) and calls it a
    # product photo — but the page chrome around it is the real signal.
    # If we already have hard keywords or a breadcrumb, CLIP is wrong; ignore it.
    product_score: float = clip_product_check.get("product_score", 0.0)
    promo_score: float = clip_product_check.get("promo_score", 0.0)
    clip_says_product = (
        clip_product_check.get("is_product_photo", False)
        and product_score > 0.55
        and product_score > promo_score * 1.8
    )
    # Only trust CLIP's product verdict when no strong UI signals contradict it.
    strong_ui_present = bool(hard_hits) or has_breadcrumb or has_combo
    sensitivity = 0.5 if (clip_says_product and not strong_ui_present) else 1.0

    # ── SIGNAL A: Hard UI keyword hits ───────────────────────────────────────
    if hard_hits:
        hard_contribution = min(len(hard_hits) * 0.6, 0.70) * sensitivity
        score += hard_contribution
        reasons.append(f"hard_ui_keywords({len(hard_hits)}): {hard_hits[:3]}")

    # ── SIGNAL B1: Breadcrumb navigation pattern ──────────────────────────────
    if has_breadcrumb:
        score += 0.40 * sensitivity
        reasons.append("breadcrumb_pattern_detected")

    # ── SIGNAL B2: Webpage metadata combo (ID: + Status: + Updated: etc.) ─────
    # These three fields together are unambiguous product-listing page metadata.
    if has_combo:
        score += 0.35 * sensitivity
        reasons.append(f"webpage_metadata_combo({combo_hits})")

    # ── SIGNAL B3: URL in image text (address bar / link text) ───────────────
    if _URL_RE.search(original_text):
        score += 0.20 * sensitivity
        reasons.append("url_in_ocr_text")

    # ── SIGNAL B4: E-commerce UI (already computed — free) ───────────────────
    if ocr_result.get("has_ecommerce_ui", False):
        score += 0.25 * sensitivity
        reasons.append("ecommerce_ui_detected_by_ocr")

    # ── SIGNAL B5: Soft keyword cluster ──────────────────────────────────────
    soft_hits = [kw for kw in _SOFT_UI_KEYWORDS if kw in full_text]
    if soft_hits:
        soft_contribution = min(len(soft_hits) * 0.08, 0.20) * sensitivity
        score += soft_contribution
        reasons.append(f"soft_ui_keywords({len(soft_hits)}): {soft_hits[:3]}")

    # ── SIGNAL B6: High OCR box count ────────────────────────────────────────
    # Webpage screenshots have many text regions; product photos have few.
    if ocr_box_count >= 20:
        score += 0.25 * sensitivity
        reasons.append(f"high_ocr_box_count({ocr_box_count})")
    elif ocr_box_count >= 14:
        score += 0.12 * sensitivity
        reasons.append(f"moderate_ocr_box_count({ocr_box_count})")

    # ── SIGNAL C: CLIP promo signal ───────────────────────────────────────────
    if promo_score > 0.35 and not (clip_says_product and not strong_ui_present):
        clip_contribution = min((promo_score - 0.35) * 1.5, 0.25)
        score += clip_contribution
        reasons.append(f"clip_promo_signal({promo_score:.2f})")

    # ── SIGNAL D: Bounding-box layout analysis ────────────────────────────────
    # Wide text boxes pinned to the top/bottom edge = nav bars, footers, headers.
    # This catches screenshots where OCR keywords are missing (e.g. image-rendered UI).
    if img_width > 0 and img_height > 0:
        ocr_boxes = ocr_result.get("extracted_data", [])
        layout = analyse_text_layout(ocr_boxes, img_width, img_height)
        if layout["is_ui_layout"]:
            layout_contribution = min(layout["layout_score"] * 0.5, 0.30) * sensitivity
            score += layout_contribution
            reasons.append(
                f"ui_layout(ui_boxes={layout['ui_box_count']}/"
                f"{layout['total_boxes']}, score={layout['layout_score']:.2f})"
            )

    # ── NORMALIZE ─────────────────────────────────────────────────────────────
    score = min(score, 1.0)

    is_screenshot = score >= 0.70
    flag_for_review = 0.40 <= score < 0.70

    return {
        "screenshot_score": round(score, 3),
        "is_screenshot": is_screenshot,
        "flag_for_review": flag_for_review,
        "reasons": reasons,
        "ocr_box_count": ocr_box_count,
        "sensitivity_reduced": clip_says_product and not strong_ui_present,
    }


def apply_screenshot_decision(
    existing_result: Dict,
    screenshot_detection: Dict,
) -> Dict:
    """
    Merge screenshot detection result into the existing moderation result.
    Overwrites screen_short and risk_level fields only.
    All other fields (blur, watermark, promotional) are untouched.

    Args:
        existing_result:      The result dict built by process_single_image()
        screenshot_detection: Output of compute_screenshot_score()

    Returns:
        Updated result dict
    """
    score = screenshot_detection["screenshot_score"]
    is_screenshot = screenshot_detection["is_screenshot"]
    flag_for_review = screenshot_detection["flag_for_review"]

    if is_screenshot:
        # Hard reject — score >= 0.70
        existing_result["screen_short"] = 8
        # A confirmed screenshot is NOT a promotional image — the "promo text"
        # signals (price, phone, UI buttons) are webpage chrome, not seller ads.
        # Clearing this prevents double-penalising and stops false promotional flags.
        existing_result["promotional_text"] = 0
    elif flag_for_review:
        # Soft flag — score 0.40–0.69 → value 4 signals "needs review"
        if existing_result.get("screen_short", 0) == 0:
            existing_result["screen_short"] = 4
    # else: leave screen_short as-is (0 = clean, or already set by quality_service)

    # Recalculate risk_level to account for updated fields
    existing_result["risk_level"] = max(
        existing_result.get("blur_image", 0),
        existing_result.get("screen_short", 0),
        existing_result.get("promotional_text", 0),
        existing_result.get("watermark", 0),
    )

    # Append screenshot debug info to _debug block
    debug = existing_result.get("_debug", {})
    debug["screenshot_score"] = score
    debug["screenshot_reasons"] = screenshot_detection["reasons"]
    debug["screenshot_ocr_box_count"] = screenshot_detection["ocr_box_count"]
    debug["screenshot_sensitivity_reduced"] = screenshot_detection["sensitivity_reduced"]
    existing_result["_debug"] = debug

    return existing_result
