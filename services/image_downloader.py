"""
Image downloader with retry logic and format normalisation.
Returns a PIL Image (RGB) ready for downstream processing.
"""

import io
import time
from typing import Optional

import requests
from PIL import Image

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}

_TIMEOUT   = 12   # seconds per attempt
_MAX_RETRY = 3
_RETRY_BACKOFF = 1.5  # seconds between retries


def download_image(url: str) -> Image.Image:
    """
    Download image from URL and return as PIL RGB Image.

    Raises:
        ValueError: if the URL cannot be fetched or the response is not an image
        after _MAX_RETRY attempts.
    """
    last_error: Optional[Exception] = None

    for attempt in range(1, _MAX_RETRY + 1):
        try:
            response = requests.get(
                url, headers=_HEADERS, timeout=_TIMEOUT, stream=True
            )
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            if "image" not in content_type and "octet-stream" not in content_type:
                raise ValueError(
                    f"URL did not return an image (Content-Type: {content_type})"
                )

            raw = response.content
            image = Image.open(io.BytesIO(raw)).convert("RGB")
            return image

        except (requests.RequestException, OSError) as exc:
            last_error = exc
            if attempt < _MAX_RETRY:
                time.sleep(_RETRY_BACKOFF * attempt)

    raise ValueError(
        f"Failed to download image from {url!r} "
        f"after {_MAX_RETRY} attempts: {last_error}"
    )
