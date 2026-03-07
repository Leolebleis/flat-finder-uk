import re
import requests
from datetime import datetime, timezone
from urllib.parse import urlencode, quote_plus

from bs4 import BeautifulSoup

from scraper.rightmove import _check_description

BASE_URL = "https://www.openrent.co.uk/properties-to-rent"
EXCLUDE_TERMS = ["shared", "bedsit", "studio", "flat share", "house share", "room available"]


def build_search_url(location: str, radius_km: int, min_beds: int,
                     max_beds: int, max_price: int) -> str:
    """Build an OpenRent search URL from parameters."""
    params = {
        "term": location,
        "within": radius_km,
        "prices_min": 0,
        "prices_max": max_price,
        "bedrooms_min": min_beds,
        "bedrooms_max": max_beds,
        "isLive": "true",
    }
    return f"{BASE_URL}?{urlencode(params, quote_via=quote_plus)}"


def _extract_coordinates(soup: BeautifulSoup) -> tuple[list[int], list[float], list[float]]:
    """Extract PROPERTYIDS, latitudes, and longitudes from inline JS arrays."""
    ids, lats, lngs = [], [], []
    for script in soup.find_all("script"):
        text = script.string or ""
        id_match = re.search(r"var\s+PROPERTYIDS\s*=\s*\[([\s\S]*?)\]", text)
        lat_match = re.search(r"var\s+PROPERTYLISTLATITUDES\s*=\s*\[([\s\S]*?)\]", text)
        lng_match = re.search(r"var\s+PROPERTYLISTLONGITUDES\s*=\s*\[([\s\S]*?)\]", text)
        if id_match:
            ids = [int(x.strip()) for x in id_match.group(1).split(",") if x.strip()]
        if lat_match:
            lats = [float(x.strip()) for x in lat_match.group(1).split(",") if x.strip()]
        if lng_match:
            lngs = [float(x.strip()) for x in lng_match.group(1).split(",") if x.strip()]
    return ids, lats, lngs


def _extract_listing_id(card) -> str | None:
    """Get listing ID from the carousel's data-listing-id attribute, or from the href."""
    carousel = card.select_one("[data-listing-id]")
    if carousel:
        return carousel["data-listing-id"]
    href = card.get("href", "")
    match = re.search(r"/(\d+)$", href)
    return match.group(1) if match else None


def _extract_price(card) -> int | None:
    """Extract monthly price from the pim div."""
    pim = card.select_one(".pim .fs-4.fw-medium.text-primary")
    if not pim:
        return None
    price_text = pim.get_text(strip=True)
    # Remove currency symbol and commas: "£2,100" -> "2100"
    cleaned = re.sub(r"[^\d]", "", price_text)
    return int(cleaned) if cleaned else None


def _extract_title(card) -> str | None:
    """Extract the title from the main heading div."""
    title_div = card.select_one(".fw-medium.text-primary.fs-3")
    return title_div.get_text(strip=True) if title_div else None


def _extract_address(title: str | None) -> str | None:
    """Derive address from title by stripping the bed/type prefix.

    Title format: "1 Bed Flat, Goldhurst Terrace, NW6"
    Address: "Goldhurst Terrace, NW6"
    """
    if not title:
        return None
    parts = title.split(", ", 1)
    return parts[1] if len(parts) > 1 else title


def _extract_description(card) -> str:
    """Extract the description snippet from the listing card."""
    desc_div = card.select_one(".line-clamp-2")
    return desc_div.get_text(strip=True) if desc_div else ""


def _extract_image_url(card) -> str | None:
    """Extract the first property image URL, handling lazy-loaded images."""
    img = card.select_one("img.propertyPic")
    if not img:
        return None
    # Prefer data-src (real image) over src (may be placeholder)
    raw = img.get("data-src") or img.get("src", "")
    if not raw or "NoImageImage" in raw:
        return None
    # Normalise protocol-relative URLs
    if raw.startswith("//"):
        return f"https:{raw}"
    return raw


def _extract_bedrooms(card) -> int | None:
    """Extract bedroom count from the features list."""
    items = card.select("ul.list-unstyled li")
    for li in items:
        text = li.get_text(strip=True).lower()
        match = re.match(r"(\d+)\s*bed", text)
        if match:
            return int(match.group(1))
    return None


def _extract_furnishing(card) -> str | None:
    """Extract furnishing info from the features list."""
    items = card.select("ul.list-unstyled li")
    for li in items:
        text = li.get_text(strip=True)
        if "furnish" in text.lower():
            return text
    return None


def _extract_property_type(title: str | None) -> str | None:
    """Derive property type from the title prefix, e.g. '2 Bed Flat' -> 'Flat'."""
    if not title:
        return None
    # Pattern: "<N> Bed <Type>," or "<Type>,"
    match = re.match(r"(?:\d+\s+Beds?\s+)?(.+?),", title)
    return match.group(1).strip() if match else None


def _should_exclude(title: str, description: str) -> bool:
    """Check if listing should be excluded based on title/description."""
    text = f"{title} {description}".lower()
    return any(term in text for term in EXCLUDE_TERMS)


def parse_openrent_html(html: str) -> list[dict]:
    """Parse OpenRent search results HTML into listing dicts."""
    soup = BeautifulSoup(html, "html.parser")

    # Build coordinate lookup: listing_id -> (lat, lng)
    prop_ids, lats, lngs = _extract_coordinates(soup)
    coord_map: dict[str, tuple[float, float]] = {}
    for i, pid in enumerate(prop_ids):
        if i < len(lats) and i < len(lngs):
            coord_map[str(pid)] = (lats[i], lngs[i])

    cards = soup.select("a.pli.search-property-card")
    listings = []

    for card in cards:
        listing_id = _extract_listing_id(card)
        if not listing_id:
            continue

        title = _extract_title(card)
        description = _extract_description(card)

        if _should_exclude(title or "", description):
            continue

        href = card.get("href", "")
        desc_flags = _check_description(description)
        lat, lng = coord_map.get(listing_id, (None, None))

        listing = {
            "id": f"openrent_{listing_id}",
            "source": "openrent",
            "url": f"https://www.openrent.co.uk{href}",
            "title": title,
            "price_pcm": _extract_price(card),
            "bedrooms": _extract_bedrooms(card),
            "address": _extract_address(title),
            "latitude": lat,
            "longitude": lng,
            "description": description,
            "image_url": _extract_image_url(card),
            "property_type": _extract_property_type(title),
            "furnishing": _extract_furnishing(card),
            "sqft": None,  # Not available on search page
            "first_seen": datetime.now(timezone.utc).isoformat(),
            "listing_date": None,  # Not reliably available on search page
            **desc_flags,
        }
        listings.append(listing)

    return listings


def fetch_openrent(location: str, radius_km: int, min_beds: int,
                   max_beds: int, max_price: int) -> list[dict]:
    """Fetch and parse OpenRent search results."""
    url = build_search_url(location, radius_km, min_beds, max_beds, max_price)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                       "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }
    resp = requests.get(url, headers=headers, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    listings = parse_openrent_html(resp.text)
    # OpenRent doesn't always enforce server-side filters after redirect,
    # so enforce price and bedroom limits client-side
    return [
        l for l in listings
        if (l.get("price_pcm") is None or l["price_pcm"] <= max_price)
        and (l.get("bedrooms") is None or min_beds <= l["bedrooms"] <= max_beds)
    ]
