"""
Computer-vision heuristic constants and rule definitions
for native-text vs overlay-text classification.

All thresholds are documented with rationale so future engineers
can tune them without trial-and-error.
"""

from dataclasses import dataclass, field
from typing import Tuple

# ---------------------------------------------------------------------------
# IMAGE REGION ZONES (as fraction of image height/width)
# ---------------------------------------------------------------------------

# "Edge zone" — top or bottom N% of the image.
# Text centred in this band and spanning most of the image width is almost
# certainly a header/footer/banner (overlay), not a label printed on the body.
EDGE_ZONE_FRAC: float = 0.12

# "Wide text" threshold — box covers this fraction of image width.
# A label on a product body is narrow; a seller banner spans the full width.
WIDE_BOX_FRAC: float = 0.55

# Fraction of all OCR boxes that must look like "UI chrome" before the image
# is flagged as a screenshot / full-overlay promotional image.
UI_BOX_FRACTION_THRESHOLD: float = 0.35

# ---------------------------------------------------------------------------
# TEXT-BOX GEOMETRY THRESHOLDS
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class BoxGeometryThresholds:
    # A box taller than this fraction of image height is likely a large
    # promotional banner (e.g., "SALE" in huge font), not a product label.
    max_native_height_frac: float = 0.15

    # A box occupying more than this fraction of total image area is
    # almost certainly an overlay (splash banner, price badge, etc.).
    max_native_area_frac: float = 0.08

    # Aspect ratio (width / height) boundaries for a typical product label:
    # labels are wide but not as extreme as a full-width banner.
    label_min_aspect: float = 0.5    # taller-than-wide labels are fine
    label_max_aspect: float = 12.0   # wider than 12:1 = likely a banner strip

BOX_GEOMETRY = BoxGeometryThresholds()

# ---------------------------------------------------------------------------
# COLOUR / BRIGHTNESS THRESHOLDS
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ColourThresholds:
    # Maximum standard deviation of pixel values inside a text bounding box
    # for the region to be considered "monochrome industrial typography".
    # Manufacturer labels are usually black-on-white or white-on-black.
    # Promotional overlays tend to use bright, high-contrast colours.
    monochrome_std_max: float = 55.0

    # Mean saturation (HSV S channel, 0–255) threshold.
    # A region with mean saturation above this is likely a colourful promo badge.
    high_saturation_threshold: float = 80.0

    # Mean brightness (HSV V channel, 0–255) of text region.
    # Very bright regions (near-white or neon) combined with colourful text
    # are a strong overlay signal.
    bright_overlay_threshold: float = 200.0

COLOUR = ColourThresholds()

# ---------------------------------------------------------------------------
# TYPOGRAPHY / FONT SIZE THRESHOLDS
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TypographyThresholds:
    # Height of a text bounding box (in pixels) relative to image height.
    # Text taller than this fraction of image height is considered "large CTA font".
    large_font_frac: float = 0.08

    # Minimum OCR confidence to trust a detection at all.
    min_confidence: float = 0.25

TYPOGRAPHY = TypographyThresholds()

# ---------------------------------------------------------------------------
# NATIVE TEXT SIGNAL KEYWORDS
# Phrases that almost exclusively appear on product bodies, never in ads.
# Matching any of these strongly suggests the box is native product text.
# ---------------------------------------------------------------------------
NATIVE_TEXT_KEYWORDS: Tuple[str, ...] = (
    # Electrical / power labels
    "input", "output", "voltage", "current", "watt", "hz", "ac", "dc",
    "max", "min", "rated", "fuse", "amps", "volt",
    # Certification / safety
    "ul", "ce", "fcc", "rohs", "etl", "csa", "iso", "iec",
    "caution", "warning", "danger", "do not", "keep away",
    # Hardware labels
    "serial", "s/n", "sn", "model", "m/n", "part", "p/n", "rev",
    "barcode", "ean", "upc", "qr",
    # Connectivity / ports
    "usb", "hdmi", "vga", "lan", "wan", "reset", "power",
    "antenna", "mic", "audio", "video",
    # Camera / optical
    "lens", "sensor", "ir", "ptz", "zoom", "focal", "aperture",
    "resolution", "fps", "fov",
    # Battery / energy
    "battery", "capacity", "mah", "charge", "li-ion", "lithium",
    # Networking
    "ssid", "mac", "ip", "dhcp", "wifi", "wi-fi", "ethernet",
    # UPS / power device labels (prevent APC false-positives)
    "on line", "on battery", "overload", "avr", "boost", "trim",
    "replace battery", "battery charge", "load",
    # Packaging / spec print
    "net weight", "gross weight", "dimensions", "made in",
    "manufactured by", "distributed by", "country of origin",
)

# ---------------------------------------------------------------------------
# OVERLAY SIGNAL KEYWORDS
# Phrases that almost exclusively appear in promotional overlays.
# Used as a fast pre-screen before running full regex patterns.
# ---------------------------------------------------------------------------
OVERLAY_SIGNAL_KEYWORDS: Tuple[str, ...] = (
    "buy now", "order now", "call now", "shop now",
    "free delivery", "free shipping", "cash on delivery", "cod",
    "best price", "hot sale", "special offer", "limited offer",
    "discount", "% off", "cashback",
    "whatsapp", "facebook", "instagram", "telegram",
    "inbox us", "dm us", "message us",
    "www.", "http", ".com", ".bd",
    "কিনুন", "অর্ডার", "ডেলিভারি", "ছাড়",
)
