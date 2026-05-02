"""
Confidence scoring engine.

Aggregates weighted signals from all four pipeline stages into a
single 0–100 confidence score and maps it to a boolean decision.
"""

from typing import Dict, List, Tuple

from utils.regex_patterns import PATTERN_WEIGHTS

# ---------------------------------------------------------------------------
# STAGE WEIGHTS
# How much each pipeline stage contributes to the final score.
# These sum to 1.0; adjust to tune precision/recall trade-off.
# ---------------------------------------------------------------------------
STAGE_WEIGHTS: Dict[str, float] = {
    "stage0_native":    0.30,   # Body-native text region analysis
    "stage2_semantic":  0.25,   # Semantic context matching
    "stage3_promo":     0.45,   # Promotional pattern engine (highest weight)
}

# ---------------------------------------------------------------------------
# DECISION THRESHOLDS
# ---------------------------------------------------------------------------
THRESHOLD_REJECT: int  = 60   # score >= 60  → is_promotional = True
THRESHOLD_REVIEW: int  = 35   # score 35–59  → flag_for_review = True

# Bonus applied when >50% of OCR tokens are unmatched by the product vocabulary
# AND promotional patterns also fired (double evidence).
UNMATCHED_RATIO_BONUS: int = 15

# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def compute_pattern_score(promo_hits: List[Dict]) -> int:
    """
    Sum weights of unique fired pattern types; each type counted once.
    Returns raw score (not capped) — caller caps at 100.
    """
    fired_types = {h["type"] for h in promo_hits}
    return sum(PATTERN_WEIGHTS.get(t, 10) for t in fired_types)


def apply_unmatched_bonus(
    base_score: int,
    unmatched_tokens: List[str],
    total_tokens: int,
    promo_hits: List[Dict],
) -> int:
    """Add unmatched-ratio bonus when evidence is doubly confirmed."""
    if not promo_hits or total_tokens == 0:
        return base_score
    ratio = len(unmatched_tokens) / total_tokens
    return base_score + UNMATCHED_RATIO_BONUS if ratio > 0.50 else base_score


def native_text_penalty(native_fraction: float) -> float:
    """
    Returns a multiplier (0.0–1.0) to DOWN-SCALE the promo score when most
    OCR text was classified as body-native.

    native_fraction = native_box_count / total_box_count

    If 80%+ of boxes are native → multiply score by 0.20 (near-zero).
    If 0% native              → no penalty (multiplier = 1.0).
    """
    # Linear ramp: 0 native → 1.0, fully native → 0.15
    return max(0.15, 1.0 - native_fraction * 0.85)


def compute_final_score(
    pattern_score: int,
    native_fraction: float,
    has_overlay_boxes: bool,
    semantic_unmatched_ratio: float,
    promo_hits: List[Dict],
    total_tokens: int,
) -> Tuple[int, bool, bool]:
    """
    Combine all signals into a final confidence score.

    Args:
        pattern_score          : raw score from promotional patterns
        native_fraction        : fraction of OCR boxes classified as native
        has_overlay_boxes      : True if ANY box was explicitly classified overlay
        semantic_unmatched_ratio: fraction of tokens not in product vocabulary
        promo_hits             : list of matched promotional patterns
        total_tokens           : total unique OCR tokens examined

    Returns:
        (confidence_score 0–100, is_promotional bool, flag_for_review bool)
    """
    score = pattern_score

    # Stage 0 penalty: if most text is native → drastically reduce score
    if not has_overlay_boxes:
        score = int(score * native_text_penalty(native_fraction))

    # Unmatched-token bonus
    unmatched_count = int(semantic_unmatched_ratio * total_tokens)
    unmatched_tokens_proxy = ["x"] * unmatched_count  # proxy list for length check
    score = apply_unmatched_bonus(score, unmatched_tokens_proxy, total_tokens, promo_hits)

    # Cap
    score = min(score, 100)

    return (
        score,
        score >= THRESHOLD_REJECT,
        THRESHOLD_REVIEW <= score < THRESHOLD_REJECT,
    )
