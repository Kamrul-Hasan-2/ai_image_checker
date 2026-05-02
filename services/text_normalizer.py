"""
Text normalisation utilities shared across all pipeline stages.

Single source-of-truth for how we clean OCR output before matching or
feeding it to the promotional regex engine.
"""

import re
import unicodedata
from typing import List, Set

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_SPACE_RE = re.compile(r"\s+")

# Minimum token length — tokens shorter than this are dropped as noise
MIN_TOKEN_LEN = 2


def normalise(text: str) -> str:
    """
    Lowercase → strip unicode accents → remove punctuation → collapse spaces.

    Applied identically to OCR output and product metadata so that
    comparison is symmetric regardless of how EasyOCR renders the text.
    """
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text


def tokenise(text: str) -> List[str]:
    """Return deduplicated list of normalised tokens (min MIN_TOKEN_LEN chars)."""
    seen: Set[str] = set()
    result: List[str] = []
    for w in normalise(text).split():
        if len(w) >= MIN_TOKEN_LEN and w not in seen:
            seen.add(w)
            result.append(w)
    return result


def tokenise_raw(text: str) -> List[str]:
    """Tokenise without deduplication (preserves count information)."""
    return [w for w in normalise(text).split() if len(w) >= MIN_TOKEN_LEN]
