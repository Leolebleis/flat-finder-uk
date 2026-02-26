# ui/main.py
import asyncio
import logging
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
from ui.sync import sync_from_vps

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
    """Initialize DB and start background sync on startup."""
    init_db(UI_DB_PATH)
    _init_user_state_table(UI_DB_PATH)

    async def _sync_loop():
        while True:
            try:
                await asyncio.to_thread(sync_from_vps, UI_DB_PATH)
            except Exception as e:
                log.error(f"Background sync error: {e}")
            await asyncio.sleep(300)

    task = asyncio.create_task(_sync_loop())
    yield
    task.cancel()


app = FastAPI(title="Flat Finder UI", root_path="/flat", lifespan=lifespan)

# Templates and static files
_ui_dir = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(_ui_dir / "templates"))
app.mount("/static", StaticFiles(directory=str(_ui_dir / "static")), name="static")


# --- Template routes ---

@app.get("/", response_class=HTMLResponse, name="feed_page")
def feed_page(request: Request):
    conn = get_connection(UI_DB_PATH)
    rows = conn.execute(
        """SELECT l.*, us.seen, us.favourite, us.notes
           FROM listings l
           LEFT JOIN user_state us ON l.id = us.listing_id
           ORDER BY l.first_seen DESC
           LIMIT 50"""
    ).fetchall()
    conn.close()
    listings = []
    for row in rows:
        d = dict(row)
        d["seen"] = bool(d["seen"]) if d["seen"] else False
        d["favourite"] = bool(d["favourite"]) if d["favourite"] else False
        listings.append(d)
    return templates.TemplateResponse(request, "feed.html", {
        "listings": listings,
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
