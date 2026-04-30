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
from typing import Dict


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


def compute_screenshot_score(
    ocr_result: Dict,
    clip_product_check: Dict,
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
