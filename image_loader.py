"""
Shared, hardened image loader for the AI Image Checker.

Both entrypoints (main.py FastAPI and modal_handler.py) use load_image_safe()
so the security/robustness guards live in ONE place and cannot drift:

  • data:image URLs without a comma no longer raise IndexError (#5)
  • SSRF: http(s) URLs pointing at localhost / private / link-local / cloud
    metadata IPs are rejected before any network request (#6)
  • DoS: downloads are streamed with a hard size cap so a multi-GB response
    cannot exhaust memory (#9)
"""

import base64
import io
import ipaddress
import socket
from urllib.parse import urlparse

import requests
from PIL import Image

# Hard cap on downloaded image bytes (product images are small; 50 MB is generous).
MAX_IMAGE_BYTES = 50 * 1024 * 1024
DOWNLOAD_TIMEOUT = 10
DOWNLOAD_CHUNK = 64 * 1024

_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


def _is_blocked_ip(ip_str: str) -> bool:
    """True if the IP is loopback, private, link-local, reserved, or unspecified."""
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        # Not a parseable IP — let it through (it'll be a hostname resolved below).
        return False
    return (
        ip.is_loopback
        or ip.is_private
        or ip.is_link_local      # 169.254.0.0/16 — includes cloud metadata 169.254.169.254
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
    )


def _assert_url_is_public(url: str) -> None:
    """
    Reject URLs that resolve to non-public addresses (SSRF guard).

    Resolves the hostname and checks EVERY resolved address, so a hostname that
    points at 127.0.0.1 (or any internal IP) is blocked too.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError(f"Unsupported URL scheme: {parsed.scheme!r}")
    host = parsed.hostname
    if not host:
        raise ValueError("URL has no host")

    # Direct-IP host (e.g. http://169.254.169.254) — check it straight away.
    if _is_blocked_ip(host):
        raise ValueError(f"Refusing to fetch internal/private address: {host}")

    # Hostname — resolve and check all returned addresses.
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80))
    except socket.gaierror as e:
        raise ValueError(f"Could not resolve host {host!r}: {e}")

    for info in infos:
        resolved_ip = info[4][0]
        if _is_blocked_ip(resolved_ip):
            raise ValueError(
                f"Refusing to fetch {host!r}: resolves to internal/private IP {resolved_ip}"
            )


def _download_with_limit(url: str) -> bytes:
    """Stream a URL into memory, aborting if it exceeds MAX_IMAGE_BYTES."""
    _assert_url_is_public(url)
    with requests.get(
        url, headers=_DEFAULT_HEADERS, timeout=DOWNLOAD_TIMEOUT, stream=True
    ) as response:
        response.raise_for_status()

        # Fast reject via Content-Length when the server provides it.
        clen = response.headers.get("Content-Length")
        if clen is not None:
            try:
                if int(clen) > MAX_IMAGE_BYTES:
                    raise ValueError(
                        f"Image too large: {int(clen)} bytes > {MAX_IMAGE_BYTES} limit"
                    )
            except ValueError as e:
                if "too large" in str(e):
                    raise

        # Stream and enforce the cap even when Content-Length is absent or lies.
        buf = io.BytesIO()
        total = 0
        for chunk in response.iter_content(chunk_size=DOWNLOAD_CHUNK):
            if not chunk:
                continue
            total += len(chunk)
            if total > MAX_IMAGE_BYTES:
                raise ValueError(
                    f"Image too large: exceeded {MAX_IMAGE_BYTES} byte limit while downloading"
                )
            buf.write(chunk)
        return buf.getvalue()


def _decode_data_url(image_input: str) -> bytes:
    """Decode a data:image URL, tolerating a missing comma separator."""
    if "," in image_input:
        base64_str = image_input.split(",", 1)[1]
    else:
        # Malformed data URL (no comma). Treat everything after the scheme as the
        # payload rather than crashing with IndexError.
        base64_str = image_input[len("data:image"):].lstrip(";")
    return base64.b64decode(base64_str)


def load_image_safe(image_input: str) -> Image.Image:
    """
    Load an image from an http(s) URL, a data:image URL, or a raw base64 string.

    Raises ValueError on any failure (network, decode, oversize, blocked URL),
    matching the previous load_image() contract so existing callers/handlers work.
    """
    try:
        if image_input.startswith("http://") or image_input.startswith("https://"):
            data = _download_with_limit(image_input)
            image = Image.open(io.BytesIO(data))
        elif image_input.startswith("data:image"):
            image = Image.open(io.BytesIO(_decode_data_url(image_input)))
        else:
            image = Image.open(io.BytesIO(base64.b64decode(image_input)))

        return image.convert("RGB")
    except ValueError:
        raise
    except Exception as e:
        raise ValueError(f"Failed to load image: {str(e)}")
