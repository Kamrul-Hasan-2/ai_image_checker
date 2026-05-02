"""
Validator — orchestrates all four pipeline stages and produces the
final structured JSON result.

Pipeline order:
  Stage 0a : CV layout analysis   (cv_layout_analyzer)
  Stage 0b : Native text classification (native_text_region_detector)
  Stage 1  : OCR extraction       (ocr_service)       ← already done upstream
  Stage 2  : Semantic matching    (semantic_matcher)
  Stage 3  : Promotional patterns (promotional_detector)
  Final    : Confidence engine    (confidence_engine)

The caller passes pre-downloaded image + OCR result to avoid redundant
model inference.  If called standalone, it downloads and runs OCR itself.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from PIL import Image

from services import (
    cv_layout_analyzer,
    native_text_region_detector,
    ocr_service,
    promotional_detector,
    semantic_matcher,
)
from services.image_downloader import download_image
from utils.confidence_engine import compute_final_score


# ---------------------------------------------------------------------------
# REASON BUILDER
# ---------------------------------------------------------------------------

def _build_reason(
    promo_flags: List[Dict],
    native_texts: List[str],
    matched_tokens: List[str],
    unmatched_tokens: List[str],
    is_promotional: bool,
    confidence: int,
    flag_for_review: bool,
) -> str:
    if not is_promotional and not flag_for_review:
        if not unmatched_tokens:
            return (
                f"All {len(matched_tokens)} OCR tokens match the product "
                "vocabulary. No unmatched tokens and no promotional patterns "
                "detected. Image is safe."
            )
        native_note = (
            f" {len(native_texts)} text box(es) classified as body-native "
            "(product labels/specs)."
            if native_texts
            else ""
        )
        return (
            f"{len(matched_tokens)} OCR tokens match product context; "
            f"{len(unmatched_tokens)} unmatched tokens found but zero "
            f"promotional patterns detected.{native_note} Image is safe."
        )

    type_summary = ", ".join(sorted({h["type"] for h in promo_flags}))
    examples = "; ".join(
        f'"{h["matched"]}" ({h["type"]})' for h in promo_flags[:4]
    )
    decision = "PROMOTIONAL" if is_promotional else "REVIEW_NEEDED"
    return (
        f"{decision} — confidence {confidence}/100. "
        f"Pattern types fired: [{type_summary}]. "
        f"Examples: {examples}. "
        f"Unmatched OCR tokens: {unmatched_tokens[:8]}."
    )


# ---------------------------------------------------------------------------
# MAIN PUBLIC FUNCTION
# ---------------------------------------------------------------------------

def validate_image(
    image_url: str,
    title: str,
    description: str,
    category: str,
    image_id: int = 0,
    preloaded_image: Optional[Image.Image] = None,
    preloaded_ocr: Optional[Dict] = None,
    use_semantic: bool = True,
) -> Dict[str, Any]:
    """
    Run the full 4-stage promotional text validation pipeline.

    Args:
        image_url       : public image URL (used if preloaded_image is None)
        title           : product title
        description     : product description
        category        : product category
        image_id        : included in the response for traceability
        preloaded_image : PIL Image (RGB) — skip download if provided
        preloaded_ocr   : output of ocr_service.extract_text() — skip OCR if provided
        use_semantic    : whether to run sentence-transformer tier in Stage 2

    Returns
    -------
    {
        "image_id"            : int
        "ocr_texts"           : list[str]
        "body_native_texts"   : list[str]
        "matched_product_texts": list[str]
        "overlay_unmatched_texts": list[str]
        "promotional_flags"   : list[dict]
        "is_promotional"      : bool
        "flag_for_review"     : bool
        "confidence_score"    : int  (0–100)
        "reason"              : str
        "_debug"              : dict  (intermediate signals for audit)
    }
    """

    # ── STAGE 1: Download + OCR ──────────────────────────────────────────
    image = preloaded_image or download_image(image_url)
    ocr   = preloaded_ocr   or ocr_service.extract_text(image)

    img_width  = ocr.get("img_width",  image.size[0])
    img_height = ocr.get("img_height", image.size[1])
    full_text  = ocr.get("full_text", "")
    ocr_texts  = [b["text"] for b in ocr.get("extracted_data", []) if b.get("text")]

    # ── STAGE 0a: CV layout analysis ─────────────────────────────────────
    layout = cv_layout_analyzer.analyse_layout(image)

    # ── STAGE 0b: Native text classification ─────────────────────────────
    region_result = native_text_region_detector.analyse_text_regions(
        ocr, image, layout
    )
    native_texts   = region_result["native_texts"]
    overlay_texts  = region_result["overlay_texts"]
    native_fraction = region_result["native_fraction"]
    has_overlay    = region_result["has_overlay"]

    # ── STAGE 2: Semantic token matching ─────────────────────────────────
    # Only classify text from overlay + ambiguous boxes.
    # Native-box texts are already cleared — no point running vocab match on them.
    non_native_texts = overlay_texts + [
        b["text"] for b in region_result["ambiguous_boxes"]
    ]
    # If no overlay/ambiguous boxes, fall back to all OCR text to avoid
    # accidentally missing promotional content hidden in ambiguous boxes.
    texts_for_matching = non_native_texts if non_native_texts else ocr_texts

    semantic = semantic_matcher.classify_tokens(
        ocr_texts=texts_for_matching,
        title=title,
        description=description,
        category=category,
        use_semantic=use_semantic,
    )
    matched_tokens   = semantic["matched_tokens"]
    unmatched_tokens = semantic["unmatched_tokens"]
    total_tokens     = semantic["total_unique_tokens"]
    unmatched_ratio  = semantic["unmatched_ratio"]

    # ── STAGE 3: Promotional pattern engine ──────────────────────────────
    promo = promotional_detector.detect(
        overlay_texts=overlay_texts,
        unmatched_tokens=unmatched_tokens,
        full_ocr_text=full_text,
    )
    promo_flags = promo["promotional_flags"]
    raw_score   = promo["raw_score"]

    # ── FINAL: Confidence engine ──────────────────────────────────────────
    confidence, is_promotional, flag_for_review = compute_final_score(
        pattern_score=raw_score,
        native_fraction=native_fraction,
        has_overlay_boxes=has_overlay,
        semantic_unmatched_ratio=unmatched_ratio,
        promo_hits=promo_flags,
        total_tokens=total_tokens,
    )

    # ── Overlay unmatched texts (what Stage 3 actually examined) ──────────
    overlay_unmatched = overlay_texts + [
        t for t in unmatched_tokens if t not in matched_tokens
    ]

    reason = _build_reason(
        promo_flags, native_texts, matched_tokens, unmatched_tokens,
        is_promotional, confidence, flag_for_review,
    )

    return {
        "image_id":               image_id,
        "ocr_texts":              ocr_texts,
        "body_native_texts":      native_texts,
        "matched_product_texts":  matched_tokens,
        "overlay_unmatched_texts": overlay_unmatched,
        "promotional_flags":      promo_flags,
        "is_promotional":         is_promotional,
        "flag_for_review":        flag_for_review,
        "confidence_score":       confidence,
        "reason":                 reason,
        "_debug": {
            "layout":             layout,
            "native_fraction":    native_fraction,
            "has_overlay_boxes":  has_overlay,
            "overlay_boxes":      region_result["overlay_texts"],
            "ambiguous_boxes":    [b["text"] for b in region_result["ambiguous_boxes"]],
            "unmatched_ratio":    unmatched_ratio,
            "raw_promo_score":    raw_score,
            "fired_types":        promo["fired_types"],
            "native_box_count":   len(region_result["native_boxes"]),
            "overlay_box_count":  len(region_result["overlay_boxes"]),
        },
    }
