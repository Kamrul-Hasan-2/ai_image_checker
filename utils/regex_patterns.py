"""
Compiled regex patterns for promotional text detection.
All patterns are pre-compiled at import time — zero runtime overhead.
"""

import re
from typing import Dict, Tuple, List

# ---------------------------------------------------------------------------
# PHONE NUMBERS
# ---------------------------------------------------------------------------
PHONE = re.compile(
    r'(\+?88)?01[3-9]\d{8}'           # BD mobile: 01XXXXXXXXX
    r'|(\+?88)?\d{2,4}[-\s]\d{6,8}'  # Landline with separator
    r'|\b\d{10,11}\b'                  # Any 10–11 digit run
    r'|[০-৯]{10,11}'                   # Bengali digit mobile
    r'|০১[০-৯]{9}',                    # Bengali BD mobile
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# URLS / DOMAINS
# ---------------------------------------------------------------------------
URL = re.compile(
    r'https?://\S+'
    r'|www\.\S+\.\w{2,}'
    r'|\b\w[\w\-]*\.(com|net|org|bd|io|shop|store|online)\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# SOCIAL MEDIA HANDLES / PLATFORM NAMES
# ---------------------------------------------------------------------------
SOCIAL = re.compile(
    r'@[\w\.]+'
    r'|\bfacebook\b|\bfb\.com\b|\bfb\.me\b|\binstagram\b|\bwhatsapp\b'
    r'|\btelegram\b|\byoutube\b|\btiktok\b|\btwitter\b|\bx\.com\b'
    r'|\bmessenger\b|\bimo\b|\bviber\b|\bsignal\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# DISCOUNT / OFFER PHRASES
# ---------------------------------------------------------------------------
DISCOUNT = re.compile(
    r'\d+\s*%\s*off'
    r'|\bflat\s+\d+\b'
    r'|\bsave\s+\d+'
    r'|\bbuy\s+\d+\s+get\s+\d+'
    r'|\bup\s+to\s+\d+\s*%'
    r'|\bcashback\b'
    r'|\bbonus\b'
    r'|\bspecial\s+discount\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# PRICE WITH CURRENCY SYMBOL
# ---------------------------------------------------------------------------
PRICE = re.compile(
    r'[৳₹$€£¥]\s*[\d,]+'
    r'|\b[\d,]+\s*(tk|taka|bdt)\b'
    r'|\bRs\.?\s*[\d,]+'
    r'|\brupees?\s*[\d,]+',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# CALL-TO-ACTION PHRASES
# ---------------------------------------------------------------------------
CTA = re.compile(
    r'\bcall\s+now\b|\border\s+now\b|\bbuy\s+now\b|\bshop\s+now\b'
    r'|\bget\s+now\b|\bclick\s+here\b|\bvisit\s+us\b|\bcontact\s+us\b'
    r'|\bmessage\s+us\b|\binbox\s+us\b|\bdm\s+us\b|\bwhatsapp\s+us\b'
    r'|\bbook\s+now\b|\border\s+today\b|\bget\s+yours\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# DELIVERY / SHIPPING PROMISES
# ---------------------------------------------------------------------------
DELIVERY = re.compile(
    r'\bfree\s+delivery\b|\bfree\s+shipping\b'
    r'|\bcash\s+on\s+delivery\b|\bcod\b'
    r'|\bhome\s+delivery\b|\bdoor\s+delivery\b'
    r'|\bsame\s+day\s+delivery\b|\bexpress\s+delivery\b'
    r'|\bfast\s+delivery\b|\bquick\s+delivery\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# WARRANTY / AUTHENTICITY CLAIMS
# ---------------------------------------------------------------------------
WARRANTY = re.compile(
    r'\bofficial\s+warranty\b|\boriginal\s+warranty\b'
    r'|\b\d+\s+year\s+warranty\b|\b\d+\s+month\s+warranty\b'
    r'|\bgenuine\s+product\b|\b100\s*%\s+original\b'
    r'|\bauthorized\s+dealer\b|\bofficial\s+distributor\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# SALES BUZZWORDS
# ---------------------------------------------------------------------------
BUZZWORD = re.compile(
    r'\bbest\s+price\b|\bbest\s+quality\b|\bbest\s+deal\b'
    r'|\bhot\s+sale\b|\bhot\s+deal\b|\bsuper\s+sale\b'
    r'|\bgreat\s+deal\b|\bunbeatable\b|\bexclusive\s+offer\b'
    r'|\blimited\s+offer\b|\bspecial\s+offer\b|\bflash\s+sale\b'
    r'|\bmega\s+sale\b|\bclearance\b|\bblowout\b|\btoday\s+only\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# BANGLA PROMOTIONAL (ROMANISED OCR OUTPUT)
# ---------------------------------------------------------------------------
BANGLA_PROMO_ROMAN = re.compile(
    r'\bkena\s+nin\b|\bkino\b|\bsasto\b|\bsheshtho\b'
    r'|\boffer\s+price\b|\bpachben\b|\bpaben\b'
    r'|\bghor\s+e\s+boshe\b|\bbikroy\b|\bkhoroch\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# BANGLA UNICODE SCRIPT (U+0980–U+09FF)
# 3+ consecutive Bangla chars = likely seller overlay in an English-product image
# ---------------------------------------------------------------------------
BANGLA_SCRIPT = re.compile(r'[ঀ-৿]{3,}')

# ---------------------------------------------------------------------------
# SELLER / SHOP BRANDING
# ---------------------------------------------------------------------------
SELLER_BRAND = re.compile(
    r'\bofficial\s+shop\b|\bofficial\s+store\b|\bauthorized\s+shop\b'
    r'|\bour\s+shop\b|\bvisit\s+our\b|\bfollow\s+us\b'
    r'|\blike\s+our\s+page\b|\bjoin\s+our\b',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# EMOJI SALES SIGNALS
# ---------------------------------------------------------------------------
EMOJI_SALES = re.compile(
    r'[\U0001F3A6\U0001F525\U0001F4B0\U0001F4B8\U0001F6D2'
    r'❤★☆\U0001F44D\U0001F389\U0001F381]+'
)

# ---------------------------------------------------------------------------
# MASTER REGISTRY  —  (label, pattern, weight)
# weight = how much this signal contributes to confidence (sum then cap at 100)
# ---------------------------------------------------------------------------
ALL_PATTERNS: List[Tuple[str, re.Pattern, int]] = [
    ("phone_number",        PHONE,            40),
    ("url",                 URL,              35),
    ("social_media",        SOCIAL,           35),
    ("discount_offer",      DISCOUNT,         30),
    ("cta_sales",           CTA,              30),
    ("delivery_promise",    DELIVERY,         30),
    ("price_with_currency", PRICE,            25),
    ("seller_branding",     SELLER_BRAND,     25),
    ("bangla_promo",        BANGLA_PROMO_ROMAN, 25),
    ("warranty_claim",      WARRANTY,         20),
    ("bangla_script",       BANGLA_SCRIPT,    20),
    ("sales_buzzword",      BUZZWORD,         15),
    ("emoji_sales",         EMOJI_SALES,      10),
]

# Quick label→weight lookup
PATTERN_WEIGHTS: Dict[str, int] = {label: w for label, _, w in ALL_PATTERNS}
