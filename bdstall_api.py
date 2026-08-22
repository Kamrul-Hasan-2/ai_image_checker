"""
Client for BDStall's `product_details` API.

Both id-only moderation endpoints (`/image_checker` and `/weight_checker`) take
just `{"id": <listing_id>}` and pull the listing's own data from here instead of
having it pushed to them in the request body:

    GET https://www.bdstall.com/api/item_ai/product_details/?key=123_456&id=141462

Responses are cached for a short TTL because BDStall calls both endpoints for
the same listing back to back — without it every listing save would fetch the
same payload twice.
"""

import os
import threading
import time
from typing import Any, Dict, List, Optional

import requests

PRODUCT_DETAILS_URL = os.environ.get(
    "BDSTALL_PRODUCT_DETAILS_URL",
    "https://www.bdstall.com/api/item_ai/product_details/",
)
API_KEY = os.environ.get("BDSTALL_API_KEY", "123_456")

_FETCH_TIMEOUT = int(os.environ.get("BDSTALL_PRODUCT_DETAILS_TIMEOUT", 15))
_CACHE_TTL = int(os.environ.get("BDSTALL_PRODUCT_DETAILS_TTL_SECONDS", 60))
_CACHE_MAX_ENTRIES = 256

# listing_avator.ai_verification_avator: 0 = never set, 1 = uploaded/pending,
# 2 = already checked by us. Both 0 and 1 mean "hasn't been through the checker
# yet" — only 2 is done, so only 2 gets skipped.
PENDING_AI_VERIFIED = (0, 1)

_lock = threading.Lock()
_cache: Dict[int, Any] = {}


class ProductDetailsError(RuntimeError):
    """product_details couldn't be fetched, or came back with success=false."""

    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def _cache_get(listing_id: int) -> Optional[Dict[str, Any]]:
    with _lock:
        entry = _cache.get(listing_id)
    if not entry:
        return None
    fetched_at, data = entry
    if (time.time() - fetched_at) > _CACHE_TTL:
        return None
    return data


def _cache_put(listing_id: int, data: Dict[str, Any]) -> None:
    with _lock:
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            # Cheap eviction — drop the oldest half rather than tracking an LRU.
            for stale_id in sorted(_cache, key=lambda k: _cache[k][0])[: _CACHE_MAX_ENTRIES // 2]:
                _cache.pop(stale_id, None)
        _cache[listing_id] = (time.time(), data)


def fetch_product_details(listing_id: int, use_cache: bool = True) -> Dict[str, Any]:
    """
    Fetch one listing's `data` object from product_details.

    Raises ProductDetailsError (with an HTTP-ish `status_code`) when the listing
    doesn't exist or the API is unreachable — callers should surface that rather
    than silently reporting a clean listing.
    """
    if use_cache:
        cached = _cache_get(listing_id)
        if cached is not None:
            return cached

    try:
        resp = requests.get(
            PRODUCT_DETAILS_URL,
            params={"key": API_KEY, "id": listing_id},
            timeout=_FETCH_TIMEOUT,
        )
    except requests.RequestException as e:
        raise ProductDetailsError(f"product_details request failed for id={listing_id}: {e}", 502)

    # An unknown listing comes back either as HTTP 404 or as HTTP 200 with
    # success=false, depending on the id — both mean "no such listing".
    if resp.status_code == 404:
        raise ProductDetailsError(f"product_details has no listing id={listing_id} (HTTP 404)", 404)

    if resp.status_code >= 400:
        raise ProductDetailsError(
            f"product_details returned HTTP {resp.status_code} for id={listing_id}", 502
        )

    try:
        payload = resp.json()
    except ValueError as e:
        raise ProductDetailsError(f"product_details returned invalid JSON for id={listing_id}: {e}", 502)

    if not isinstance(payload, dict) or not payload.get("success"):
        message = (payload or {}).get("message", "unknown error") if isinstance(payload, dict) else "unknown error"
        raise ProductDetailsError(f"product_details rejected id={listing_id}: {message}", 404)

    data = payload.get("data") or {}
    if not isinstance(data, dict):
        raise ProductDetailsError(f"product_details returned no data object for id={listing_id}", 502)

    _cache_put(listing_id, data)
    return data


def _as_int(value: Any) -> Optional[int]:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def listing_images_pending_check(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    The listing's images that still need checking (ai_verified 0 or 1), as
    {"id", "position_id", "image"} dicts ready for the image pipeline.

    Images already at ai_verified=2, and entries with no id or no URL, are
    dropped.
    """
    images = data.get("images") or []
    pending: List[Dict[str, Any]] = []

    for img in images:
        if not isinstance(img, dict):
            continue

        ai_verified = _as_int(img.get("ai_verified"))
        if ai_verified is not None and ai_verified not in PENDING_AI_VERIFIED:
            continue

        image_id = _as_int(img.get("id"))
        url = img.get("url") or img.get("image")
        if image_id is None or not url:
            continue

        pending.append({
            "id": image_id,
            "position_id": _as_int(img.get("position_id")) or 0,
            "image": url,
        })

    return pending


def listing_shipping_weight_kg(data: Dict[str, Any]) -> Optional[float]:
    """
    The listing's declared shipping weight in kg, or None when product_details
    doesn't carry one.

    Only reads real numeric fields. The `specification` list sometimes holds a
    free-text "Package Weight: Approximately 0.70 kg" entry — that is deliberately
    NOT parsed: it isn't guaranteed to be present, numeric, or in kg, so guessing
    from it would flag listings on a misread string.
    """
    for key in ("shipping_weight_kg", "shipping_weight", "weight_kg"):
        value = data.get(key)
        if value is None or isinstance(value, bool):
            continue
        try:
            weight = float(value)
        except (TypeError, ValueError):
            continue
        if weight > 0:
            return weight
    return None
