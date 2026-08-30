"""
Gemini-backed market-price lookup for the /price_checker endpoint.

Answers "what does this product actually sell for in Bangladesh right now?" so a
listing's own price can be held up against the rest of the market. Unlike the
weight lookup in gemini_service.py — where the answer is a fixed published spec
Gemini already knows — a price is a moving number that only today's shop pages
can supply, so this asks Gemini to run a **Google Search** and answer from what
it finds.

That grounding forces two differences from gemini_service.py, both deliberate:

  * **No structured output.** The Gemini API rejects `responseMimeType:
    application/json` whenever a tool is attached ("Tool use with a response
    mime type: 'application/json' is unsupported", HTTP 400), so the model is
    asked for bare JSON in the prompt and the reply is parsed defensively —
    markdown fences stripped, first JSON object extracted.
  * **A short cache TTL.** Weights are cached for a day because the same listing
    must produce the same number twice. Prices genuinely move, so they are held
    only long enough to spare the repeated lookups of one moderation session.

`offers` are what the model read off the shop pages; `sources` are the URLs
Google actually served it, taken from the response's grounding metadata rather
than from the model's own text — a model-written URL can be plausible and wrong,
and these are shown to staff as evidence.

Every failure path returns `_lookup_ok: False`, which callers must treat as
"no market reading available" — never as "this listing is priced correctly" —
and is deliberately not cached.
"""

import json
import os
import re
import threading
import time
from typing import Dict, List, Optional, Tuple

import requests

from gemini_service import GEMINI_API_KEY, GEMINI_API_BASE

# Grounded search needs a model that can call the search tool. The weight
# lookup's default (gemini-2.5-flash-lite) cannot, so this is configured
# separately instead of sharing GEMINI_MODEL.
GEMINI_PRICE_MODEL = os.environ.get("GEMINI_PRICE_MODEL", "gemini-2.5-flash").strip()

# A grounded search runs several queries and reads pages before answering, so it
# is far slower than the weight lookup's single knowledge recall.
_TIMEOUT = int(os.environ.get("GEMINI_PRICE_TIMEOUT_SECONDS", 90))

# Long enough to cover a moderator working through a queue without re-billing
# the same search; short enough that a price move shows up the same day.
_CACHE_TTL = int(os.environ.get("GEMINI_PRICE_CACHE_TTL_SECONDS", 6 * 3600))
_CACHE_MAX_ENTRIES = 1024

_cache_lock = threading.Lock()
_cache: Dict[Tuple[str, str], Tuple[float, Dict]] = {}

# Nothing on the site is priced below a taka or above a crore; a number outside
# that is a currency slip (USD read as BDT, or a phone number scraped as a
# price), not a real market price.
_MIN_PRICE_BDT = 1.0
_MAX_PRICE_BDT = 10_000_000.0

_UNKNOWN = {
    "found": False,
    "low_bdt": None,
    "high_bdt": None,
    "typical_bdt": None,
    "offers": [],
    "sources": [],
    "search_queries": [],
    "confidence": "low",
    "_lookup_ok": False,
}

_PROMPT = """You are researching the current market price of a product for a Bangladeshi
marketplace, so a seller's asking price can be compared against the rest of the market.

Product: {title}
{context}
Use Google Search to find what this exact product currently sells for **in Bangladesh**, in BDT.
Check Bangladeshi retailers and marketplaces — Startech, Techland, Ryans Computers, Daraz
Bangladesh, Pickaboo, Skyland, Global Brand, Binary Logic, UCC, and similar shops.

Reply with ONLY this JSON object and nothing else — no markdown fence, no commentary:

{{"found": true,
  "low_bdt": <lowest currently advertised price>,
  "high_bdt": <highest currently advertised price>,
  "typical_bdt": <the price most shops are charging>,
  "offers": [{{"seller": "<shop name>", "price_bdt": <number>, "url": "<product page url>"}}],
  "confidence": "high"}}

Rules:
- Prices must be in BDT for the Bangladeshi market. If a source is in USD or INR, convert it
  and say so in the seller name; never report a foreign price as if it were a local one.
- List the distinct shops you actually found a price on, up to 5, in `offers`.
- Match the SAME product. A different model number, capacity, or generation is a different
  product — do not substitute it. Accessories and spare parts are not the product either.
- If the product is generic/no-name, or you cannot find it on sale in Bangladesh, return
  {{"found": false, "confidence": "low"}} with no prices. Reporting a guessed price is worse
  than reporting none: a real seller gets accused over an invented number.
- Prices are for the {condition} condition of this item.
- Use confidence "high" only when several Bangladeshi shops agree on a price."""


def _endpoint() -> str:
    return f"{GEMINI_API_BASE}/models/{GEMINI_PRICE_MODEL}:generateContent"


def _cache_key(title: str, condition: Optional[str]) -> Tuple[str, str]:
    return (" ".join(title.lower().split()), (condition or "").lower().strip())


def _cache_get(key: Tuple[str, str]) -> Optional[Dict]:
    with _cache_lock:
        entry = _cache.get(key)
    if not entry:
        return None
    stored_at, value = entry
    if (time.time() - stored_at) > _CACHE_TTL:
        return None
    return json.loads(json.dumps(value))


def _cache_put(key: Tuple[str, str], value: Dict) -> None:
    with _cache_lock:
        if len(_cache) >= _CACHE_MAX_ENTRIES:
            oldest = sorted(_cache, key=lambda k: _cache[k][0])[: _CACHE_MAX_ENTRIES // 2]
            for stale in oldest:
                _cache.pop(stale, None)
        _cache[key] = (time.time(), json.loads(json.dumps(value)))


def _coerce_price(value) -> Optional[float]:
    """A usable BDT price, or None. Rejects bools, junk and out-of-range values."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, str):
        # "৳3,500", "3500 BDT", "Tk 3500." — keep the digits and one decimal point.
        cleaned = re.sub(r"[^\d.]", "", value)
        if cleaned.count(".") > 1:
            cleaned = cleaned.split(".")[0]
        value = cleaned
    try:
        price = float(value)
    except (TypeError, ValueError):
        return None
    if not (_MIN_PRICE_BDT <= price <= _MAX_PRICE_BDT):
        return None
    return round(price, 2)


def _extract_json(text: str) -> Optional[Dict]:
    """
    Parse the model's reply into a dict.

    Grounded answers can't be schema-constrained, so the reply may arrive fenced
    or with a sentence wrapped around it. Try the whole string first, then the
    outermost {...} span.
    """
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        parsed = json.loads(text[start:end + 1])
        return parsed if isinstance(parsed, dict) else None
    except ValueError:
        return None


def _clean_offers(raw) -> List[Dict]:
    """The model's per-shop findings, keeping only entries with a usable price."""
    if not isinstance(raw, list):
        return []
    offers = []
    for item in raw[:5]:
        if not isinstance(item, dict):
            continue
        price = _coerce_price(item.get("price_bdt") or item.get("price"))
        if price is None:
            continue
        url = item.get("url")
        offers.append({
            "seller": str(item.get("seller") or "unknown")[:120],
            "price_bdt": price,
            "url": url if isinstance(url, str) and url.startswith("http") else None,
        })
    offers.sort(key=lambda o: o["price_bdt"])
    return offers


def _grounding_sources(candidate: Dict) -> Tuple[List[Dict], List[str]]:
    """
    The pages Google actually served, and the queries it ran, from the response's
    grounding metadata. Preferred over URLs in the model's own text, which can be
    plausible-looking and fabricated.
    """
    metadata = candidate.get("groundingMetadata") or {}
    sources, seen = [], set()
    for chunk in (metadata.get("groundingChunks") or []):
        web = (chunk or {}).get("web") or {}
        uri = web.get("uri")
        if not uri or uri in seen:
            continue
        seen.add(uri)
        sources.append({"title": web.get("title") or "", "url": uri})
        if len(sources) >= 10:
            break
    queries = [q for q in (metadata.get("webSearchQueries") or []) if isinstance(q, str)][:8]
    return sources, queries


def estimate_market_price_bdt(
    title: str,
    category: Optional[str] = None,
    brand: Optional[str] = None,
    condition: Optional[str] = None,
    description: Optional[str] = None,
) -> Dict:
    """
    Ask Gemini to search the web for what `title` currently sells for in Bangladesh.

    Returns {"found": bool, "low_bdt": float|None, "high_bdt": float|None,
             "typical_bdt": float|None, "offers": [...], "sources": [...],
             "search_queries": [...], "confidence": str, "_lookup_ok": bool}.

    `_lookup_ok=False` means the call or the parse failed — treat it as "no market
    reading", not as a clean bill of health. `found=False` means the search ran but
    turned up no comparable Bangladeshi listing.
    """
    if not GEMINI_API_KEY or not title:
        return json.loads(json.dumps(_UNKNOWN))

    key = _cache_key(title, condition)
    cached = _cache_get(key)
    if cached is not None:
        return cached

    context = ""
    if brand:
        context += f"Brand: {brand}\n"
    if category:
        context += f"Category: {category}\n"
    if description:
        context += f"Description: {description[:500]}\n"

    payload = {
        "contents": [{
            "parts": [{
                "text": _PROMPT.format(
                    title=title,
                    context=context,
                    condition=(condition or "New").lower(),
                )
            }]
        }],
        "tools": [{"google_search": {}}],
        "generationConfig": {
            "temperature": 0,
            # Thinking tokens are drawn from the SAME budget as the answer, and a
            # grounded search spends thousands of them reading pages — enough to
            # leave nothing for the JSON, which then arrives truncated and
            # unparseable. Disabling thinking fixed exactly that (and halved the
            # latency): the model still searches, it just stops narrating to
            # itself first. Reading prices off shop pages needs no deliberation.
            "thinkingConfig": {"thinkingBudget": 0},
            "maxOutputTokens": 8192,
        },
    }

    try:
        resp = requests.post(
            _endpoint(),
            headers={
                "x-goog-api-key": GEMINI_API_KEY,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=_TIMEOUT,
        )
    except requests.RequestException as e:
        print(f"⚠️  Gemini price-lookup request failed: {e}")
        return json.loads(json.dumps(_UNKNOWN))

    if resp.status_code != 200:
        print(f"⚠️  Gemini price-lookup HTTP {resp.status_code}: {resp.text[:300]}")
        return json.loads(json.dumps(_UNKNOWN))

    try:
        body = resp.json()
        candidate = body["candidates"][0]
        parts = candidate.get("content", {}).get("parts", [])
        raw = "".join(p.get("text", "") for p in parts)
    except (ValueError, KeyError, IndexError, TypeError) as e:
        print(f"⚠️  Gemini price-lookup unreadable response: {e}")
        return json.loads(json.dumps(_UNKNOWN))

    parsed = _extract_json(raw)
    if parsed is None:
        # Most often MAX_TOKENS: the model spent the budget searching and never
        # emitted the JSON. Report it as a failed lookup, not as "no price found".
        print(f"⚠️  Gemini price-lookup unparseable JSON "
              f"(finishReason={candidate.get('finishReason')}): {raw[:200]}")
        return json.loads(json.dumps(_UNKNOWN))

    sources, queries = _grounding_sources(candidate)
    offers = _clean_offers(parsed.get("offers"))

    if not parsed.get("found"):
        result = dict(_UNKNOWN, sources=sources, search_queries=queries,
                      confidence=str(parsed.get("confidence") or "low"),
                      _lookup_ok=True)
        _cache_put(key, result)
        return result

    low     = _coerce_price(parsed.get("low_bdt"))
    high    = _coerce_price(parsed.get("high_bdt"))
    typical = _coerce_price(parsed.get("typical_bdt"))

    # The offers are individual shop prices actually read off pages, so they are
    # firmer than the model's own summary numbers — let them fill any gap and
    # widen a range that contradicts them.
    if offers:
        offer_prices = [o["price_bdt"] for o in offers]
        low  = min([p for p in (low, min(offer_prices)) if p is not None])
        high = max([p for p in (high, max(offer_prices)) if p is not None])

    if low is not None and high is not None and low > high:
        low, high = high, low
    # The model's own `typical_bdt` is a summary it wrote; the offers are prices
    # it actually read off pages. With enough of them their median is the better
    # centre, and — unlike a midpoint of low/high — one outlier cannot drag it.
    # A single counterfeit listing at a fifth of the real price was otherwise
    # enough to stretch the range until every price looked normal.
    if len(offers) >= 3:
        prices = sorted(o["price_bdt"] for o in offers)
        middle = len(prices) // 2
        typical = (prices[middle] if len(prices) % 2
                   else round((prices[middle - 1] + prices[middle]) / 2, 2))
    elif typical is None and low is not None and high is not None:
        typical = round((low + high) / 2, 2)
    # A typical price outside its own range is a model slip; pull it back in
    # rather than reporting a figure that contradicts the range beside it.
    if typical is not None and low is not None and high is not None:
        typical = min(max(typical, low), high)

    found = any(v is not None for v in (low, high, typical))

    result = {
        "found": found,
        "low_bdt": low,
        "high_bdt": high,
        "typical_bdt": typical,
        "offers": offers,
        "sources": sources,
        "search_queries": queries,
        "confidence": str(parsed.get("confidence") or "low"),
        "_lookup_ok": True,
    }
    # Only successful lookups are cached — a transport failure must stay retryable.
    _cache_put(key, result)
    return result
