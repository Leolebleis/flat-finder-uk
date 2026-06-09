"""Zone geometry utilities: centroid, covering radius, point-in-polygon, external lookups."""

import json
import logging
import math

import requests
from shapely.geometry import Point, shape

log = logging.getLogger("flat-finder")

HTTP_OK = 200


def compute_zone_params(geometry: dict) -> dict:
    """Compute centroid and covering radius from a GeoJSON Geometry dict.

    Returns dict with centroid_lat, centroid_lng, covering_radius_km.
    Raises ValueError if geometry is not a valid Polygon.
    """
    geom = shape(geometry)
    if geom.geom_type != "Polygon":
        msg = f"Expected Polygon, got {geom.geom_type}"
        raise ValueError(msg)
    if not geom.is_valid:
        msg = "Invalid polygon geometry"
        raise ValueError(msg)
    centroid = geom.centroid
    # Covering radius: max distance from centroid to any vertex, in km
    max_dist_deg = 0.0
    for coord in geom.exterior.coords:
        d = math.sqrt((coord[0] - centroid.x) ** 2 + (coord[1] - centroid.y) ** 2)
        max_dist_deg = max(max_dist_deg, d)
    # Convert degrees to km (approximate, latitude-dependent)
    lat_rad = math.radians(centroid.y)
    km_per_deg_lat = 111.32
    km_per_deg_lng = 111.32 * math.cos(lat_rad)
    km_per_deg = (km_per_deg_lat + km_per_deg_lng) / 2
    covering_radius_km = max_dist_deg * km_per_deg
    return {
        "centroid_lat": centroid.y,
        "centroid_lng": centroid.x,
        "covering_radius_km": round(covering_radius_km, 2),
    }


def point_in_zone(lat: float, lng: float, geometry_str: str) -> bool:
    """Check if a lat/lng point falls inside a zone polygon (stored as GeoJSON string)."""
    geom = shape(json.loads(geometry_str))
    return geom.contains(Point(lng, lat))


def resolve_postcode(lat: float, lng: float) -> str | None:
    """Reverse-geocode lat/lng to nearest UK postcode outcode via postcodes.io."""
    try:
        resp = requests.get(
            "https://api.postcodes.io/postcodes",
            params={"lon": lng, "lat": lat, "limit": 1},
            timeout=10,
        )
        if resp.status_code != HTTP_OK:
            return None
        results = resp.json().get("result", [])
        if not results:
            return None
        return results[0].get("outcode")
    except requests.RequestException as e:
        log.warning("postcodes.io lookup failed: %s", e)
        return None


def resolve_rightmove_id(query: str) -> str | None:
    """Look up a Rightmove locationIdentifier via the LOS typeahead API."""
    try:
        resp = requests.get(
            "https://los.rightmove.co.uk/typeahead",
            params={"query": query},
            timeout=10,
        )
        if resp.status_code != HTTP_OK:
            return None
        matches = resp.json().get("matches", [])
        if not matches:
            return None
        m = matches[0]
        return f"{m['type']}^{m['id']}"
    except requests.RequestException as e:
        log.warning("Rightmove LOS lookup failed: %s", e)
        return None
