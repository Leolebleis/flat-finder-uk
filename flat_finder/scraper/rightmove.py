import json
import logging
import math
import re
from datetime import UTC, datetime
from urllib.parse import urlencode

import requests

from flat_finder.scraping import check_description, make_retry_session, should_exclude_text

log = logging.getLogger("flat-finder")

SEARCH_URL = "https://www.rightmove.co.uk/property-to-rent/find.html"
PAGE_SIZE = 24

FURNISH_PATTERNS = [
    (r"\bunfurnished\b", "Unfurnished"),
    (r"\bpart[- ]?furnished\b", "Part furnished"),
    (r"\bfurnished\b", "Furnished"),
]


def build_search_url(  # noqa: PLR0913
    location_id: str, radius: float, min_beds: int, max_beds: int, max_price: int, index: int = 0
) -> str:
    params = {
        "locationIdentifier": location_id,
        "radius": radius,
        "minBedrooms": min_beds,
        "maxBedrooms": max_beds,
        "maxPrice": max_price,
        "numberOfPropertiesPerPage": PAGE_SIZE,
        "channel": "RENT",
        "index": index,
        "sortType": 6,  # newest listed
        "propertyTypes": "flat",
        "furnishTypes": "furnished,partFurnished",
        "currencyCode": "GBP",
        "areaSizeUnit": "sqft",
    }
    return f"{SEARCH_URL}?{urlencode(params)}"


def _parse_sqft(size_str: str | None) -> int | None:
    if not size_str:
        return None
    match = re.search(r"([\d,]+)\s*sq", size_str, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def _should_exclude(prop: dict) -> bool:
    return should_exclude_text(
        f"{prop.get('propertyTypeFullDescription', '')} {prop.get('summary', '')} {prop.get('displayAddress', '')}"
    )


def _get_monthly_price(price_data: dict) -> int | None:
    """Extract monthly price, converting from weekly if needed."""
    amount = price_data.get("amount")
    if amount is None:
        return None
    freq = price_data.get("frequency", "monthly")
    if freq == "weekly":
        return math.ceil(amount * 52 / 12)
    return amount


def _detect_furnishing(text: str) -> str | None:
    """Detect furnishing from description text."""
    text_lower = text.lower()
    for pattern, label in FURNISH_PATTERNS:
        if re.search(pattern, text_lower):
            return label
    return None


def parse_rightmove_response(data: dict) -> list[dict]:
    listings = []
    for prop in data.get("properties", []):
        if _should_exclude(prop):
            continue
        description = prop.get("summary", "")
        desc_flags = check_description(description)
        images = prop.get("propertyImages", {}).get("images", [])
        image_url = images[0]["srcUrl"] if images else None
        price_data = prop.get("price", {})
        # Try lettingInformation first (old format), then detect from text
        letting_info = prop.get("lettingInformation", {}) or {}
        furnishing = letting_info.get("furnishType") or _detect_furnishing(description)
        listing = {
            "id": f"rightmove_{prop['id']}",
            "source": "rightmove",
            "url": f"https://www.rightmove.co.uk{prop.get('propertyUrl', '')}",
            "title": prop.get("propertyTypeFullDescription"),
            "price_pcm": _get_monthly_price(price_data),
            "bedrooms": prop.get("bedrooms"),
            "address": prop.get("displayAddress"),
            "latitude": prop.get("location", {}).get("latitude"),
            "longitude": prop.get("location", {}).get("longitude"),
            "description": description,
            "image_url": image_url,
            "property_type": prop.get("propertySubType") or prop.get("propertyTypeFullDescription"),
            "furnishing": furnishing,
            "sqft": _parse_sqft(prop.get("displaySize")),
            "first_seen": datetime.now(UTC).isoformat(),
            "listing_date": prop.get("firstVisibleDate"),
            **desc_flags,
        }
        listings.append(listing)
    return listings


def _extract_next_data(html: str) -> dict:
    """Extract __NEXT_DATA__ JSON from Rightmove HTML page."""
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
    if not match:
        msg = "Could not find __NEXT_DATA__ in Rightmove HTML"
        raise ValueError(msg)
    return json.loads(match.group(1))


def fetch_rightmove(  # noqa: PLR0913
    location_id: str,
    radius: float,
    min_beds: int,
    max_beds: int,
    max_price: int,
    session: requests.Session | None = None,
) -> list[dict]:
    session = session or make_retry_session()
    all_listings = []
    index = 0
    while True:
        url = build_search_url(location_id, radius, min_beds, max_beds, max_price, index)
        try:
            resp = session.get(url, timeout=30)
            resp.raise_for_status()
            next_data = _extract_next_data(resp.text)
        except (requests.RequestException, ValueError):
            if all_listings:
                # A later page failed mid-pagination: keep what we already
                # fetched rather than discarding the whole zone
                log.warning(
                    "Rightmove page at index %d failed; keeping %d listings from earlier pages",
                    index,
                    len(all_listings),
                    exc_info=True,
                )
                break
            raise
        search_results = next_data["props"]["pageProps"]["searchResults"]
        listings = parse_rightmove_response(search_results)
        if not listings:
            break
        all_listings.extend(listings)
        result_count = search_results.get("resultCount", "0")
        if isinstance(result_count, str):
            result_count = int(result_count.replace(",", ""))
        if index + PAGE_SIZE >= result_count:
            break
        index += PAGE_SIZE
    return all_listings
