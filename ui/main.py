# ui/main.py
import logging
import math
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from shared.models import init_db, get_connection, get_listings

log = logging.getLogger("flat-finder-ui")

UI_DB_PATH = Path(os.environ.get(
    "FLAT_FINDER_UI_DB",
    "/home/leo/flat-finder-ui.db",
))

USER_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_state (
    listing_id TEXT PRIMARY KEY,
    seen       BOOLEAN DEFAULT 0,
    favourite  BOOLEAN DEFAULT 0,
    notes      TEXT,
    updated_at DATETIME
);
"""


def _init_user_state_table(db_path: Path) -> None:
    """Create the user_state table if it doesn't exist."""
    conn = get_connection(db_path)
    conn.execute(USER_STATE_SCHEMA)
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

# Anytime Fitness Swiss Cottage (Harben Parade, NW3)
GYM_LAT = 51.5445
GYM_LNG = -0.1762


def _haversine_miles(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance in miles between two coordinates."""
    R = 3958.8  # Earth radius in miles
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


SORT_OPTIONS = {
    "newest": "Newest first",
    "price_asc": "Price (low to high)",
    "price_desc": "Price (high to low)",
    "size_desc": "Size (largest)",
    "distance": "Distance (nearest)",
    "commute": "Commute (shortest)",
}


def _sort_listings(listings: list[dict], sort: str) -> list[dict]:
    if sort == "price_asc":
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


# --- Template routes ---

@app.get("/", response_class=HTMLResponse, name="feed_page")
def feed_page(request: Request, sort: str = "newest", zone: str = "all"):
    if sort not in SORT_OPTIONS:
        sort = "newest"
    conn = get_connection(UI_DB_PATH)
    rows = conn.execute(
        """SELECT l.*, us.seen, us.favourite, us.notes
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
        d["gym_distance_mi"] = round(_haversine_miles(
            GYM_LAT, GYM_LNG, d["latitude"], d["longitude"]
        ), 2) if d.get("latitude") and d.get("longitude") else None
        listings.append(d)
    zones = sorted(set(d.get("zone") or "Unknown" for d in listings))
    if zone != "all":
        listings = [l for l in listings if (l.get("zone") or "Unknown") == zone]
    listings = _sort_listings(listings, sort)
    return templates.TemplateResponse(request, "feed.html", {
        "listings": listings,
        "sort": sort,
        "sort_options": SORT_OPTIONS,
        "zones": zones,
        "zone": zone,
    })


@app.get("/map", response_class=HTMLResponse, name="map_page")
def map_page(request: Request):
    return templates.TemplateResponse(request, "map.html")


@app.get("/listing/{listing_id}", response_class=HTMLResponse, name="detail_page")
def detail_page(listing_id: str, request: Request):
    conn = get_connection(UI_DB_PATH)
    row = conn.execute(
        "SELECT * FROM listings WHERE id = ?", (listing_id,)
    ).fetchone()
    if not row:
        conn.close()
        raise HTTPException(status_code=404, detail="Listing not found")
    listing = dict(row)
    # Attach user state if present
    state_row = conn.execute(
        "SELECT * FROM user_state WHERE listing_id = ?", (listing_id,)
    ).fetchone()
    conn.close()
    listing["seen"] = bool(state_row["seen"]) if state_row else False
    listing["favourite"] = bool(state_row["favourite"]) if state_row else False
    listing["notes"] = state_row["notes"] if state_row else None
    if listing.get("latitude") and listing.get("longitude"):
        listing["gym_distance_mi"] = round(_haversine_miles(
            GYM_LAT, GYM_LNG, listing["latitude"], listing["longitude"]
        ), 2)
    else:
        listing["gym_distance_mi"] = None
    return templates.TemplateResponse(request, "detail.html", {
        "listing": listing,
    })


# --- API routes ---

class StateUpdate(BaseModel):
    seen: bool | None = None
    favourite: bool | None = None
    notes: str | None = None


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
    now = datetime.now(timezone.utc).isoformat()

    conn.execute(
        """INSERT OR REPLACE INTO user_state
           (listing_id, seen, favourite, notes, updated_at)
           VALUES (?, ?, ?, ?, ?)""",
        (listing_id, int(seen), int(favourite), notes, now),
    )
    conn.commit()
    conn.close()

    return {
        "listing_id": listing_id,
        "seen": seen,
        "favourite": favourite,
        "notes": notes,
        "updated_at": now,
    }


@app.get("/api/listings")
def api_listings():
    conn = get_connection(UI_DB_PATH)
    rows = conn.execute(
        """SELECT l.*, us.seen, us.favourite, us.notes
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
        result.append(d)
    return result
