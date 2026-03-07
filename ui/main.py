# ui/main.py
import logging
import math
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from shared.models import (init_db, get_connection, get_listings,
                           get_pois, insert_poi, delete_poi,
                           get_poi_commutes_for_listings, upsert_poi_commute)
from shared.geo import extract_coords_from_url

log = logging.getLogger("flat-finder-ui")

UI_DB_PATH = Path(os.environ.get(
    "FLAT_FINDER_UI_DB",
    "/home/leo/flat-finder-ui.db",
))

USER_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_state (
    listing_id          TEXT PRIMARY KEY,
    seen                BOOLEAN DEFAULT 0,
    favourite           BOOLEAN DEFAULT 0,
    notes               TEXT,
    override_dishwasher TEXT,
    override_washer     TEXT,
    override_outdoor    TEXT,
    updated_at          DATETIME
);
"""


def _init_user_state_table(db_path: Path) -> None:
    """Create the user_state table if it doesn't exist."""
    conn = get_connection(db_path)
    conn.execute(USER_STATE_SCHEMA)
    # Migrate existing databases: add override columns if missing
    for col in ["override_dishwasher", "override_washer", "override_outdoor"]:
        try:
            conn.execute(f"ALTER TABLE user_state ADD COLUMN {col} TEXT")
        except Exception:
            pass
    conn.commit()
    conn.close()


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Initialize DB on startup."""
    init_db(UI_DB_PATH)
    _init_user_state_table(UI_DB_PATH)
    yield


app = FastAPI(title="Flat Finder UI", root_path="/flat", lifespan=lifespan)

# Finchley Road Station coordinates for distance calculation
STATION_LAT = 51.5472
STATION_LNG = -0.1803

POI_COLORS = [
    {"name": "blue",    "color": "#1d4ed8", "bg": "#dbeafe", "dark_color": "#93c5fd", "dark_bg": "#172554"},
    {"name": "orange",  "color": "#c2410c", "bg": "#ffedd5", "dark_color": "#fdba74", "dark_bg": "#431407"},
    {"name": "purple",  "color": "#7c3aed", "bg": "#ede9fe", "dark_color": "#c4b5fd", "dark_bg": "#2e1065"},
    {"name": "teal",    "color": "#0f766e", "bg": "#ccfbf1", "dark_color": "#2dd4bf", "dark_bg": "#042f2e"},
    {"name": "rose",    "color": "#be123c", "bg": "#ffe4e6", "dark_color": "#fda4af", "dark_bg": "#4c0519"},
    {"name": "amber",   "color": "#b45309", "bg": "#fef3c7", "dark_color": "#fcd34d", "dark_bg": "#451a03"},
    {"name": "emerald", "color": "#047857", "bg": "#d1fae5", "dark_color": "#34d399", "dark_bg": "#064e3b"},
    {"name": "slate",   "color": "#475569", "bg": "#f1f5f9", "dark_color": "#94a3b8", "dark_bg": "#1e293b"},
]

def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in miles between two coordinates."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _compute_scores(listings: list[dict], w_commute: float = 0.5, w_gym: float = 0.5) -> None:
    """Compute weighted match scores in-place. Mutates each listing dict."""
    commute_vals = [l["commute_mins"] for l in listings if l.get("commute_mins") is not None]
    gym_vals = [l["gym_commute_mins"] for l in listings if l.get("gym_commute_mins") is not None]

    c_min = c_max = c_range = 0
    g_min = g_max = g_range = 0
    if commute_vals:
        c_min, c_max = min(commute_vals), max(commute_vals)
        c_range = c_max - c_min if c_max != c_min else 1
    if gym_vals:
        g_min, g_max = min(gym_vals), max(gym_vals)
        g_range = g_max - g_min if g_max != g_min else 1

    for l in listings:
        c_score = 0.0
        g_score = 0.0
        if l.get("commute_mins") is not None and commute_vals:
            c_score = 100 * (1 - (l["commute_mins"] - c_min) / c_range)
        if l.get("gym_commute_mins") is not None and gym_vals:
            g_score = 100 * (1 - (l["gym_commute_mins"] - g_min) / g_range)
        l["match_score"] = round(w_commute * c_score + w_gym * g_score)


SORT_OPTIONS = {
    "best_match": "Best match",
    "newest": "Newest first",
    "price_asc": "Price (low to high)",
    "price_desc": "Price (high to low)",
    "size_desc": "Size (largest)",
    "distance": "Distance (nearest)",
    "commute": "Commute (shortest)",
}


def _sort_listings(listings: list[dict], sort: str) -> list[dict]:
    if sort == "best_match":
        return sorted(listings, key=lambda l: -(l.get("match_score") or 0))
    elif sort == "price_asc":
        return sorted(listings, key=lambda l: (l["price_pcm"] is None, l["price_pcm"] or 0))
    elif sort == "price_desc":
        return sorted(listings, key=lambda l: (l["price_pcm"] is None, -(l["price_pcm"] or 0)))
    elif sort == "size_desc":
        return sorted(listings, key=lambda l: (l["sqft"] is None, -(l["sqft"] or 0)))
    elif sort == "distance":
        return sorted(listings, key=lambda l: (l["distance_mi"] is None, l["distance_mi"] or 999))
    elif sort == "commute":
        return sorted(listings, key=lambda l: (l.get("commute_mins") is None, l.get("commute_mins") or 999))
    return listings  # newest - already sorted by first_seen DESC from SQL

# Templates and static files
_ui_dir = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_ui_dir / "templates"))
app.mount("/static", StaticFiles(directory=str(_ui_dir / "static")), name="static")


# --- Data helpers ---

def _get_feed_data(sort: str, zone: str) -> dict:
    """Build feed page context data."""
    if sort not in SORT_OPTIONS:
        sort = "newest"
    conn = get_connection(UI_DB_PATH)
    rows = conn.execute(
        """SELECT l.*, us.seen, us.favourite, us.notes,
                  us.override_dishwasher, us.override_washer, us.override_outdoor
           FROM listings l
           LEFT JOIN user_state us ON l.id = us.listing_id
           ORDER BY l.first_seen DESC"""
    ).fetchall()
    conn.close()
    listings = []
    for row in rows:
        d = dict(row)
        d["seen"] = bool(d["seen"]) if d["seen"] else False
        d["favourite"] = bool(d["favourite"]) if d["favourite"] else False
        if d.get("latitude") and d.get("longitude"):
            d["distance_mi"] = round(_haversine_miles(
                STATION_LAT, STATION_LNG, d["latitude"], d["longitude"]
            ), 2)
        else:
            d["distance_mi"] = None
        if d.get("override_dishwasher"):
            d["has_dishwasher"] = d["override_dishwasher"]
        if d.get("override_washer"):
            d["has_washer"] = d["override_washer"]
        if d.get("override_outdoor"):
            d["has_outdoor"] = d["override_outdoor"]
        listings.append(d)
    zones = sorted(set(d.get("zone") or "Unknown" for d in listings))
    if zone != "all":
        listings = [l for l in listings if (l.get("zone") or "Unknown") == zone]
    _compute_scores(listings)
    listings = _sort_listings(listings, sort)
    return {
        "listings": listings,
        "sort": sort,
        "sort_options": SORT_OPTIONS,
        "zones": zones,
        "zone": zone,
    }


def _get_detail_data(listing_id: str) -> dict:
    """Build detail page context data."""
    conn = get_connection(UI_DB_PATH)
    row = conn.execute(
        "SELECT * FROM listings WHERE id = ?", (listing_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Listing not found")
    listing = dict(row)
    state_row = conn.execute(
        "SELECT * FROM user_state WHERE listing_id = ?", (listing_id,)
    ).fetchone()
    conn.close()
    listing["seen"] = bool(state_row["seen"]) if state_row else False
    listing["favourite"] = bool(state_row["favourite"]) if state_row else False
    listing["notes"] = state_row["notes"] if state_row else None
    listing["override_dishwasher"] = state_row["override_dishwasher"] if state_row else None
    listing["override_washer"] = state_row["override_washer"] if state_row else None
    listing["override_outdoor"] = state_row["override_outdoor"] if state_row else None
    listing["original_dishwasher"] = listing["has_dishwasher"]
    listing["original_washer"] = listing["has_washer"]
    listing["original_outdoor"] = listing["has_outdoor"]
    if listing.get("override_dishwasher"):
        listing["has_dishwasher"] = listing["override_dishwasher"]
    if listing.get("override_washer"):
        listing["has_washer"] = listing["override_washer"]
    if listing.get("override_outdoor"):
        listing["has_outdoor"] = listing["override_outdoor"]
    return {"listing": listing}


# --- Template routes ---

@app.get("/", response_class=HTMLResponse, name="feed_page")
def feed_page(request: Request, sort: str = "newest", zone: str = "all"):
    return templates.TemplateResponse(request, "feed.html", _get_feed_data(sort, zone))


@app.get("/map", response_class=HTMLResponse, name="map_page")
def map_page(request: Request):
    return templates.TemplateResponse(request, "map.html")


@app.get("/settings", response_class=HTMLResponse, name="settings_page")
def settings_page(request: Request):
    conn = get_connection(UI_DB_PATH)
    pois = get_pois(conn)
    conn.close()
    for poi in pois:
        poi["color"] = POI_COLORS[poi["color_index"] % len(POI_COLORS)]
    return templates.TemplateResponse(request, "settings.html", {"pois": pois})


@app.post("/settings/poi", name="add_poi")
def add_poi(request: Request, name: str = Form(...), maps_url: str = Form(...)):
    from starlette.responses import RedirectResponse
    coords = extract_coords_from_url(maps_url)
    if not coords or not name.strip():
        return RedirectResponse(request.url_for("settings_page"), status_code=303)
    lat, lng = coords
    conn = get_connection(UI_DB_PATH)
    existing_pois = get_pois(conn)
    color_index = len(existing_pois) % len(POI_COLORS)
    poi_id = insert_poi(conn, name.strip(), lat, lng, color_index)
    conn.close()
    # Trigger backfill in background
    import threading
    threading.Thread(target=_backfill_poi, args=(poi_id, lat, lng), daemon=True).start()
    return RedirectResponse(request.url_for("settings_page"), status_code=303)


@app.delete("/settings/poi/{poi_id}", name="delete_poi")
def delete_poi_route(poi_id: int):
    conn = get_connection(UI_DB_PATH)
    delete_poi(conn, poi_id)
    conn.close()
    return {"ok": True}


def _backfill_poi(poi_id: int, poi_lat: float, poi_lng: float) -> None:
    """Background thread: fetch commute times for all listings missing this POI."""
    import time
    from scraper.commute import tfl_journey_mins
    conn = get_connection(UI_DB_PATH)
    rows = conn.execute(
        """SELECT id, latitude, longitude FROM listings
           WHERE latitude IS NOT NULL AND longitude IS NOT NULL
           AND id NOT IN (SELECT listing_id FROM poi_commutes WHERE poi_id = ?)""",
        (poi_id,),
    ).fetchall()
    for row in rows:
        mins = tfl_journey_mins(row["latitude"], row["longitude"], poi_lat, poi_lng)
        if mins is not None:
            upsert_poi_commute(conn, row["id"], poi_id, mins)
        time.sleep(0.5)
    conn.close()


@app.get("/listing/{listing_id}", response_class=HTMLResponse, name="detail_page")
def detail_page(listing_id: str, request: Request):
    return templates.TemplateResponse(request, "detail.html", _get_detail_data(listing_id))


# --- API routes ---

class StateUpdate(BaseModel):
    seen: bool | None = None
    favourite: bool | None = None
    notes: str | None = None
    override_dishwasher: str | None = None
    override_washer: str | None = None
    override_outdoor: str | None = None


@app.post("/api/state/{listing_id}")
def update_state(listing_id: str, body: StateUpdate):
    conn = get_connection(UI_DB_PATH)
    # Verify listing exists
    row = conn.execute(
        "SELECT id FROM listings WHERE id = ?", (listing_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Listing not found")

    # Upsert: get existing state or create defaults
    existing = conn.execute(
        "SELECT * FROM user_state WHERE listing_id = ?", (listing_id,)
    ).fetchone()

    seen = body.seen if body.seen is not None else (bool(existing["seen"]) if existing else False)
    favourite = body.favourite if body.favourite is not None else (bool(existing["favourite"]) if existing else False)
    notes = body.notes if body.notes is not None else (existing["notes"] if existing else None)

    # Override fields: use model_fields_set to distinguish "not sent" from "sent as null"
    override_dishwasher = existing["override_dishwasher"] if existing else None
    if "override_dishwasher" in body.model_fields_set:
        override_dishwasher = body.override_dishwasher
    override_washer = existing["override_washer"] if existing else None
    if "override_washer" in body.model_fields_set:
        override_washer = body.override_washer
    override_outdoor = existing["override_outdoor"] if existing else None
    if "override_outdoor" in body.model_fields_set:
        override_outdoor = body.override_outdoor

    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT OR REPLACE INTO user_state
           (listing_id, seen, favourite, notes,
            override_dishwasher, override_washer, override_outdoor, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (listing_id, int(seen), int(favourite), notes,
         override_dishwasher, override_washer, override_outdoor, now),
    )
    conn.commit()
    conn.close()

    return {
        "listing_id": listing_id,
        "seen": seen,
        "favourite": favourite,
        "notes": notes,
        "override_dishwasher": override_dishwasher,
        "override_washer": override_washer,
        "override_outdoor": override_outdoor,
        "updated_at": now,
    }


@app.get("/api/listings")
def api_listings():
    conn = get_connection(UI_DB_PATH)
    rows = conn.execute(
        """SELECT l.*, us.seen, us.favourite, us.notes,
                  us.override_dishwasher, us.override_washer, us.override_outdoor
           FROM listings l
           LEFT JOIN user_state us ON l.id = us.listing_id
           ORDER BY l.first_seen DESC"""
    ).fetchall()
    conn.close()
    result = []
    for row in rows:
        d = dict(row)
        # Normalize booleans from SQLite ints
        d["seen"] = bool(d["seen"]) if d["seen"] else False
        d["favourite"] = bool(d["favourite"]) if d["favourite"] else False
        # Apply label overrides
        if d.get("override_dishwasher"):
            d["has_dishwasher"] = d["override_dishwasher"]
        if d.get("override_washer"):
            d["has_washer"] = d["override_washer"]
        if d.get("override_outdoor"):
            d["has_outdoor"] = d["override_outdoor"]
        result.append(d)
    return result
