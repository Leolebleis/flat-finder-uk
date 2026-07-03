import re
from datetime import UTC, datetime
from urllib.parse import quote_plus, urlencode

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

from flat_finder.scraping import check_description, make_retry_session, should_exclude_text

BASE_URL = "https://www.openrent.co.uk/properties-to-rent"


def build_search_url(location: str, radius_km: int, min_beds: int, max_beds: int, max_price: int) -> str:
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


def _extract_listing_id(card: Tag) -> str | None:
    """Get listing ID from the carousel's data-listing-id attribute, or from the href."""
    carousel = card.select_one("[data-listing-id]")
    if carousel:
        value = carousel.get("data-listing-id")
        return value if isinstance(value, str) else None
    href = card.get("href", "")
    if not isinstance(href, str):
        return None
    match = re.search(r"/(\d+)$", href)
    return match.group(1) if match else None


def _extract_price(card: Tag) -> int | None:
    """Extract monthly price from the pim div."""
    pim = card.select_one(".pim .fs-4.fw-medium.text-primary")
    if not pim:
        return None
    price_text = pim.get_text(strip=True)
    # Remove currency symbol and commas: "£2,100" -> "2100"
    cleaned = re.sub(r"[^\d]", "", price_text)
    return int(cleaned) if cleaned else None


def _extract_title(card: Tag) -> str | None:
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


def _extract_description(card: Tag) -> str:
    """Extract the description snippet from the listing card."""
    desc_div = card.select_one(".line-clamp-2")
    return desc_div.get_text(strip=True) if desc_div else ""


def _extract_image_url(card: Tag) -> str | None:
    """Extract the first property image URL, handling lazy-loaded images."""
    img = card.select_one("img.propertyPic")
    if not img:
        return None
    # Prefer data-src (real image) over src (may be placeholder)
    raw = img.get("data-src") or img.get("src", "")
    if not isinstance(raw, str) or not raw or "NoImageImage" in raw:
        return None
    # Normalise protocol-relative URLs
    if raw.startswith("//"):
        return f"https:{raw}"
    return raw


def _extract_bedrooms(card: Tag) -> int | None:
    """Extract bedroom count from the features list."""
    items = card.select("ul.list-unstyled li")
    for li in items:
        text = li.get_text(strip=True).lower()
        match = re.match(r"(\d+)\s*bed", text)
        if match:
            return int(match.group(1))
    return None


def _extract_furnishing(card: Tag) -> str | None:
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
    match = re.match(r"(?:\d+\s+Beds?\s+)?(.+?),", title)
    return match.group(1).strip() if match else None


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

        if should_exclude_text(f"{title or ''} {description}"):
            continue

        href = card.get("href", "")
        desc_flags = check_description(description)
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
            "first_seen": datetime.now(UTC).isoformat(),
            "listing_date": None,  # Not reliably available on search page
            **desc_flags,
        }
        listings.append(listing)

    return listings


def fetch_openrent(  # noqa: PLR0913
    location: str,
    radius_km: int,
    min_beds: int,
    max_beds: int,
    max_price: int,
    session: requests.Session | None = None,
) -> list[dict]:
    """Fetch and parse OpenRent search results."""
    if session is None:
        session = make_retry_session()
    url = build_search_url(location, radius_km, min_beds, max_beds, max_price)
    resp = session.get(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()
    listings = parse_openrent_html(resp.text)
    # OpenRent doesn't always enforce server-side filters after redirect,
    # so enforce price and bedroom limits client-side
    return [
        listing
        for listing in listings
        if (listing.get("price_pcm") is None or listing["price_pcm"] <= max_price)
        and (listing.get("bedrooms") is None or min_beds <= listing["bedrooms"] <= max_beds)
    ]
