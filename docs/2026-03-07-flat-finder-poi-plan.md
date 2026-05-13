# Dynamic POI Implementation Plan — COMPLETED

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace hardcoded work/gym commute destinations with user-configurable POIs via a settings page.

**Architecture:** New `pois` and `poi_commutes` tables in the shared SQLite DB. Settings page (CRUD) in the UI. Scraper reads POIs from DB instead of hardcoded coordinates. Dynamic weight sliders and metric badges on feed/detail pages. Google Maps link parsing extracts coordinates.

**Tech Stack:** Python, FastAPI, SQLite, Jinja2, vanilla JS, requests (TfL API + redirect following)

---

### Task 1: Google Maps link parser

**Files:**
- Create: `shared/geo.py`
- Create: `tests/test_geo.py`

**Step 1: Write the failing tests**

```python
# tests/test_geo.py
from shared.geo import extract_coords_from_url

def test_extract_coords_from_full_url():
    url = "https://www.google.com/maps/@51.5497263,-0.1782744,2693m/data=!3m1!1e3"
    lat, lng = extract_coords_from_url(url)
    assert abs(lat - 51.5497263) < 0.0001
    assert abs(lng - (-0.1782744)) < 0.0001

def test_extract_coords_from_place_url():
    url = "https://www.google.com/maps/place/Local+Gym/@51.5200,-0.1500,17z/"
    lat, lng = extract_coords_from_url(url)
    assert abs(lat - 51.5200) < 0.0001
    assert abs(lng - (-0.1500)) < 0.0001

def test_extract_coords_returns_none_for_garbage():
    assert extract_coords_from_url("not a url") is None
    assert extract_coords_from_url("https://google.com") is None

def test_extract_coords_from_query_param():
    url = "https://www.google.com/maps?q=51.5200,-0.1500"
    lat, lng = extract_coords_from_url(url)
    assert abs(lat - 51.5200) < 0.0001
    assert abs(lng - (-0.1500)) < 0.0001
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_geo.py -v`
Expected: FAIL (module not found)

**Step 3: Write minimal implementation**

```python
# shared/geo.py
import re
import logging
import requests

log = logging.getLogger("flat-finder")

_COORD_PATTERNS = [
    re.compile(r"@(-?\d+\.\d+),(-?\d+\.\d+)"),       # @lat,lng in path
    re.compile(r"[?&]q=(-?\d+\.\d+),(-?\d+\.\d+)"),   # ?q=lat,lng
]

def _extract_from_text(text: str) -> tuple[float, float] | None:
    for pattern in _COORD_PATTERNS:
        m = pattern.search(text)
        if m:
            return float(m.group(1)), float(m.group(2))
    return None

def extract_coords_from_url(url: str) -> tuple[float, float] | None:
    """Extract lat,lng from a Google Maps URL.
    Handles full URLs with @lat,lng and ?q=lat,lng.
    For short links (goo.gl, maps.app.goo.gl), follows redirects first.
    Returns (lat, lng) or None.
    """
    if "goo.gl" in url or "maps.app" in url:
        try:
            resp = requests.head(url, allow_redirects=True, timeout=10)
            url = resp.url
        except Exception as e:
            log.error(f"Failed to resolve short URL {url}: {e}")
            return None
    return _extract_from_text(url)
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_geo.py -v`
Expected: PASS (4/4)

**Step 5: Commit**

```bash
git add shared/geo.py tests/test_geo.py
git commit -m "feat: add Google Maps URL coordinate parser"
```

---

### Task 2: POI data model and migration

**Files:**
- Modify: `shared/models.py`
- Modify: `tests/test_models.py`

**Step 1: Write the failing tests**

Add to `tests/test_models.py`:

```python
def test_init_db_creates_pois_table():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='pois'")
        assert cursor.fetchone() is not None
        conn.close()

def test_init_db_creates_poi_commutes_table():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='poi_commutes'")
        assert cursor.fetchone() is not None
        conn.close()

def test_migrate_seeds_pois_from_legacy_columns():
    """When pois table is empty but listings have commute_mins, seed Work and Gym POIs."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        # First init creates tables
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        # Insert a listing with legacy commute data
        conn.execute(
            """INSERT INTO listings (id, source, url, first_seen, commute_mins, gym_commute_mins)
               VALUES ('test1', 'rightmove', 'http://x', '2026-01-01', 35, 12)"""
        )
        conn.commit()
        conn.close()
        # Re-init should trigger migration
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        pois = conn.execute("SELECT * FROM pois ORDER BY id").fetchall()
        assert len(pois) == 2
        assert pois[0]["name"] == "Work"
        assert pois[1]["name"] == "Gym"
        # Check poi_commutes populated
        commutes = conn.execute("SELECT * FROM poi_commutes WHERE listing_id = 'test1'").fetchall()
        assert len(commutes) == 2
        vals = {row["poi_id"]: row["commute_mins"] for row in commutes}
        assert vals[pois[0]["id"]] == 35
        assert vals[pois[1]["id"]] == 12
        conn.close()
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL (no pois table)

**Step 3: Write implementation**

Add to `shared/models.py`:

```python
POIS_SCHEMA = """
CREATE TABLE IF NOT EXISTS pois (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    lat         REAL NOT NULL,
    lng         REAL NOT NULL,
    color_index INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);
"""

POI_COMMUTES_SCHEMA = """
CREATE TABLE IF NOT EXISTS poi_commutes (
    listing_id  TEXT NOT NULL,
    poi_id      INTEGER NOT NULL,
    commute_mins INTEGER NOT NULL,
    PRIMARY KEY (listing_id, poi_id)
);
"""
```

Update `init_db()`:

```python
def init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(LISTINGS_SCHEMA)
    conn.execute(SCRAPER_STATE_SCHEMA)
    conn.execute(POIS_SCHEMA)
    conn.execute(POI_COMMUTES_SCHEMA)
    # Migrate existing databases: add new columns if missing
    for col, col_type in [("zone", "TEXT"), ("commute_mins", "INTEGER"),
                          ("gym_commute_mins", "INTEGER")]:
        try:
            conn.execute(f"ALTER TABLE listings ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass
    # Migrate legacy commute data into pois/poi_commutes
    _migrate_legacy_commutes(conn)
    conn.commit()
    conn.close()


def _migrate_legacy_commutes(conn: sqlite3.Connection) -> None:
    """Seed POIs from hardcoded work/gym if pois table is empty and legacy data exists."""
    poi_count = conn.execute("SELECT COUNT(*) FROM pois").fetchone()[0]
    if poi_count > 0:
        return
    # Check if any listing has legacy commute data
    has_legacy = conn.execute(
        "SELECT 1 FROM listings WHERE commute_mins IS NOT NULL OR gym_commute_mins IS NOT NULL LIMIT 1"
    ).fetchone()
    if not has_legacy:
        return
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO pois (name, lat, lng, color_index, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Work", 51.5074, -0.1278, 0, now),
    )
    conn.execute(
        "INSERT INTO pois (name, lat, lng, color_index, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Gym", 51.5200, -0.1500, 1, now),
    )
    work_id = conn.execute("SELECT id FROM pois WHERE name = 'Work'").fetchone()[0]
    gym_id = conn.execute("SELECT id FROM pois WHERE name = 'Gym'").fetchone()[0]
    rows = conn.execute(
        "SELECT id, commute_mins, gym_commute_mins FROM listings "
        "WHERE commute_mins IS NOT NULL OR gym_commute_mins IS NOT NULL"
    ).fetchall()
    for row in rows:
        if row[1] is not None:
            conn.execute(
                "INSERT OR IGNORE INTO poi_commutes (listing_id, poi_id, commute_mins) VALUES (?, ?, ?)",
                (row[0], work_id, row[1]),
            )
        if row[2] is not None:
            conn.execute(
                "INSERT OR IGNORE INTO poi_commutes (listing_id, poi_id, commute_mins) VALUES (?, ?, ?)",
                (row[0], gym_id, row[2]),
            )
```

Also add POI helper functions:

```python
def get_pois(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM pois ORDER BY id").fetchall()
    return [dict(row) for row in rows]

def insert_poi(conn: sqlite3.Connection, name: str, lat: float, lng: float, color_index: int) -> int:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO pois (name, lat, lng, color_index, created_at) VALUES (?, ?, ?, ?, ?)",
        (name, lat, lng, color_index, now),
    )
    conn.commit()
    return cursor.lastrowid

def delete_poi(conn: sqlite3.Connection, poi_id: int) -> None:
    conn.execute("DELETE FROM poi_commutes WHERE poi_id = ?", (poi_id,))
    conn.execute("DELETE FROM pois WHERE id = ?", (poi_id,))
    conn.commit()

def get_poi_commutes_for_listings(conn: sqlite3.Connection, listing_ids: list[str]) -> dict[str, dict[int, int]]:
    """Returns {listing_id: {poi_id: commute_mins}}."""
    if not listing_ids:
        return {}
    placeholders = ",".join("?" for _ in listing_ids)
    rows = conn.execute(
        f"SELECT listing_id, poi_id, commute_mins FROM poi_commutes WHERE listing_id IN ({placeholders})",
        listing_ids,
    ).fetchall()
    result: dict[str, dict[int, int]] = {}
    for row in rows:
        result.setdefault(row["listing_id"], {})[row["poi_id"]] = row["commute_mins"]
    return result

def upsert_poi_commute(conn: sqlite3.Connection, listing_id: str, poi_id: int, commute_mins: int) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO poi_commutes (listing_id, poi_id, commute_mins) VALUES (?, ?, ?)",
        (listing_id, poi_id, commute_mins),
    )
    conn.commit()
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: PASS (all tests including new ones)

**Step 5: Commit**

```bash
git add shared/models.py tests/test_models.py
git commit -m "feat: add pois and poi_commutes tables with legacy migration"
```

---

### Task 3: Simplify commute.py

**Files:**
- Modify: `scraper/commute.py`
- Modify: `tests/test_commute.py`

**Step 1: Write updated tests**

Replace `tests/test_commute.py`:

```python
from unittest.mock import patch, MagicMock
from scraper.commute import tfl_journey_mins

def test_tfl_journey_mins_returns_shortest():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "journeys": [
            {"duration": 45},
            {"duration": 32},
            {"duration": 50},
        ]
    }
    with patch("scraper.commute.requests.get", return_value=mock_resp) as mock_get:
        result = tfl_journey_mins(51.5472, -0.1803, 51.5074, -0.1278)
    assert result == 32
    call_url = mock_get.call_args[0][0]
    assert "51.5472,-0.1803" in call_url
    assert "51.5074,-0.1278" in call_url

def test_tfl_journey_mins_returns_none_on_error():
    with patch("scraper.commute.requests.get", side_effect=Exception("timeout")):
        result = tfl_journey_mins(51.5472, -0.1803, 51.5074, -0.1278)
    assert result is None

def test_tfl_journey_mins_returns_none_for_no_journeys():
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"journeys": []}
    with patch("scraper.commute.requests.get", return_value=mock_resp):
        result = tfl_journey_mins(51.5472, -0.1803, 51.5074, -0.1278)
    assert result is None
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_commute.py -v`
Expected: FAIL (cannot import `tfl_journey_mins`)

**Step 3: Write implementation**

Replace `scraper/commute.py`:

```python
import logging
import requests

log = logging.getLogger("flat-finder")

TFL_MODES = "tube,bus,overground,elizabeth-line,dlr,tram"


def tfl_journey_mins(from_lat: float, from_lng: float,
                     to_lat: float, to_lng: float,
                     arrive_by: str = "0830") -> int | None:
    """Query TfL Journey Planner for shortest journey duration in minutes."""
    url = f"https://api.tfl.gov.uk/Journey/JourneyResults/{from_lat},{from_lng}/to/{to_lat},{to_lng}"
    try:
        resp = requests.get(url, params={
            "mode": TFL_MODES,
            "time": arrive_by,
            "timeIs": "arriving",
        }, timeout=15)
        resp.raise_for_status()
        journeys = resp.json().get("journeys", [])
        if not journeys:
            return None
        return min(j["duration"] for j in journeys)
    except Exception as e:
        log.error(f"TfL journey lookup failed: {e}")
        return None
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_commute.py -v`
Expected: PASS (3/3)

**Step 5: Commit**

```bash
git add scraper/commute.py tests/test_commute.py
git commit -m "refactor: simplify commute.py to single tfl_journey_mins function"
```

---

### Task 4: Update scraper to use POIs from DB

**Files:**
- Modify: `scraper/scraper.py`
- Modify: `tests/test_scraper.py`

**Step 1: Write failing test**

Add to `tests/test_scraper.py`:

```python
from shared.models import insert_poi, get_pois

def test_scraper_fetches_commutes_for_all_pois():
    """run() should fetch commute times for each POI in the DB, not hardcoded ones."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = get_connection(db_path)
        # Seed a POI
        poi_id = insert_poi(conn, "Test Place", 51.50, -0.12, 0)
        conn.close()
        # Insert a new listing
        listing = _make_listing("rm_new")
        listing["latitude"] = 51.54
        listing["longitude"] = -0.17
        with patch("scraper.scraper.fetch_rightmove", return_value=[listing]), \
             patch("scraper.scraper.fetch_openrent", return_value=[]), \
             patch("scraper.scraper.load_zones", return_value=[{
                 "name": "Test", "rightmove_id": "X", "openrent_term": "X",
                 "radius_miles": 1.0, "lat": 51.54, "lng": -0.17
             }]), \
             patch("scraper.scraper.tfl_journey_mins", return_value=25) as mock_tfl, \
             patch("scraper.scraper.DB_PATH", db_path), \
             patch("scraper.scraper.NTFY_TOPIC", ""), \
             patch("scraper.scraper.GMAIL_ADDRESS", ""), \
             patch("scraper.scraper.GMAIL_APP_PASSWORD", ""):
            from scraper.scraper import run
            run()
        conn = get_connection(db_path)
        commutes = conn.execute(
            "SELECT * FROM poi_commutes WHERE listing_id = 'rm_new'"
        ).fetchall()
        conn.close()
        assert len(commutes) == 1
        assert commutes[0]["poi_id"] == poi_id
        assert commutes[0]["commute_mins"] == 25
```

**Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_scraper.py::test_scraper_fetches_commutes_for_all_pois -v`
Expected: FAIL

**Step 3: Write implementation**

Update `scraper/scraper.py` imports:

```python
from scraper.commute import tfl_journey_mins
from shared.models import (init_db, get_connection, insert_listing, get_state, set_state,
                           get_pois, upsert_poi_commute)
```

Remove the import of `get_commute_mins, get_gym_commute_mins`.

Replace the commute-fetching section in `run()` (lines 125-154) with:

```python
    # Load POIs from database
    pois = get_pois(conn)

    # Fetch commute times for new listings
    for listing in new_listings:
        if listing.get("latitude") and listing.get("longitude"):
            for poi in pois:
                mins = tfl_journey_mins(listing["latitude"], listing["longitude"],
                                        poi["lat"], poi["lng"])
                if mins is not None:
                    upsert_poi_commute(conn, listing["id"], poi["id"], mins)
                time.sleep(0.5)

    # Backfill: listings missing commute data for any POI
    if pois:
        for poi in pois:
            missing = conn.execute(
                """SELECT l.id, l.latitude, l.longitude FROM listings l
                   WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL
                   AND NOT EXISTS (
                       SELECT 1 FROM poi_commutes pc
                       WHERE pc.listing_id = l.id AND pc.poi_id = ?
                   )""",
                (poi["id"],),
            ).fetchall()
            if missing:
                log.info(f"Backfilling '{poi['name']}' commute for {len(missing)} listings")
                for row in missing:
                    mins = tfl_journey_mins(row["latitude"], row["longitude"],
                                            poi["lat"], poi["lng"])
                    if mins is not None:
                        upsert_poi_commute(conn, row["id"], poi["id"], mins)
                    time.sleep(0.5)
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_scraper.py -v`
Expected: PASS (all existing + new test)

**Step 5: Commit**

```bash
git add scraper/scraper.py tests/test_scraper.py
git commit -m "feat: scraper fetches commutes for dynamic POIs from DB"
```

---

### Task 5: Settings page backend (UI routes)

**Files:**
- Modify: `ui/main.py`
- Create: `ui/templates/settings.html`
- Modify: `tests/test_ui.py`

**Step 1: Write failing tests**

Add to `tests/test_ui.py`:

```python
from shared.models import get_pois, insert_poi


def test_settings_page_returns_html():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)
        resp = client.get("/settings")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


def test_add_poi_via_settings():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)
        resp = client.post("/settings/poi", data={
            "name": "Office",
            "maps_url": "https://www.google.com/maps/@51.5074,-0.1278,17z/"
        }, follow_redirects=False)
        assert resp.status_code == 303
        conn = get_connection(db_path)
        pois = get_pois(conn)
        conn.close()
        assert len(pois) == 1
        assert pois[0]["name"] == "Office"
        assert abs(pois[0]["lat"] - 51.5074) < 0.001
        assert abs(pois[0]["lng"] - (-0.1278)) < 0.001


def test_delete_poi_via_settings():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        conn = get_connection(db_path)
        poi_id = insert_poi(conn, "Test", 51.5, -0.1, 0)
        conn.close()
        client = _make_app(db_path)
        resp = client.delete(f"/settings/poi/{poi_id}")
        assert resp.status_code == 200
        conn = get_connection(db_path)
        pois = get_pois(conn)
        conn.close()
        assert len(pois) == 0


def test_add_poi_rejects_invalid_url():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)
        resp = client.post("/settings/poi", data={
            "name": "Bad",
            "maps_url": "not a url"
        }, follow_redirects=False)
        assert resp.status_code == 303
        conn = get_connection(db_path)
        pois = get_pois(conn)
        conn.close()
        assert len(pois) == 0
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ui.py::test_settings_page_returns_html tests/test_ui.py::test_add_poi_via_settings tests/test_ui.py::test_delete_poi_via_settings tests/test_ui.py::test_add_poi_rejects_invalid_url -v`
Expected: FAIL

**Step 3: Write implementation**

Add imports to `ui/main.py`:

```python
from shared.models import (init_db, get_connection, get_listings,
                           get_pois, insert_poi, delete_poi,
                           get_poi_commutes_for_listings, upsert_poi_commute)
from shared.geo import extract_coords_from_url
```

Add POI color palette constant:

```python
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
```

Add settings routes:

```python
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
```

Add the Form import at the top:

```python
from fastapi import FastAPI, Form, HTTPException, Request
```

**Step 4: Create settings template**

Create `ui/templates/settings.html`:

```html
{% extends "base.html" %}
{% block title %}Settings - Flat Finder{% endblock %}
{% block content %}

<div class="settings">
    <h1 class="settings__title">Places of Interest</h1>
    <p class="settings__desc">Add locations to track commute times from each listing. Paste a Google Maps link to set the coordinates.</p>

    <form class="settings__form" method="post" action="{{ request.url_for('add_poi') }}">
        <div class="settings__field">
            <label for="poi-name">Name</label>
            <input type="text" id="poi-name" name="name" placeholder="e.g. Office, Gym" required>
        </div>
        <div class="settings__field settings__field--wide">
            <label for="poi-url">Google Maps link</label>
            <input type="url" id="poi-url" name="maps_url" placeholder="https://www.google.com/maps/..." required>
        </div>
        <button type="submit" class="btn-action btn-action--primary">Add</button>
    </form>

    {% if pois %}
    <div class="settings__list">
        {% for poi in pois %}
        <div class="settings__poi" data-poi-id="{{ poi.id }}">
            <span class="settings__poi-swatch" style="background: {{ poi.color.color }}"></span>
            <span class="settings__poi-name">{{ poi.name }}</span>
            <span class="settings__poi-coords">{{ "%.4f"|format(poi.lat) }}, {{ "%.4f"|format(poi.lng) }}</span>
            <button class="settings__poi-delete" data-action="delete-poi" data-id="{{ poi.id }}" title="Remove">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        </div>
        {% endfor %}
    </div>
    {% else %}
    <p class="settings__empty">No places added yet. Add one above to start tracking commute times.</p>
    {% endif %}
</div>

{% endblock %}
```

**Step 4b: Run tests**

Run: `.venv/bin/python -m pytest tests/test_ui.py::test_settings_page_returns_html tests/test_ui.py::test_add_poi_via_settings tests/test_ui.py::test_delete_poi_via_settings tests/test_ui.py::test_add_poi_rejects_invalid_url -v`
Expected: PASS (4/4)

**Step 5: Commit**

```bash
git add ui/main.py ui/templates/settings.html tests/test_ui.py
git commit -m "feat: add settings page for managing POIs"
```

---

### Task 6: Settings page CSS and nav link

**Files:**
- Modify: `ui/static/v2.css`
- Modify: `ui/templates/base.html`

**Step 1: Add settings link to nav**

In `ui/templates/base.html`, add after the Map link (line 21):

```html
<a class="nav__link" href="{{ request.url_for('settings_page') }}">Settings</a>
```

**Step 2: Add settings CSS**

Append to `ui/static/v2.css`:

```css
/* --- Settings page --- */
.settings {
  max-width: 640px;
  margin: 0 auto;
  animation: fadeIn 0.3s ease-out;
}

.settings__title {
  font-family: var(--font-display);
  font-size: 1.5rem;
  font-weight: 700;
  margin: 1.5rem 0 0.25rem;
}

.settings__desc {
  font-size: 0.875rem;
  color: var(--text-muted);
  margin-bottom: 1.5rem;
}

.settings__form {
  display: flex;
  gap: 0.75rem;
  align-items: flex-end;
  flex-wrap: wrap;
  margin-bottom: 2rem;
}

.settings__field {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}
.settings__field label {
  font-size: 0.8rem;
  font-weight: 500;
  color: var(--text-muted);
}
.settings__field input {
  padding: 0.5rem 0.75rem;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  background: var(--surface);
  color: var(--text);
  font-family: var(--font-body);
  font-size: 0.875rem;
}
.settings__field input:focus {
  outline: none;
  border-color: var(--accent);
}
.settings__field--wide { flex: 1; min-width: 200px; }
.settings__field--wide input { width: 100%; }

.settings__list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.settings__poi {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  padding: 0.75rem 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
}

.settings__poi-swatch {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex-shrink: 0;
}

.settings__poi-name {
  font-weight: 600;
  font-size: 0.9rem;
}

.settings__poi-coords {
  font-size: 0.8rem;
  color: var(--text-faint);
  margin-left: auto;
  font-variant-numeric: tabular-nums;
}

.settings__poi-delete {
  border: none;
  background: transparent;
  color: var(--text-faint);
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 4px;
  display: flex;
  transition: all var(--transition);
}
.settings__poi-delete:hover {
  color: var(--no);
  background: var(--no-bg);
}

.settings__empty {
  font-size: 0.875rem;
  color: var(--text-faint);
  text-align: center;
  padding: 2rem;
}
```

**Step 3: Commit**

```bash
git add ui/static/v2.css ui/templates/base.html
git commit -m "feat: settings page styling and nav link"
```

---

### Task 7: Update feed and detail pages for dynamic POIs

**Files:**
- Modify: `ui/main.py` (scoring + data helpers)
- Modify: `ui/templates/feed.html`
- Modify: `ui/templates/detail.html`
- Modify: `ui/static/v2.css` (dynamic POI colors)

**Step 1: Update `_compute_scores()` in `ui/main.py`**

Replace the existing function:

```python
def _compute_scores(listings: list[dict], poi_ids: list[int],
                    weights: dict[int, float] | None = None) -> None:
    """Compute weighted match scores in-place using dynamic POIs."""
    if not poi_ids:
        for l in listings:
            l["match_score"] = None
        return
    # Default: equal weight for all POIs
    if weights is None:
        w = 1.0 / len(poi_ids)
        weights = {pid: w for pid in poi_ids}
    # Normalize weights to sum to 1
    total = sum(weights.values())
    if total > 0:
        weights = {k: v / total for k, v in weights.items()}
    # Collect min/max per POI
    stats: dict[int, dict] = {}
    for pid in poi_ids:
        vals = [l["poi_commutes"][pid] for l in listings
                if pid in l.get("poi_commutes", {})]
        if vals:
            mn, mx = min(vals), max(vals)
            stats[pid] = {"min": mn, "max": mx, "range": mx - mn if mx != mn else 1}
    for l in listings:
        total_score = 0.0
        for pid in poi_ids:
            if pid in stats and pid in l.get("poi_commutes", {}):
                s = stats[pid]
                val = l["poi_commutes"][pid]
                total_score += weights.get(pid, 0) * 100 * (1 - (val - s["min"]) / s["range"])
        l["match_score"] = round(total_score)
```

**Step 2: Update `_get_feed_data()` to load POI commutes**

After building the `listings` list and before `_compute_scores`, add:

```python
    # Load POIs and their commute data
    conn2 = get_connection(UI_DB_PATH)
    pois = get_pois(conn2)
    listing_ids = [l["id"] for l in listings]
    all_commutes = get_poi_commutes_for_listings(conn2, listing_ids)
    conn2.close()
    for l in listings:
        l["poi_commutes"] = all_commutes.get(l["id"], {})
    # Attach POI color info
    for poi in pois:
        poi["color"] = POI_COLORS[poi["color_index"] % len(POI_COLORS)]
    poi_ids = [p["id"] for p in pois]
    _compute_scores(listings, poi_ids)
```

Update the return dict to include `pois`:

```python
    return {
        "listings": listings,
        "sort": sort,
        "sort_options": SORT_OPTIONS,
        "zones": zones,
        "zone": zone,
        "pois": pois,
    }
```

**Step 3: Update `_get_detail_data()` similarly**

After building the listing dict, add:

```python
    conn2 = get_connection(UI_DB_PATH)
    pois = get_pois(conn2)
    commutes_map = get_poi_commutes_for_listings(conn2, [listing_id])
    conn2.close()
    listing["poi_commutes"] = commutes_map.get(listing_id, {})
    for poi in pois:
        poi["color"] = POI_COLORS[poi["color_index"] % len(POI_COLORS)]
    return {"listing": listing, "pois": pois}
```

**Step 4: Update feed.html**

Replace the weight sliders section (lines 29-40):

```html
    {% if pois %}
    <div class="toolbar__sliders" id="weight-sliders">
        {% for poi in pois %}
        <div class="slider-group">
            <label class="slider-label" for="w-poi-{{ poi.id }}">{{ poi.name }}</label>
            <input type="range" id="w-poi-{{ poi.id }}" min="0" max="100" value="50"
                   class="slider poi-weight-slider" data-poi-id="{{ poi.id }}">
            <span class="slider-val" id="w-poi-{{ poi.id }}-val">50%</span>
        </div>
        {% endfor %}
    </div>
    {% endif %}
```

Replace the metric badges section in the card (lines 102-112):

```html
            <div class="listing-card__metrics">
                {% for poi in pois %}
                {% if poi.id in l.poi_commutes %}
                <span class="metric" style="background: var(--poi-bg-{{ poi.color_index % 8 }}); color: var(--poi-color-{{ poi.color_index % 8 }});">{{ l.poi_commutes[poi.id] }} min to {{ poi.name }}</span>
                {% endif %}
                {% endfor %}
                {% if l.distance_mi is not none %}
                <span class="metric metric--station">{{ l.distance_mi }} mi from stn</span>
                {% endif %}
            </div>
```

Update the data attributes on the card `<article>` tag. Replace `data-commute-mins` and `data-gym-commute`:

```html
             {% for poi in pois %}
             data-poi-{{ poi.id }}="{{ l.poi_commutes[poi.id] if poi.id in l.poi_commutes else '' }}"
             {% endfor %}
```

**Step 5: Update detail.html**

Replace the hardcoded commute/gym badges (lines 79-84):

```html
            {% for poi in pois %}
            {% if poi.id in listing.poi_commutes %}
            <span class="metric" style="background: var(--poi-bg-{{ poi.color_index % 8 }}); color: var(--poi-color-{{ poi.color_index % 8 }});">{{ listing.poi_commutes[poi.id] }} min to {{ poi.name }}</span>
            {% endif %}
            {% endfor %}
```

**Step 6: Add POI color CSS variables**

Add to the `:root` block in `v2.css` (replacing the hardcoded `--commute`, `--gym` tokens):

```css
  /* POI palette */
  --poi-color-0: #1d4ed8; --poi-bg-0: #dbeafe;
  --poi-color-1: #c2410c; --poi-bg-1: #ffedd5;
  --poi-color-2: #7c3aed; --poi-bg-2: #ede9fe;
  --poi-color-3: #0f766e; --poi-bg-3: #ccfbf1;
  --poi-color-4: #be123c; --poi-bg-4: #ffe4e6;
  --poi-color-5: #b45309; --poi-bg-5: #fef3c7;
  --poi-color-6: #047857; --poi-bg-6: #d1fae5;
  --poi-color-7: #475569; --poi-bg-7: #f1f5f9;
```

Add dark-mode overrides:

```css
  --poi-color-0: #93c5fd; --poi-bg-0: #172554;
  --poi-color-1: #fdba74; --poi-bg-1: #431407;
  --poi-color-2: #c4b5fd; --poi-bg-2: #2e1065;
  --poi-color-3: #2dd4bf; --poi-bg-3: #042f2e;
  --poi-color-4: #fda4af; --poi-bg-4: #4c0519;
  --poi-color-5: #fcd34d; --poi-bg-5: #451a03;
  --poi-color-6: #34d399; --poi-bg-6: #064e3b;
  --poi-color-7: #94a3b8; --poi-bg-7: #1e293b;
```

Keep `--commute`, `--gym` variables for backward compat (they're still used by `--station` pattern).

**Step 7: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS (some existing tests may need adjustment — see Step 8)

**Step 8: Fix any broken tests**

The `test_feed_page_shows_gym_commute` test checks for "min to gym" text. This will now come from POIs. If the migration seeds a "Gym" POI, the text becomes "min to Gym". Update the test assertion:

```python
def test_feed_page_shows_gym_commute():
    # ... existing setup with gym_commute_mins=12 ...
    # Also seed a Gym POI so the template renders it
    conn = get_connection(db_path)
    poi_id = insert_poi(conn, "Gym", 51.5200, -0.1500, 1)
    from shared.models import upsert_poi_commute
    upsert_poi_commute(conn, "rightmove_1", poi_id, 12)
    conn.close()
    # ...
    assert "min to Gym" in resp.text
```

**Step 9: Commit**

```bash
git add ui/main.py ui/templates/feed.html ui/templates/detail.html ui/static/v2.css tests/test_ui.py
git commit -m "feat: dynamic POI metric badges and weight sliders on feed/detail"
```

---

### Task 8: Update client-side scoring (v2.js)

**Files:**
- Modify: `ui/static/v2.js`

**Step 1: Update `initWeightSliders()`**

Replace the function:

```javascript
function initWeightSliders() {
    var sliders = document.querySelectorAll(".poi-weight-slider");
    if (!sliders.length) return;

    sliders.forEach(function (slider) {
      var valEl = document.getElementById(slider.id + "-val");
      slider.addEventListener("input", function () {
        if (valEl) valEl.textContent = slider.value + "%";
        recalcScores();
      });
    });
  }
```

**Step 2: Update `recalcScores()`**

Replace the function:

```javascript
function recalcScores() {
    var sliders = document.querySelectorAll(".poi-weight-slider");
    if (!sliders.length) return;

    // Collect weights keyed by POI id
    var weights = {};
    var totalWeight = 0;
    sliders.forEach(function (s) {
      var w = parseInt(s.value, 10);
      weights[s.dataset.poiId] = w;
      totalWeight += w;
    });
    // Normalize
    if (totalWeight === 0) totalWeight = 1;

    var cards = Array.from(document.querySelectorAll(".listing-card"));
    if (!cards.length) return;

    // Collect min/max per POI across all cards
    var stats = {};
    Object.keys(weights).forEach(function (pid) {
      var vals = [];
      cards.forEach(function (c) {
        var v = c.dataset["poi" + pid];
        if (v !== undefined && v !== "") vals.push(parseFloat(v));
      });
      if (vals.length) {
        var mn = Math.min.apply(null, vals);
        var mx = Math.max.apply(null, vals);
        stats[pid] = { min: mn, max: mx, range: mx !== mn ? mx - mn : 1 };
      }
    });

    cards.forEach(function (c) {
      var score = 0;
      Object.keys(weights).forEach(function (pid) {
        var v = c.dataset["poi" + pid];
        if (v !== undefined && v !== "" && stats[pid]) {
          var s = stats[pid];
          var normalized = 100 * (1 - (parseFloat(v) - s.min) / s.range);
          score += (weights[pid] / totalWeight) * normalized;
        }
      });
      score = Math.round(score);
      c.dataset.matchScore = score;
      var badge = c.querySelector(".metric--score");
      if (badge) badge.textContent = score;
    });

    // Re-sort cards by score
    var grid = document.querySelector(".listing-grid");
    if (!grid) return;
    cards.sort(function (a, b) {
      return parseInt(b.dataset.matchScore, 10) - parseInt(a.dataset.matchScore, 10);
    });
    cards.forEach(function (c) { grid.appendChild(c); });
  }
```

**Step 3: Add delete POI handler**

Add to the init block:

```javascript
function initDeletePoi() {
    document.querySelectorAll("[data-action='delete-poi']").forEach(function (btn) {
      btn.addEventListener("click", async function () {
        var id = btn.dataset.id;
        var resp = await fetch(API_BASE.replace("/api", "") + "/settings/poi/" + id, {
          method: "DELETE",
        });
        if (resp.ok) {
          btn.closest(".settings__poi").remove();
        }
      });
    });
  }
```

Add `initDeletePoi()` to the DOMContentLoaded handler.

**Step 4: Commit**

```bash
git add ui/static/v2.js
git commit -m "feat: dynamic N-POI weight sliders and scoring in JS"
```

---

### Task 9: Update notifications

**Files:**
- Modify: `scraper/scraper.py`
- Modify: `scraper/notifier.py`

**Step 1: Update notifier to accept POI commute data**

In `scraper/notifier.py`, update `format_ntfy_message`:

```python
def format_ntfy_message(listings: list[dict], pois: list[dict] | None = None) -> tuple[str, str]:
    count = len(listings)
    title = f"{count} new flat{'s' if count != 1 else ''} found"
    lines = []
    for listing in listings:
        address = listing.get("address", "Unknown")
        price = listing.get("price_pcm")
        price_str = f"£{price:,}" if price is not None else "Price unknown"
        parts = [f"{address} - {price_str}"]
        if pois and listing.get("poi_commutes"):
            commute_parts = []
            for poi in pois:
                mins = listing["poi_commutes"].get(poi["id"])
                if mins is not None:
                    commute_parts.append(f"{mins}min to {poi['name']}")
            if commute_parts:
                parts.append(", ".join(commute_parts))
        lines.append(" | ".join(parts))
    body = "\n".join(lines)
    return title, body
```

**Step 2: Update scraper.py to pass POI data to notifier**

In the notification section of `run()`, attach poi_commutes to each listing and pass pois:

```python
    # After commute fetching, before notifications:
    # Attach poi_commutes to new listings for notification
    for listing in new_listings:
        commute_row = conn.execute(
            "SELECT poi_id, commute_mins FROM poi_commutes WHERE listing_id = ?",
            (listing["id"],),
        ).fetchall()
        listing["poi_commutes"] = {row["poi_id"]: row["commute_mins"] for row in commute_row}
```

In the notification call:

```python
        if NTFY_TOPIC:
            title, body = format_ntfy_message(new_listings, pois)
```

**Step 3: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: PASS

**Step 4: Commit**

```bash
git add scraper/scraper.py scraper/notifier.py
git commit -m "feat: include POI commute times in notifications"
```

---

### Task 10: Update pruning to cascade to poi_commutes

**Files:**
- Modify: `scraper/scraper.py`

**Step 1: Update pruning section**

After the existing prune query (line 157-165), add cascade to poi_commutes:

```python
    # Prune listings older than 2 weeks
    pruned = conn.execute(
        "DELETE FROM listings WHERE first_seen < datetime('now', '-14 days')"
    ).rowcount
    if pruned:
        conn.execute(
            "DELETE FROM user_state WHERE listing_id NOT IN (SELECT id FROM listings)"
        )
        conn.execute(
            "DELETE FROM poi_commutes WHERE listing_id NOT IN (SELECT id FROM listings)"
        )
        conn.commit()
        log.info(f"Pruned {pruned} listings older than 2 weeks")
```

**Step 2: Commit**

```bash
git add scraper/scraper.py
git commit -m "fix: cascade listing prune to poi_commutes table"
```

---

### Task 11: Final integration test and cleanup

**Files:**
- Modify: `tests/test_ui.py` (integration smoke test)

**Step 1: Write integration test**

```python
def test_feed_page_with_pois_shows_dynamic_metrics():
    """Feed should show POI-based metrics, not hardcoded commute/gym."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        conn = get_connection(db_path)
        poi_id = insert_poi(conn, "Office", 51.5074, -0.1278, 0)
        from shared.models import upsert_poi_commute
        upsert_poi_commute(conn, "rightmove_1", poi_id, 35)
        conn.close()
        client = _make_app(db_path)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "35 min to Office" in resp.text
        assert "poi-weight-slider" in resp.text
```

**Step 2: Run full test suite**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: ALL PASS

**Step 3: Commit**

```bash
git add tests/test_ui.py
git commit -m "test: add integration test for dynamic POI feed display"
```

**Step 4: Docker rebuild and smoke test**

```bash
docker compose up -d --build
# Verify: https://raspberrypi/flat/settings shows settings page
# Verify: https://raspberrypi/flat/ shows dynamic POI badges
docker logs flat-finder-scraper  # Check no import errors
```

**Step 5: Final commit with CLAUDE.md updates**

Update `CLAUDE.md` key coordinates section to reference settings page instead of hardcoded values. Remove the hardcoded coordinate references.

```bash
git add CLAUDE.md
git commit -m "docs: update CLAUDE.md for dynamic POI feature"
```
