import logging
import re

import requests

log = logging.getLogger("flat-finder")

_COORD_PATTERNS = [
    re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)"),  # @lat,lng in path
    re.compile(r"[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)"),  # ?q=lat,lng
]


def _extract_from_text(text: str) -> tuple[float, float] | None:
    for pattern in _COORD_PATTERNS:
        m = pattern.search(text)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None


def extract_coords_from_url(url: str) -> tuple[float, float] | None:
    """Extract lat,lng from a Google Maps URL.
    Handles full URLs with @lat,lng and ?q=lat,lng.
    For short links (goo.gl, maps.app.goo.gl), follows redirects first.
    Returns (lat, lng) or None.
    """
    if "goo.gl" in url or "maps.app" in url:
        try:
            resp = requests.head(url, allow_redirects=True, timeout=10)
            url = resp.url
        except requests.RequestException:
            log.exception("Failed to resolve short URL %s", url)
            return None
    return _extract_from_text(url)
