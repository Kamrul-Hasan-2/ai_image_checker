"""
Stage 1 — OCR Text Extraction.

Runs EasyOCR on a PIL Image and returns a structured result containing:
- per-box text, confidence, and normalised bounding-box polygon
- joined full-text string
- image dimensions (needed by downstream layout analysis)

This module is intentionally thin — it does NOT do any promo or watermark
detection.  That belongs in later stages.
"""

from __future__ import annotations

import numpy as np
from PIL import Image
from typing import Any, Dict, List, Optional

# EasyOCR is a heavy import — only initialise once per process
_reader: Optional[Any] = None


def _get_reader(languages: List[str] = None):
    global _reader
    if _reader is None:
        import easyocr
        langs = languages or ["en"]
        _reader = easyocr.Reader(
            langs,
            gpu=True,
            model_storage_directory="/root/.cache/easyocr",
            download_enabled=True,
        )
    return _reader


def extract_text(
    image: Image.Image,
    languages: List[str] = None,
) -> Dict[str, Any]:
    """
    Run EasyOCR on a PIL RGB image.

    Returns
    -------
    {
        "full_text"     : str          — all detected text joined by space
        "extracted_data": list[dict]   — one dict per box:
            {
                "text"      : str
                "confidence": float (0–1)
                "bbox"      : [[x,y],[x,y],[x,y],[x,y]]  (4-point polygon)
            }
        "text_count"    : int          — number of text boxes
        "img_width"     : int
        "img_height"    : int
    }
    """
    reader = _get_reader(languages)

    img_array = np.array(image)
    img_height, img_width = img_array.shape[:2]

    # EasyOCR returns: list of (bbox, text, confidence)
    raw_results = reader.readtext(img_array, paragraph=False)

    extracted_data: List[Dict] = []
    all_text: List[str] = []

    for (bbox, text, confidence) in raw_results:
        if confidence < 0.20:          # skip near-zero confidence noise
            continue
        extracted_data.append({
            "text":       text,
            "confidence": float(confidence),
            "bbox":       bbox,         # already 4-point list from EasyOCR
        })
        all_text.append(text)

    return {
        "full_text":      " ".join(all_text),
        "extracted_data": extracted_data,
        "text_count":     len(extracted_data),
        "img_width":      img_width,
        "img_height":     img_height,
    }
