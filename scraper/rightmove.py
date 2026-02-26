import json
import math
import re
import requests
from datetime import datetime, timezone
from urllib.parse import urlencode

SEARCH_URL = "https://www.rightmove.co.uk/property-to-rent/find.html"
EXCLUDE_TERMS = ["shared", "bedsit", "studio"]
OUTDOOR_PATTERNS = {
    r"\bgarden\b": "garden",
    r"\bbalcony\b": "balcony",
    r"\bterrace\b": "terrace",
    r"\bpatio\b": "patio",
    r"\boutdoor\b": "outdoor space",
}
OUTDOOR_EXCLUDE = re.compile(r"\b(communal|shared|residents)\s+garden", re.IGNORECASE)
STREET_GARDENS = re.compile(r"\b\w+\s+gardens\b", re.IGNORECASE)
APPLIANCE_PATTERNS = {
    "has_dishwasher": [r"dishwasher", r"dish washer", r"dish-washer"],
    "has_washer": [r"washing machine", r"washer[\s/-]?dryer", r"laundry"],
}
FURNISH_PATTERNS = [
    (r"\bunfurnished\b", "Unfurnished"),
    (r"\bpart[- ]?furnished\b", "Part furnished"),
    (r"\bfurnished\b", "Furnished"),
]


def build_search_url(location_id: str, radius: float, min_beds: int,
                     max_beds: int, max_price: int, index: int = 0) -> str:
    params = {
        "locationIdentifier": location_id,
        "radius": radius,
        "minBedrooms": min_beds,
        "maxBedrooms": max_beds,
        "maxPrice": max_price,
        "numberOfPropertiesPerPage": 24,
        "channel": "RENT",
        "index": index,
        "sortType": 6,  # newest listed
        "propertyTypes": "flat",
        "furnishTypes": "furnished,partFurnished",
        "currencyCode": "GBP",
        "areaSizeUnit": "sqft",
    }
    return f"{SEARCH_URL}?{urlencode(params)}"


def _check_description(text: str) -> dict:
    text_lower = text.lower()
    result = {}
    for key, patterns in APPLIANCE_PATTERNS.items():
        result[key] = "yes" if any(re.search(p, text_lower) for p in patterns) else "unknown"
    outdoor_found = []
    # Strip false positives before matching garden
    text_filtered = OUTDOOR_EXCLUDE.sub("", text_lower)
    text_filtered = STREET_GARDENS.sub("", text_filtered)
    for pattern, label in OUTDOOR_PATTERNS.items():
        if re.search(pattern, text_filtered):
            outdoor_found.append(label)
    result["has_outdoor"] = "yes" if outdoor_found else "unknown"
    result["outdoor_type"] = ", ".join(outdoor_found) if outdoor_found else None
    return result


def _parse_sqft(size_str: str | None) -> int | None:
    if not size_str:
        return None
    match = re.search(r"([\d,]+)\s*sq", size_str, re.IGNORECASE)
    if match:
        return int(match.group(1).replace(",", ""))
    return None


def _should_exclude(prop: dict) -> bool:
    text = f"{prop.get('propertyTypeFullDescription', '')} {prop.get('summary', '')} {prop.get('displayAddress', '')}".lower()
    return any(term in text for term in EXCLUDE_TERMS)


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
        desc_flags = _check_description(description)
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
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "listing_date": prop.get("firstVisibleDate"),
            **desc_flags,
        }
        listings.append(listing)
    return listings


def _extract_next_data(html: str) -> dict:
    """Extract __NEXT_DATA__ JSON from Rightmove HTML page."""
    match = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html)
    if not match:
        raise ValueError("Could not find __NEXT_DATA__ in Rightmove HTML")
    return json.loads(match.group(1))


def fetch_rightmove(location_id: str, radius: float, min_beds: int,
                    max_beds: int, max_price: int) -> list[dict]:
    all_listings = []
    index = 0
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    while True:
        url = build_search_url(location_id, radius, min_beds, max_beds, max_price, index)
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        next_data = _extract_next_data(resp.text)
        search_results = next_data["props"]["pageProps"]["searchResults"]
        listings = parse_rightmove_response(search_results)
        if not listings:
            break
        all_listings.extend(listings)
        result_count = search_results.get("resultCount", "0")
        if isinstance(result_count, str):
            result_count = int(result_count.replace(",", ""))
        if index + 24 >= result_count:
            break
        index += 24
    return all_listings
