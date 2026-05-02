"""
Stage 2 — Product Semantic Context Matcher.

Classifies each OCR token as either:
  - matched   : semantically belongs to the product (safe)
  - unmatched : no product context found → candidate for Stage 3

Three-tier matching (fastest to slowest):
  1. Exact / substring match against product vocabulary
  2. RapidFuzz token similarity (handles OCR typos)
  3. Sentence-transformer cosine similarity for semantically related terms

Tier 3 is only invoked for tokens that pass through tiers 1 and 2, because
sentence-transformer inference is ~50ms per token on CPU.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np
from rapidfuzz import fuzz

from services.text_normalizer import normalise, tokenise

# ---------------------------------------------------------------------------
# ALWAYS-SAFE VOCABULARY
# Tokens that appear on almost every product but carry no promotional meaning.
# ---------------------------------------------------------------------------
_ALWAYS_SAFE: Set[str] = {
    # Units / measurements
    "mp", "ghz", "mhz", "gb", "tb", "mb", "kb", "hz", "rpm", "kg", "mm",
    "cm", "inch", "lbs", "watt", "volt", "amp", "mah", "ip", "usb", "hdmi",
    # Hardware identifiers
    "model", "serial", "no", "version", "ver", "rev", "sn", "pn",
    # Single-char tokens that slip through normalisation
    "v", "w", "g", "x", "a",
    # Common product adjectives that are NOT promo terms
    "black", "white", "silver", "blue", "red", "gray", "grey",
    # Numbers-as-strings (model, batch, batch codes)
    "mk", "gen", "hd", "fhd", "uhd", "4k", "2k",
}

# ---------------------------------------------------------------------------
# FUZZY THRESHOLDS
# ---------------------------------------------------------------------------
FUZZY_THRESHOLD: int = 82      # RapidFuzz ratio, 0–100
MIN_FUZZY_LEN:   int = 4       # only run fuzzy on tokens >= this length

# ---------------------------------------------------------------------------
# SEMANTIC THRESHOLD  (cosine similarity, 0–1)
# ---------------------------------------------------------------------------
SEMANTIC_THRESHOLD: float = 0.72

# ---------------------------------------------------------------------------
# LAZY SENTENCE-TRANSFORMER LOADER
# One instance shared across all requests; loaded on first use.
# ---------------------------------------------------------------------------
_st_lock  = threading.Lock()
_st_model = None    # SentenceTransformer instance
_ST_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"


def _get_st_model():
    """Load sentence-transformer model lazily (thread-safe)."""
    global _st_model
    if _st_model is None:
        with _st_lock:
            if _st_model is None:
                try:
                    from sentence_transformers import SentenceTransformer
                    _st_model = SentenceTransformer(_ST_MODEL_NAME)
                except Exception:
                    _st_model = None   # disable tier 3 if import fails
    return _st_model


# ---------------------------------------------------------------------------
# VOCABULARY BUILDER
# ---------------------------------------------------------------------------

def build_product_vocabulary(
    title: str,
    description: str,
    category: str,
) -> Set[str]:
    """
    Build the complete set of tokens considered "product-safe".

    Includes:
    - All tokens from title + description + category
    - Hyphen-split sub-tokens ("full-color" → "full", "color")
    - Always-safe hardware/spec tokens
    """
    combined = f"{title} {description} {category}"
    tokens   = set(tokenise(combined))

    # Expand hyphenated compounds
    for tok in list(tokens):
        if "-" in tok:
            tokens.update(tok.split("-"))

    tokens.update(_ALWAYS_SAFE)
    return tokens


# ---------------------------------------------------------------------------
# THREE-TIER MATCHING
# ---------------------------------------------------------------------------

def _exact_or_substring(token: str, vocabulary: Set[str]) -> bool:
    if token in vocabulary:
        return True
    for vw in vocabulary:
        if token in vw or vw in token:
            return True
    return False


def _fuzzy_match(token: str, vocabulary: Set[str]) -> bool:
    if len(token) < MIN_FUZZY_LEN:
        return False
    for vw in vocabulary:
        if len(vw) >= 4 and fuzz.ratio(token, vw) >= FUZZY_THRESHOLD:
            return True
    return False


def _semantic_match(
    token: str,
    vocab_embedding: Optional[np.ndarray],
    vocabulary_words: List[str],
) -> bool:
    """
    Use sentence-transformer to check if `token` is semantically close
    to any word in the product vocabulary.

    vocab_embedding : precomputed embeddings of vocabulary words (shape: N×D)
    vocabulary_words: the words corresponding to each row in vocab_embedding
    """
    model = _get_st_model()
    if model is None or vocab_embedding is None or len(vocabulary_words) == 0:
        return False

    try:
        tok_emb = model.encode([token], normalize_embeddings=True)
        # cosine similarity: dot product of L2-normalised vectors
        sims = (vocab_embedding @ tok_emb.T).flatten()
        return float(sims.max()) >= SEMANTIC_THRESHOLD
    except Exception:
        return False


def match_token(
    token: str,
    vocabulary: Set[str],
    vocab_embedding: Optional[np.ndarray] = None,
    vocabulary_words: Optional[List[str]] = None,
) -> Tuple[bool, str]:
    """
    Return (is_matched, match_tier) for a single normalised OCR token.
    Tier names: "exact" | "fuzzy" | "semantic" | "none"
    """
    if _exact_or_substring(token, vocabulary):
        return True, "exact"
    if _fuzzy_match(token, vocabulary):
        return True, "fuzzy"
    if vocab_embedding is not None:
        if _semantic_match(token, vocab_embedding, vocabulary_words or []):
            return True, "semantic"
    return False, "none"


# ---------------------------------------------------------------------------
# VOCABULARY EMBEDDING CACHE
# ---------------------------------------------------------------------------

def precompute_vocab_embeddings(
    vocabulary: Set[str],
) -> Tuple[Optional[np.ndarray], List[str]]:
    """
    Pre-encode all vocabulary words with the sentence-transformer so we
    do one bulk inference instead of N separate calls per image.

    Returns (embedding_matrix, word_list) or (None, []) if model unavailable.
    """
    model = _get_st_model()
    if model is None:
        return None, []

    words = sorted(vocabulary)
    try:
        embs = model.encode(words, normalize_embeddings=True, batch_size=64)
        return embs, words
    except Exception:
        return None, []


# ---------------------------------------------------------------------------
# STAGE 2 MAIN FUNCTION
# ---------------------------------------------------------------------------

def classify_tokens(
    ocr_texts: List[str],
    title: str,
    description: str,
    category: str,
    use_semantic: bool = True,
) -> Dict[str, Any]:
    """
    Classify all OCR text tokens against the product vocabulary.

    Args:
        ocr_texts    : raw text strings extracted from each OCR box
        title        : product title
        description  : product description
        category     : product category
        use_semantic : whether to run sentence-transformer tier

    Returns
    -------
    {
        "vocabulary"          : set[str]   — the product vocabulary
        "matched_tokens"      : list[str]
        "unmatched_tokens"    : list[str]
        "match_details"       : list[dict] — per-token match info
        "unmatched_ratio"     : float      — unmatched / total
        "total_unique_tokens" : int
    }
    """
    vocabulary = build_product_vocabulary(title, description, category)

    # Precompute embeddings once for this request
    vocab_emb, vocab_words = (
        precompute_vocab_embeddings(vocabulary) if use_semantic else (None, [])
    )

    # Gather unique tokens from all OCR boxes
    all_tokens: List[str] = []
    seen: Set[str] = set()
    for raw in ocr_texts:
        for tok in tokenise(raw):
            if tok not in seen:
                seen.add(tok)
                all_tokens.append(tok)

    matched:   List[str] = []
    unmatched: List[str] = []
    details:   List[Dict] = []

    for tok in all_tokens:
        is_match, tier = match_token(tok, vocabulary, vocab_emb, vocab_words)
        if is_match:
            matched.append(tok)
        else:
            unmatched.append(tok)
        details.append({"token": tok, "matched": is_match, "tier": tier})

    total = len(all_tokens)
    unmatched_ratio = len(unmatched) / total if total > 0 else 0.0

    return {
        "vocabulary":           vocabulary,
        "matched_tokens":       matched,
        "unmatched_tokens":     unmatched,
        "match_details":        details,
        "unmatched_ratio":      round(unmatched_ratio, 3),
        "total_unique_tokens":  total,
    }
