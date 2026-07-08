"""Helpers shared between Rightmove and OpenRent scrapers."""

import re
from typing import Protocol

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


class HTMLFetcher(Protocol):
    """Anything that can GET a page like a requests session (see ScraplingSession)."""

    def get(self, url: str, *, timeout: float = 30) -> requests.Response: ...


EXCLUDE_TERMS = ["shared", "bedsit", "studio", "flat share", "house share", "room available"]

# NOTE: bumping the Chrome version here gets 403'd by Rightmove's WAF
# (UA claim vs TLS-fingerprint consistency check) — Chrome/120 passes, tested 2026-07-03
HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-GB,en;q=0.9",
}


# Upstream statuses worth retrying on any transport (urllib3 Retry here,
# ScraplingSession's own retry loop on the MCP path)
TRANSIENT_STATUSES = frozenset({429, 500, 502, 503, 504})


def make_retry_session() -> requests.Session:
    """Build a requests session that retries transient failures with backoff.

    Retries connection errors, read timeouts, and 429/5xx responses (honouring
    Retry-After on 429/503). Backoff is jittered so the retry cadence doesn't
    itself look bot-like.
    """
    retry = Retry(
        total=3,
        status_forcelist=TRANSIENT_STATUSES,
        backoff_factor=2,
        backoff_jitter=1,
        allowed_methods=("GET",),
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(HTTP_HEADERS)
    return session


OUTDOOR_PATTERNS = {
    r"\bgarden\b": "garden",
    r"\bbalcony\b": "balcony",
    r"\bterrace\b": "terrace",
    r"\bpatio\b": "patio",
    r"\boutdoor\b": "outdoor space",
}
_OUTDOOR_EXCLUDE = re.compile(r"\b(communal|shared|residents)\s+garden", re.IGNORECASE)
_STREET_GARDENS = re.compile(r"\b\w+\s+gardens\b", re.IGNORECASE)
APPLIANCE_PATTERNS = {
    "has_dishwasher": [r"dishwasher", r"dish washer", r"dish-washer"],
    "has_washer": [r"washing machine", r"washer[\s/-]?dryer", r"laundry"],
}

# Pre-compile once at module load so we don't recompile per listing
_APPLIANCE_REGEXES = {key: [re.compile(p) for p in patterns] for key, patterns in APPLIANCE_PATTERNS.items()}
_OUTDOOR_REGEXES = [(re.compile(p), label) for p, label in OUTDOOR_PATTERNS.items()]


def should_exclude_text(text: str) -> bool:
    """Return True if text mentions any excluded property type (shared, studio, etc.)."""
    text_lower = text.lower()
    return any(term in text_lower for term in EXCLUDE_TERMS)


def check_description(text: str) -> dict:
    """Extract appliance + outdoor flags from a listing description."""
    text_lower = text.lower()
    result = {}
    for key, regexes in _APPLIANCE_REGEXES.items():
        result[key] = "yes" if any(r.search(text_lower) for r in regexes) else "unknown"
    # Strip false positives (communal garden, street names like "Maida Gardens") before matching outdoor
    text_filtered = _OUTDOOR_EXCLUDE.sub("", text_lower)
    text_filtered = _STREET_GARDENS.sub("", text_filtered)
    outdoor_found = [label for r, label in _OUTDOOR_REGEXES if r.search(text_filtered)]
    result["has_outdoor"] = "yes" if outdoor_found else "unknown"
    result["outdoor_type"] = ", ".join(outdoor_found) if outdoor_found else None
    return result
