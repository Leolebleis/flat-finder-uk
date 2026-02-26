import re
import requests
from datetime import datetime, timezone
from urllib.parse import urlencode

SEARCH_URL = "https://www.rightmove.co.uk/api/_search"
EXCLUDE_TERMS = ["shared", "bedsit", "studio"]
OUTDOOR_TERMS = {"garden": "garden", "balcony": "balcony", "terrace": "terrace", "patio": "patio", "outdoor": "outdoor space"}
APPLIANCE_PATTERNS = {
    "has_dishwasher": [r"dishwasher", r"dish washer", r"dish-washer"],
    "has_washer": [r"washing machine", r"washer[\s/-]?dryer", r"laundry"],
}


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
        "propertyTypes": "flat,maisonette",
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
    for term, label in OUTDOOR_TERMS.items():
        if term in text_lower:
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


def parse_rightmove_response(data: dict) -> list[dict]:
    listings = []
    for prop in data.get("properties", []):
        if _should_exclude(prop):
            continue
        description = prop.get("summary", "")
        desc_flags = _check_description(description)
        images = prop.get("propertyImages", {}).get("images", [])
        image_url = images[0]["srcUrl"] if images else None
        letting_info = prop.get("lettingInformation", {})
        listing = {
            "id": f"rightmove_{prop['id']}",
            "source": "rightmove",
            "url": f"https://www.rightmove.co.uk{prop.get('propertyUrl', '')}",
            "title": prop.get("propertyTypeFullDescription"),
            "price_pcm": prop.get("price", {}).get("amount"),
            "bedrooms": prop.get("bedrooms"),
            "address": prop.get("displayAddress"),
            "latitude": prop.get("location", {}).get("latitude"),
            "longitude": prop.get("location", {}).get("longitude"),
            "description": description,
            "image_url": image_url,
            "property_type": prop.get("propertyTypeFullDescription"),
            "furnishing": letting_info.get("furnishType"),
            "sqft": _parse_sqft(prop.get("displaySize")),
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "listing_date": prop.get("firstVisibleDate"),
            **desc_flags,
        }
        listings.append(listing)
    return listings


def fetch_rightmove(location_id: str, radius: float, min_beds: int,
                    max_beds: int, max_price: int) -> list[dict]:
    all_listings = []
    index = 0
    while True:
        url = build_search_url(location_id, radius, min_beds, max_beds, max_price, index)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "application/json",
        }
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        listings = parse_rightmove_response(data)
        if not listings:
            break
        all_listings.extend(listings)
        result_count = data.get("resultCount", "0")
        if isinstance(result_count, str):
            result_count = int(result_count.replace(",", ""))
        if index + 24 >= result_count:
            break
        index += 24
    return all_listings
