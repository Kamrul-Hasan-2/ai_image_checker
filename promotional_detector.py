"""
Promotional Text Detection Module
==================================
Step 3 of the AI pipeline: determine whether OCR-extracted text that does
NOT belong to the product's own title/description/category is promotional.

Architecture
------------
Step 1  Build an "allowed vocabulary" from title + description + category.
Step 2  Split OCR tokens into matched (product text) vs unmatched (unknown).
Step 3  Run the promotional engine only on unmatched tokens.

This keeps false-positive rate low: text printed on the physical product
body (brand, model, specs) is whitelisted by Step 1 before Step 3 runs.

Dependencies: rapidfuzz (fuzzy matching) — already in most ML envs.
No sentence-transformers needed: the word-overlap approach is fast, cheap,
and accurate enough for this use-case at production scale.
"""

import re
import unicodedata
from typing import Dict, List, Set, Tuple

from rapidfuzz import fuzz

# ---------------------------------------------------------------------------
# 1. NORMALISATION HELPERS
# ---------------------------------------------------------------------------

# Characters to strip when normalising text for comparison
_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")


def normalise(text: str) -> str:
    """
    Lowercase → strip accents → remove punctuation → collapse spaces.
    Applied identically to OCR output and to product context so that
    comparison is fair regardless of how OCR renders the text.
    """
    # Unicode normalisation (handles é → e, etc.)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def tokenise(text: str) -> List[str]:
    """Return list of non-empty normalised tokens (min 2 chars to skip noise)."""
    return [w for w in normalise(text).split() if len(w) >= 2]


# ---------------------------------------------------------------------------
# 2. PRODUCT CONTEXT VOCABULARY
# ---------------------------------------------------------------------------

# Words that are always safe regardless of product context.
# These appear on almost every product and carry no promotional meaning.
_ALWAYS_SAFE: Set[str] = {
    # Units and specs
    "mp", "ghz", "mhz", "gb", "tb", "mb", "kb", "hz", "rpm", "kg", "mm",
    "cm", "inch", "lbs", "watt", "volt", "amp", "mah", "ip", "usb", "hdmi",
    # Generic product labels printed on almost all hardware
    "model", "serial", "no", "version", "ver", "rev",
    # Common single-character tokens that slip through
    "v", "w", "g", "x",
}


def build_product_vocabulary(
    title: str,
    description: str,
    category: str,
) -> Set[str]:
    """
    Build the complete set of words considered "product-safe".

    Includes:
    - All tokens from title, description, category
    - Always-safe hardware/spec tokens
    - Sub-tokens of compound words (e.g. "full-color" → "full", "color")
    """
    combined = f"{title} {description} {category}"
    tokens = set(tokenise(combined))

    # Also split hyphenated compounds so "full-color" allows both halves
    for token in list(tokens):
        if "-" in token:
            tokens.update(token.split("-"))

    tokens.update(_ALWAYS_SAFE)
    return tokens


def match_token_to_vocabulary(
    token: str,
    vocabulary: Set[str],
    fuzzy_threshold: int = 82,
) -> Tuple[bool, str]:
    """
    Return (is_matched, match_type) for a single OCR token.

    Match priority:
    1. Exact match
    2. Substring: token is fully contained inside a vocab word (e.g. "imou" in "imoucruiser")
    3. Fuzzy: RapidFuzz ratio >= threshold (handles OCR typos like "cruizer" → "cruiser")

    fuzzy_threshold=82 is tight enough to avoid false safe-matches while
    tolerating single-character OCR errors.
    """
    if token in vocabulary:
        return True, "exact"

    # Substring: short tokens like "4g", "ptz" often sit inside longer words
    for vocab_word in vocabulary:
        if token in vocab_word or vocab_word in token:
            return True, "substring"

    # Fuzzy for longer tokens only (fuzzy on short tokens produces noise)
    if len(token) >= 5:
        for vocab_word in vocabulary:
            if len(vocab_word) >= 4 and fuzz.ratio(token, vocab_word) >= fuzzy_threshold:
                return True, "fuzzy"

    return False, "none"


def classify_ocr_tokens(
    ocr_tokens: List[str],
    vocabulary: Set[str],
) -> Tuple[List[str], List[str]]:
    """
    Split OCR tokens into matched (product text) and unmatched (unknown).

    Returns:
        matched_tokens   – tokens explained by product context
        unmatched_tokens – tokens with no product context → candidates for promo check
    """
    matched, unmatched = [], []
    for token in ocr_tokens:
        is_match, _ = match_token_to_vocabulary(token, vocabulary)
        if is_match:
            matched.append(token)
        else:
            unmatched.append(token)
    return matched, unmatched


# ---------------------------------------------------------------------------
# 3. PROMOTIONAL PATTERN ENGINE
# ---------------------------------------------------------------------------

# Each entry: (label, compiled_regex)
# Order matters only for the reason string — all patterns are checked.

_PROMO_PATTERNS: List[Tuple[str, re.Pattern]] = [

    # ── Phone numbers ─────────────────────────────────────────────────────
    ("phone_number",
     re.compile(
         r'(\+?88)?01[3-9]\d{8}'           # Bangladesh mobile
         r'|(\+?88)?\d{2,4}[-\s]\d{6,8}'  # Landline with separator
         r'|\b\d{10,11}\b',                # Any 10-11 digit run
         re.IGNORECASE
     )),

    # ── URLs ──────────────────────────────────────────────────────────────
    ("url",
     re.compile(
         r'https?://\S+'
         r'|www\.\S+\.\w{2,}'
         r'|\b\w+\.(com|net|org|bd|io|shop|store)\b',
         re.IGNORECASE
     )),

    # ── Social media handles / pages ──────────────────────────────────────
    ("social_media",
     re.compile(
         r'@\w+'
         r'|\bfacebook\b|\bfb\.com\b|\binstagram\b|\bwhatsapp\b'
         r'|\btelegram\b|\byoutube\b|\btiktok\b|\btwitter\b'
         r'|\bmessenger\b|\bimo\b|\bviber\b',
         re.IGNORECASE
     )),

    # ── Discount / price-off patterns ─────────────────────────────────────
    ("discount_offer",
     re.compile(
         r'\d+\s*%\s*off'
         r'|\bflat\s+\d+\b'
         r'|\bsave\s+\d+'
         r'|\bbuy\s+\d+\s+get\s+\d+'
         r'|\bup\s+to\s+\d+\s*%'
         r'|\bcashback\b'
         r'|\bbonus\b',
         re.IGNORECASE
     )),

    # ── Price indicators with currency ────────────────────────────────────
    ("price_with_currency",
     re.compile(
         r'[৳₹$€£¥]\s*[\d,]+'       # Currency symbol then digits
         r'|\b\d[\d,]*\s*(tk|taka|bdt)\b',  # Taka suffix
         re.IGNORECASE
     )),

    # ── Call-to-action / sales phrases ────────────────────────────────────
    ("cta_sales",
     re.compile(
         r'\bcall\s+now\b|\border\s+now\b|\bbuy\s+now\b|\bshop\s+now\b'
         r'|\bget\s+now\b|\bclick\s+here\b|\bvisit\s+us\b|\bcontact\s+us\b'
         r'|\bmessage\s+us\b|\binbox\s+us\b|\bdm\s+us\b|\bwhatsapp\s+us\b'
         r'|\bbook\s+now\b|\border\s+today\b',
         re.IGNORECASE
     )),

    # ── Delivery / shipping promises ──────────────────────────────────────
    ("delivery_promise",
     re.compile(
         r'\bfree\s+delivery\b|\bfree\s+shipping\b'
         r'|\bcash\s+on\s+delivery\b|\bcod\b'
         r'|\bhome\s+delivery\b|\bdoor\s+delivery\b'
         r'|\bsame\s+day\s+delivery\b|\bexpress\s+delivery\b'
         r'|\bfast\s+delivery\b|\bquick\s+delivery\b',
         re.IGNORECASE
     )),

    # ── Warranty / authenticity claims ────────────────────────────────────
    ("warranty_claim",
     re.compile(
         r'\bofficial\s+warranty\b|\boriginal\s+warranty\b'
         r'|\b\d+\s+year\s+warranty\b|\b\d+\s+month\s+warranty\b'
         r'|\bgenuine\s+product\b|\b100\s*%\s+original\b'
         r'|\bauthorized\s+dealer\b|\bofficial\s+distributor\b',
         re.IGNORECASE
     )),

    # ── Generic sales buzzwords ───────────────────────────────────────────
    ("sales_buzzword",
     re.compile(
         r'\bbest\s+price\b|\bbest\s+quality\b|\bbest\s+deal\b'
         r'|\bhot\s+sale\b|\bhot\s+deal\b|\bsuper\s+sale\b'
         r'|\bgreat\s+deal\b|\bunbeatable\b|\bexclusive\s+offer\b'
         r'|\blimited\s+offer\b|\bspecial\s+offer\b|\bflash\s+sale\b'
         r'|\bmega\s+sale\b|\bclearance\b|\bblowout\b',
         re.IGNORECASE
     )),

    # ── Bangla promotional words (romanised OCR output) ───────────────────
    ("bangla_promo",
     re.compile(
         r'\bkena\s+nin\b|\bkino\b|\bdam\b|\bsasto\b|\bsheshtho\b'
         r'|\boffer\s+price\b|\bporbo\b|\bbikroy\b|\bkhoroch\b'
         r'|\bpachben\b|\bpaben\b|\bghor\s+e\s+boshe\b',
         re.IGNORECASE
     )),

    # ── Bangla script (Unicode range U+0980–U+09FF) ───────────────────────
    # Any Bangla script in an English-product image is likely a seller overlay
    ("bangla_script",
     re.compile(r'[ঀ-৿]{3,}')),

    # ── Seller shop / store branding ──────────────────────────────────────
    ("seller_branding",
     re.compile(
         r'\bofficial\s+shop\b|\bofficial\s+store\b|\bauthorized\s+shop\b'
         r'|\bour\s+shop\b|\bvisit\s+our\b|\bfollow\s+us\b'
         r'|\blike\s+our\s+page\b|\bjoin\s+our\b',
         re.IGNORECASE
     )),

    # ── Emoji sales signals (common in seller overlay stickers) ───────────
    ("emoji_sales",
     re.compile(
         r'[\U0001F3A6\U0001F525\U0001F4B0\U0001F4B8\U0001F6D2'
         r'❤★☆\U0001F44D\U0001F389\U0001F381]+'
     )),
]


def scan_for_promotional_patterns(text: str) -> List[Dict]:
    """
    Run every promotional pattern against the given text.

    Returns a list of match dicts — one per pattern that fired:
    {
        "type":    pattern label,
        "matched": the matched substring,
        "span":    (start, end) char positions
    }
    """
    hits = []
    for label, pattern in _PROMO_PATTERNS:
        for m in pattern.finditer(text):
            hits.append({
                "type":    label,
                "matched": m.group().strip(),
                "span":    m.span(),
            })
    return hits


# ---------------------------------------------------------------------------
# 4. CONFIDENCE SCORING
# ---------------------------------------------------------------------------

# How much each pattern type contributes to the 0–100 confidence score.
# High-certainty signals score more; ambiguous signals score less.
_PATTERN_WEIGHTS: Dict[str, int] = {
    "phone_number":       40,
    "url":                35,
    "social_media":       35,
    "discount_offer":     30,
    "price_with_currency": 25,
    "cta_sales":          30,
    "delivery_promise":   30,
    "warranty_claim":     20,
    "sales_buzzword":     15,
    "bangla_promo":       25,
    "bangla_script":      20,
    "seller_branding":    25,
    "emoji_sales":        10,
}

# Bonus: unmatched token ratio (fraction of OCR tokens not in product context)
# If most text is unmatched AND promotional patterns fire, confidence rises.
_UNMATCHED_RATIO_BONUS = 15


def compute_confidence(
    promo_hits: List[Dict],
    unmatched_tokens: List[str],
    total_tokens: int,
) -> int:
    """
    Aggregate confidence score 0–100.

    Logic:
    - Sum weights of unique fired pattern types (each type counted once).
    - Add unmatched-ratio bonus when >50% of tokens are unmatched.
    - Cap at 100.
    """
    if not promo_hits:
        return 0

    # Each pattern type contributes its weight once (deduplication)
    fired_types = {h["type"] for h in promo_hits}
    base_score = sum(_PATTERN_WEIGHTS.get(t, 10) for t in fired_types)

    # Unmatched ratio bonus
    unmatched_ratio = len(unmatched_tokens) / total_tokens if total_tokens else 0
    bonus = _UNMATCHED_RATIO_BONUS if unmatched_ratio > 0.50 else 0

    return min(base_score + bonus, 100)


# ---------------------------------------------------------------------------
# 5. REASON BUILDER
# ---------------------------------------------------------------------------

def build_reason(
    promo_hits: List[Dict],
    matched_tokens: List[str],
    unmatched_tokens: List[str],
    is_promotional: bool,
    confidence: int,
) -> str:
    """
    Produce a human-readable engineering reason string for the decision.
    Useful for audit trails and debugging.
    """
    if not is_promotional:
        if not unmatched_tokens:
            return (
                "All OCR text matches product title/description/category. "
                "No unmatched tokens — image text is product-context safe."
            )
        return (
            f"{len(matched_tokens)} OCR tokens match product context; "
            f"{len(unmatched_tokens)} unmatched tokens found but no "
            f"promotional patterns detected. Image is safe."
        )

    type_summary = ", ".join(sorted({h["type"] for h in promo_hits}))
    examples = "; ".join(
        f'"{h["matched"]}" ({h["type"]})'
        for h in promo_hits[:4]          # show up to 4 examples
    )
    return (
        f"Promotional content detected (confidence {confidence}/100). "
        f"Pattern types fired: [{type_summary}]. "
        f"Examples: {examples}. "
        f"Unmatched OCR tokens: {unmatched_tokens[:8]}."
    )


# ---------------------------------------------------------------------------
# 6. MAIN PUBLIC FUNCTION
# ---------------------------------------------------------------------------

def detect_promotional_text(
    ocr_extracted_data: List[Dict],   # list of {"text": str, "bbox": [...]}
    full_ocr_text: str,               # raw joined OCR text (for regex scanning)
    title: str,
    description: str,
    category: str,
    image_id: int = 0,
) -> Dict:
    """
    Full promotional text detection pipeline.

    Args:
        ocr_extracted_data : EasyOCR extracted_data list (text + bbox per box)
        full_ocr_text      : full joined OCR string (from ocr_result["full_text"])
        title              : product title
        description        : product description
        category           : product category
        image_id           : for response tagging

    Returns:
        Structured detection result dict ready for API response.
    """

    # ── Step 1: Build product vocabulary ─────────────────────────────────
    vocabulary = build_product_vocabulary(title, description, category)

    # ── Step 2: Extract and classify OCR tokens ───────────────────────────
    # Collect all text strings from OCR boxes
    ocr_texts = [box["text"] for box in ocr_extracted_data if box.get("text")]

    # Flat token list from all OCR boxes
    all_ocr_tokens = []
    for raw_text in ocr_texts:
        all_ocr_tokens.extend(tokenise(raw_text))

    # Deduplicate while preserving order
    seen: Set[str] = set()
    unique_tokens: List[str] = []
    for t in all_ocr_tokens:
        if t not in seen:
            seen.add(t)
            unique_tokens.append(t)

    matched_tokens, unmatched_tokens = classify_ocr_tokens(unique_tokens, vocabulary)

    # ── Step 3: Promotional pattern scan on unmatched text only ───────────
    # Join unmatched tokens back to a string, PLUS scan the full OCR text
    # for multi-word patterns (e.g. "free delivery" spans two tokens).
    unmatched_text = " ".join(unmatched_tokens)
    # Scan both: unmatched token stream AND full raw OCR text
    promo_hits = scan_for_promotional_patterns(unmatched_text)
    promo_hits += scan_for_promotional_patterns(full_ocr_text)

    # Deduplicate hits by (type, matched) to avoid double-counting
    seen_hits: Set[Tuple] = set()
    unique_hits: List[Dict] = []
    for h in promo_hits:
        key = (h["type"], h["matched"].lower())
        if key not in seen_hits:
            seen_hits.add(key)
            unique_hits.append(h)

    # ── Step 4: Decision and scoring ──────────────────────────────────────
    total_tokens = len(unique_tokens)
    confidence = compute_confidence(unique_hits, unmatched_tokens, total_tokens)
    is_promotional = len(unique_hits) > 0

    # ── Step 5: Reason ────────────────────────────────────────────────────
    reason = build_reason(
        unique_hits, matched_tokens, unmatched_tokens,
        is_promotional, confidence,
    )

    return {
        "image_id":              image_id,
        "ocr_texts":             ocr_texts,
        "matched_product_texts": matched_tokens,
        "unmatched_texts":       unmatched_tokens,
        "promotional_flags":     unique_hits,
        "is_promotional":        is_promotional,
        "confidence_score":      confidence,
        "reason":                reason,
    }
