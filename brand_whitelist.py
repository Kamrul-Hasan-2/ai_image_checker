"""
Live brand-name whitelist fetched from BDStall's brand_list API.

Prevents legitimate brand names (e.g. "Walton", "Samsung") from being
misclassified as a seller/watermark overlay just because the OCR box text
happens to also contain a generic business word ("shop", "plaza", "group", ...)
elsewhere in the same image. Only used to protect OCR boxes whose text is
*exactly* a known brand name — it never suppresses detection for boxes that
contain a brand name plus other promotional content (e.g. "Samsung Mobile
Shop 01712345678" still gets flagged normally).

Fetched once at startup and refreshed on a TTL so we don't hit the API on
every single image check. A fetch failure keeps using the last known list
(or an empty list, before the first successful fetch) — it never blocks or
fails image processing.
"""

import os
import re
import threading
import time
from typing import Set

import requests

BRAND_LIST_URL = os.environ.get(
    "BDSTALL_BRAND_LIST_URL",
    "https://www.bdstall.com/api/item_ai/brand_list/?key=123_456",
)
_REFRESH_SECONDS = int(os.environ.get("BDSTALL_BRAND_LIST_TTL_SECONDS", 6 * 3600))
_FETCH_TIMEOUT = 5

_lock = threading.Lock()
_brand_names: Set[str] = set()
_last_fetch_attempt = 0.0


def _normalise(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _fetch() -> Set[str]:
    resp = requests.get(BRAND_LIST_URL, timeout=_FETCH_TIMEOUT)
    resp.raise_for_status()
    data = resp.json()

    names: Set[str] = set()
    for item in data:
        for key in ("brand_name", "bn_brand_name"):
            value = item.get(key)
            if value:
                names.add(_normalise(value))
    return names


def refresh(force: bool = False) -> None:
    """Refresh the cached brand list if stale (or always, if force=True)."""
    global _brand_names, _last_fetch_attempt

    now = time.time()
    with _lock:
        if not force and (now - _last_fetch_attempt) < _REFRESH_SECONDS:
            return
        _last_fetch_attempt = now

    try:
        fresh_names = _fetch()
    except Exception as e:
        print(f"⚠️  Brand whitelist fetch failed, keeping {len(_brand_names)} cached brand(s): {e}")
        return

    with _lock:
        _brand_names = fresh_names
    print(f"✅ Brand whitelist loaded: {len(fresh_names)} brand name(s)")


def is_known_brand(text: str) -> bool:
    """True if `text` (a single OCR box's text) is *exactly* a known brand name."""
    if not text:
        return False
    with _lock:
        names = _brand_names
    return _normalise(text) in names
