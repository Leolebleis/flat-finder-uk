# Drawable Zones Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace static zones.json with user-drawn polygon zones managed via the Settings UI, with post-filtering in the scraper.

**Architecture:** Zones stored as GeoJSON Geometry TEXT in SQLite `zones` table. Leaflet-Geoman for polygon drawing on Settings page. Shapely for centroid/radius computation and point-in-polygon post-filtering in scraper. Zone polygons rendered as read-only overlays on listings map. Auto-resolution of Rightmove IDs via LOS typeahead and postcodes via postcodes.io.

**Tech Stack:** Python (Shapely, FastAPI), SQLite, Leaflet + Leaflet-Geoman (CDN), postcodes.io API, Rightmove LOS typeahead API

**Skills:** Use `frontend-design` for Settings UI zone panel and map overlays. Use `playwright-skill` for browser testing the drawing UX. Use `test-driven-development` for scraper post-filtering logic.

---

### Task 1: DB Schema + Zone CRUD in shared/models.py

**Files:**
- Modify: `shared/models.py`
- Test: `tests/test_models.py`

**Step 1: Write failing tests for zones table and CRUD**

Add to `tests/test_models.py`:

```python
from shared.models import (
    init_db, get_connection, get_pois, insert_poi, delete_poi,
    get_poi_commutes_for_listings, upsert_poi_commute,
    get_zones, insert_zone, update_zone, delete_zone,
)

SAMPLE_GEOMETRY = '{"type":"Polygon","coordinates":[[[-0.19,51.54],[-0.17,51.54],[-0.17,51.55],[-0.19,51.55],[-0.19,51.54]]]}'

def test_init_db_creates_zones_table():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='zones'")
        assert cursor.fetchone() is not None
        conn.close()

def test_insert_and_get_zones():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        zone_id = insert_zone(conn, "NW6 Area", SAMPLE_GEOMETRY,
                              centroid_lat=51.545, centroid_lng=-0.18,
                              covering_radius_km=1.2,
                              rightmove_id="OUTCODE^1862",
                              openrent_term="NW6",
                              color_index=0)
        assert isinstance(zone_id, int)
        zones = get_zones(conn)
        assert len(zones) == 1
        assert zones[0]["name"] == "NW6 Area"
        assert zones[0]["geometry"] == SAMPLE_GEOMETRY
        assert zones[0]["centroid_lat"] == 51.545
        assert zones[0]["covering_radius_km"] == 1.2
        assert zones[0]["rightmove_id"] == "OUTCODE^1862"
        conn.close()

def test_update_zone():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        zone_id = insert_zone(conn, "Old Name", SAMPLE_GEOMETRY,
                              centroid_lat=51.545, centroid_lng=-0.18,
                              covering_radius_km=1.2,
                              rightmove_id="OUTCODE^1862",
                              openrent_term="NW6",
                              color_index=0)
        new_geom = SAMPLE_GEOMETRY.replace("51.54", "51.55")
        update_zone(conn, zone_id, name="New Name", geometry=new_geom,
                    centroid_lat=51.55, centroid_lng=-0.18,
                    covering_radius_km=1.5,
                    rightmove_id="OUTCODE^1862",
                    openrent_term="NW6")
        zones = get_zones(conn)
        assert zones[0]["name"] == "New Name"
        assert zones[0]["covering_radius_km"] == 1.5
        conn.close()

def test_delete_zone():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        zone_id = insert_zone(conn, "Test", SAMPLE_GEOMETRY,
                              centroid_lat=51.545, centroid_lng=-0.18,
                              covering_radius_km=1.2,
                              rightmove_id="OUTCODE^1862",
                              openrent_term="NW6",
                              color_index=0)
        delete_zone(conn, zone_id)
        assert len(get_zones(conn)) == 0
        conn.close()
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_models.py::test_init_db_creates_zones_table -v`
Expected: FAIL with ImportError (get_zones not defined)

**Step 3: Implement zones schema and CRUD in shared/models.py**

Add after `POI_COMMUTES_SCHEMA` (line 58):

```python
ZONES_SCHEMA = """
CREATE TABLE IF NOT EXISTS zones (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    geometry            TEXT NOT NULL,
    centroid_lat        REAL NOT NULL,
    centroid_lng        REAL NOT NULL,
    covering_radius_km  REAL NOT NULL,
    rightmove_id        TEXT,
    openrent_term       TEXT,
    color_index         INTEGER NOT NULL,
    created_at          TEXT NOT NULL
);
"""
```

Add `conn.execute(ZONES_SCHEMA)` to `init_db()` after the POI_COMMUTES line (after line 66).

Add CRUD functions after the POI helpers section:

```python
# --- Zone helpers ---

def get_zones(conn: sqlite3.Connection) -> list[dict]:
    """Return all zones ordered by id."""
    rows = conn.execute("SELECT * FROM zones ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def insert_zone(conn: sqlite3.Connection, name: str, geometry: str,
                centroid_lat: float, centroid_lng: float,
                covering_radius_km: float,
                rightmove_id: str | None, openrent_term: str | None,
                color_index: int) -> int:
    """Insert a new zone and return its id."""
    created_at = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        """INSERT INTO zones (name, geometry, centroid_lat, centroid_lng,
           covering_radius_km, rightmove_id, openrent_term, color_index, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (name, geometry, centroid_lat, centroid_lng,
         covering_radius_km, rightmove_id, openrent_term, color_index, created_at),
    )
    conn.commit()
    return cursor.lastrowid


def update_zone(conn: sqlite3.Connection, zone_id: int, **kwargs) -> None:
    """Update zone fields. Pass only the fields to update."""
    allowed = {"name", "geometry", "centroid_lat", "centroid_lng",
               "covering_radius_km", "rightmove_id", "openrent_term"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE zones SET {set_clause} WHERE id = ?",
                 [*fields.values(), zone_id])
    conn.commit()


def delete_zone(conn: sqlite3.Connection, zone_id: int) -> None:
    """Delete a zone."""
    conn.execute("DELETE FROM zones WHERE id = ?", (zone_id,))
    conn.commit()
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add shared/models.py tests/test_models.py
git commit -m "feat: zones table schema and CRUD helpers"
```

---

### Task 2: Zone Resolution Service (postcodes.io + Rightmove LOS)

**Files:**
- Create: `shared/zones.py`
- Test: `tests/test_zone_resolution.py`
- Modify: `scraper/requirements.txt` (add shapely)
- Modify: `ui/requirements.txt` (add shapely)

**Step 1: Write failing tests for zone resolution**

Create `tests/test_zone_resolution.py`:

```python
import json
import pytest
from unittest.mock import patch, MagicMock
from shared.zones import compute_zone_params, resolve_rightmove_id, resolve_postcode

SQUARE_POLYGON = {
    "type": "Polygon",
    "coordinates": [[
        [-0.19, 51.54], [-0.17, 51.54],
        [-0.17, 51.56], [-0.19, 51.56],
        [-0.19, 51.54]
    ]]
}


def test_compute_zone_params_centroid():
    """Centroid of a square polygon should be its center."""
    params = compute_zone_params(SQUARE_POLYGON)
    assert abs(params["centroid_lat"] - 51.55) < 0.01
    assert abs(params["centroid_lng"] - (-0.18)) < 0.01


def test_compute_zone_params_covering_radius():
    """Covering radius should be > 0 and enclose the polygon."""
    params = compute_zone_params(SQUARE_POLYGON)
    assert params["covering_radius_km"] > 0
    # Square with ~2km sides should have radius ~1.4km
    assert params["covering_radius_km"] < 3.0


def test_compute_zone_params_validates_polygon():
    """Should raise ValueError for invalid geometry."""
    with pytest.raises(ValueError):
        compute_zone_params({"type": "Point", "coordinates": [0, 0]})


def test_point_in_polygon():
    from shared.zones import point_in_zone
    geom_str = json.dumps(SQUARE_POLYGON)
    # Center point -- inside
    assert point_in_zone(51.55, -0.18, geom_str) is True
    # Way outside
    assert point_in_zone(52.0, -0.18, geom_str) is False


@patch("shared.zones.requests.get")
def test_resolve_postcode(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "status": 200,
        "result": [{"outcode": "NW6", "postcode": "NW6 1NB"}]
    }
    mock_get.return_value = mock_resp
    result = resolve_postcode(51.545, -0.18)
    assert result == "NW6"
    mock_get.assert_called_once()


@patch("shared.zones.requests.get")
def test_resolve_postcode_returns_none_on_failure(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"status": 200, "result": []}
    mock_get.return_value = mock_resp
    result = resolve_postcode(51.545, -0.18)
    assert result is None


@patch("shared.zones.requests.get")
def test_resolve_rightmove_id(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "matches": [{"id": "1862", "type": "OUTCODE", "displayName": "NW6"}]
    }
    mock_get.return_value = mock_resp
    result = resolve_rightmove_id("NW6")
    assert result == "OUTCODE^1862"


@patch("shared.zones.requests.get")
def test_resolve_rightmove_id_returns_none_on_empty(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"matches": []}
    mock_get.return_value = mock_resp
    result = resolve_rightmove_id("ZZZZZ")
    assert result is None
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_zone_resolution.py::test_compute_zone_params_centroid -v`
Expected: FAIL with ModuleNotFoundError (shared.zones)

**Step 3: Install Shapely**

Run: `.venv/bin/pip install shapely`

Add `shapely>=2.0` to both `scraper/requirements.txt` and `ui/requirements.txt`.

**Step 4: Implement shared/zones.py**

Create `shared/zones.py`:

```python
"""Zone geometry utilities: centroid, covering radius, point-in-polygon, external lookups."""
import json
import logging
import math

import requests
from shapely.geometry import shape, Point, mapping

log = logging.getLogger("flat-finder")


def compute_zone_params(geometry: dict) -> dict:
    """Compute centroid and covering radius from a GeoJSON Geometry dict.

    Returns dict with centroid_lat, centroid_lng, covering_radius_km.
    Raises ValueError if geometry is not a valid Polygon.
    """
    geom = shape(geometry)
    if geom.geom_type != "Polygon":
        raise ValueError(f"Expected Polygon, got {geom.geom_type}")
    if not geom.is_valid:
        raise ValueError("Invalid polygon geometry")
    centroid = geom.centroid
    # Covering radius: max distance from centroid to any vertex, in km
    max_dist_deg = 0.0
    for coord in geom.exterior.coords:
        d = math.sqrt((coord[0] - centroid.x) ** 2 + (coord[1] - centroid.y) ** 2)
        if d > max_dist_deg:
            max_dist_deg = d
    # Convert degrees to km (approximate, latitude-dependent)
    lat_rad = math.radians(centroid.y)
    km_per_deg_lat = 111.32
    km_per_deg_lng = 111.32 * math.cos(lat_rad)
    # Use average of lat/lng scale for rough conversion
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
        if resp.status_code != 200:
            return None
        results = resp.json().get("result", [])
        if not results:
            return None
        return results[0].get("outcode")
    except Exception as e:
        log.warning(f"postcodes.io lookup failed: {e}")
        return None


def resolve_rightmove_id(query: str) -> str | None:
    """Look up a Rightmove locationIdentifier via the LOS typeahead API."""
    try:
        resp = requests.get(
            "https://los.rightmove.co.uk/typeahead",
            params={"query": query},
            timeout=10,
        )
        if resp.status_code != 200:
            return None
        matches = resp.json().get("matches", [])
        if not matches:
            return None
        m = matches[0]
        return f"{m['type']}^{m['id']}"
    except Exception as e:
        log.warning(f"Rightmove LOS lookup failed: {e}")
        return None


def generate_circle_polygon(lat: float, lng: float, radius_km: float, n_vertices: int = 32) -> dict:
    """Generate a circular polygon as GeoJSON Geometry from center + radius.

    Used for migrating legacy circular zones from zones.json.
    """
    coords = []
    for i in range(n_vertices):
        angle = 2 * math.pi * i / n_vertices
        # Approximate offset in degrees
        dlat = (radius_km / 111.32) * math.sin(angle)
        dlng = (radius_km / (111.32 * math.cos(math.radians(lat)))) * math.cos(angle)
        coords.append([lng + dlng, lat + dlat])
    coords.append(coords[0])  # Close the ring
    return {"type": "Polygon", "coordinates": [coords]}
```

**Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_zone_resolution.py -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add shared/zones.py tests/test_zone_resolution.py scraper/requirements.txt ui/requirements.txt
git commit -m "feat: zone resolution service with Shapely, postcodes.io, Rightmove LOS"
```

---

### Task 3: Zones.json Migration

**Files:**
- Modify: `shared/models.py` (add migration call in `init_db`)
- Create: `shared/zones_migration.py`
- Test: `tests/test_zone_migration.py`

**Step 1: Write failing tests for migration**

Create `tests/test_zone_migration.py`:

```python
import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
from shared.models import init_db, get_connection, get_zones


def _write_zones_json(path: Path, zones: list[dict]):
    with open(path, "w") as f:
        json.dump(zones, f)


LEGACY_ZONES = [
    {
        "name": "Finchley Road",
        "rightmove_id": "STATION^3509",
        "openrent_term": "Finchley Road Station",
        "radius_miles": 1.0,
        "lat": 51.5472,
        "lng": -0.1803,
    },
    {
        "name": "St John's Wood",
        "rightmove_id": "STATION^8627",
        "openrent_term": "St John's Wood Station",
        "radius_miles": 0.75,
        "lat": 51.5347,
        "lng": -0.1743,
    },
]


def test_migration_imports_zones_from_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        zones_path = Path(tmpdir) / "zones.json"
        _write_zones_json(zones_path, LEGACY_ZONES)
        with patch("shared.models.ZONES_FILE", zones_path):
            init_db(db_path)
        conn = get_connection(db_path)
        zones = get_zones(conn)
        conn.close()
        assert len(zones) == 2
        assert zones[0]["name"] == "Finchley Road"
        assert zones[0]["rightmove_id"] == "STATION^3509"
        assert zones[0]["openrent_term"] == "Finchley Road Station"
        # Should have a valid polygon
        geom = json.loads(zones[0]["geometry"])
        assert geom["type"] == "Polygon"
        assert len(geom["coordinates"][0]) == 33  # 32 vertices + closing


def test_migration_is_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        zones_path = Path(tmpdir) / "zones.json"
        _write_zones_json(zones_path, LEGACY_ZONES)
        with patch("shared.models.ZONES_FILE", zones_path):
            init_db(db_path)
            init_db(db_path)  # Second call
        conn = get_connection(db_path)
        zones = get_zones(conn)
        conn.close()
        assert len(zones) == 2  # Not 4


def test_migration_skips_when_no_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("shared.models.ZONES_FILE", Path(tmpdir) / "nonexistent.json"):
            init_db(db_path)
        conn = get_connection(db_path)
        zones = get_zones(conn)
        conn.close()
        assert len(zones) == 0
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_zone_migration.py::test_migration_imports_zones_from_json -v`
Expected: FAIL (no migration logic yet)

**Step 3: Implement migration**

Add to `shared/models.py`, import at top:

```python
from shared.config import ZONES_FILE
```

Add migration function after `_migrate_legacy_commutes`:

```python
def _migrate_legacy_zones(conn: sqlite3.Connection) -> None:
    """Import zones from zones.json into DB if zones table is empty. Idempotent."""
    count = conn.execute("SELECT COUNT(*) FROM zones").fetchone()[0]
    if count > 0:
        return
    if not ZONES_FILE.exists():
        return
    import json as _json
    from shared.zones import generate_circle_polygon
    with open(ZONES_FILE) as f:
        legacy_zones = _json.load(f)
    now = datetime.now(timezone.utc).isoformat()
    for i, z in enumerate(legacy_zones):
        radius_km = z["radius_miles"] * 1.60934
        geom = generate_circle_polygon(z["lat"], z["lng"], radius_km)
        conn.execute(
            """INSERT INTO zones (name, geometry, centroid_lat, centroid_lng,
               covering_radius_km, rightmove_id, openrent_term, color_index, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (z["name"], _json.dumps(geom), z["lat"], z["lng"],
             round(radius_km, 2), z.get("rightmove_id"), z.get("openrent_term"),
             i % 8, now),
        )
```

Call it in `init_db()` after the ZONES_SCHEMA execute and after `_migrate_legacy_commutes`:

```python
_migrate_legacy_zones(conn)
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_zone_migration.py -v`
Expected: All PASS

**Step 5: Also run existing tests to check nothing broke**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add shared/models.py tests/test_zone_migration.py
git commit -m "feat: migrate legacy zones.json into zones DB table"
```

---

### Task 4: Scraper -- Load Zones from DB + Post-Filter

**Files:**
- Modify: `scraper/scraper.py`
- Modify: `shared/config.py`
- Test: `tests/test_scraper.py`

**Step 1: Write failing tests for post-filtering**

Add to `tests/test_scraper.py`:

```python
import json
from scraper.scraper import _filter_listings_by_zone


ZONE_GEOM = json.dumps({
    "type": "Polygon",
    "coordinates": [[
        [-0.19, 51.54], [-0.17, 51.54],
        [-0.17, 51.56], [-0.19, 51.56],
        [-0.19, 51.54]
    ]]
})


def test_filter_listings_keeps_inside():
    listings = [_make_listing("rm_1")]
    listings[0]["latitude"] = 51.55
    listings[0]["longitude"] = -0.18
    zone = {"geometry": ZONE_GEOM}
    result = _filter_listings_by_zone(listings, zone)
    assert len(result) == 1


def test_filter_listings_removes_outside():
    listings = [_make_listing("rm_1")]
    listings[0]["latitude"] = 52.0  # Way outside
    listings[0]["longitude"] = -0.18
    zone = {"geometry": ZONE_GEOM}
    result = _filter_listings_by_zone(listings, zone)
    assert len(result) == 0


def test_filter_listings_keeps_no_coordinates():
    listings = [_make_listing("rm_1")]
    listings[0]["latitude"] = None
    listings[0]["longitude"] = None
    zone = {"geometry": ZONE_GEOM}
    result = _filter_listings_by_zone(listings, zone)
    assert len(result) == 1  # Kept because no coords to check
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_scraper.py::test_filter_listings_keeps_inside -v`
Expected: FAIL with ImportError

**Step 3: Implement post-filter and DB zone loading**

Add to `scraper/scraper.py` imports:

```python
from shared.zones import point_in_zone
from shared.models import get_zones
```

Add filter function:

```python
def _filter_listings_by_zone(listings: list[dict], zone: dict) -> list[dict]:
    """Keep only listings inside the zone polygon. Keep those without coords."""
    geom_str = zone.get("geometry")
    if not geom_str:
        return listings
    return [
        l for l in listings
        if not (l.get("latitude") and l.get("longitude"))
        or point_in_zone(l["latitude"], l["longitude"], geom_str)
    ]
```

Modify `run()` function:

1. Replace `zones = load_zones()` (line 86) with:
```python
zones = get_zones(conn)
if not zones:
    # Fallback: try loading from legacy config
    from shared.config import load_zones as load_zones_legacy
    zones = load_zones_legacy()
```

2. Update the scraper loop to use DB zone fields. In the zone loop (lines 92-121), change the fetch calls:
```python
for zone in zones:
    # DB zones use covering_radius_km; legacy zones use radius_miles
    rm_radius = zone.get("covering_radius_km", zone.get("radius_miles", 1.0))
    if "covering_radius_km" in zone:
        rm_radius = rm_radius / 1.60934  # Convert km to miles for Rightmove
    or_radius = zone.get("covering_radius_km", zone.get("radius_miles", 1.0))

    rm_listings, rm_error = _scrape_source(
        f"rightmove/{zone['name']}",
        lambda z=zone, r=rm_radius: fetch_rightmove(
            z.get("rightmove_id", ""), r,
            MIN_BEDROOMS, MAX_BEDROOMS, MAX_RENT_PCM),
        conn,
    )
    or_listings, or_error = _scrape_source(
        f"openrent/{zone['name']}",
        lambda z=zone, r=or_radius: fetch_openrent(
            z.get("openrent_term", ""), r,
            MIN_BEDROOMS, MAX_BEDROOMS, MAX_RENT_PCM),
        conn,
    )

    _handle_failure_state(conn, f"rightmove/{zone['name']}", rm_error)
    _handle_failure_state(conn, f"openrent/{zone['name']}", or_error)

    # Post-filter by polygon
    combined = _filter_listings_by_zone(rm_listings + or_listings, zone)
```

3. Then continue with the existing dedup logic using `combined` instead of `rm_listings + or_listings`.

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_scraper.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add scraper/scraper.py tests/test_scraper.py
git commit -m "feat: scraper loads zones from DB with polygon post-filtering"
```

---

### Task 5: Zone API Endpoints in UI

**Files:**
- Modify: `ui/main.py`
- Test: `tests/test_ui.py`

**Step 1: Write failing tests for zone API**

Add to `tests/test_ui.py`:

```python
import json
from shared.models import get_zones, insert_zone

SAMPLE_GEOMETRY = {"type":"Polygon","coordinates":[[[-0.19,51.54],[-0.17,51.54],[-0.17,51.55],[-0.19,51.55],[-0.19,51.54]]]}


def test_api_get_zones_empty():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)
        resp = client.get("/api/zones")
        assert resp.status_code == 200
        assert resp.json() == []


def test_api_create_zone():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)
        with patch("ui.main.resolve_postcode", return_value="NW6"), \
             patch("ui.main.resolve_rightmove_id", return_value="OUTCODE^1862"):
            resp = client.post("/api/zones", json={
                "name": "Test Zone",
                "geometry": SAMPLE_GEOMETRY,
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Zone"
        assert data["rightmove_id"] == "OUTCODE^1862"
        assert data["openrent_term"] == "NW6"
        # Verify stored
        conn = get_connection(db_path)
        zones = get_zones(conn)
        conn.close()
        assert len(zones) == 1


def test_api_delete_zone():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        conn = get_connection(db_path)
        zone_id = insert_zone(conn, "Test", json.dumps(SAMPLE_GEOMETRY),
                              centroid_lat=51.545, centroid_lng=-0.18,
                              covering_radius_km=1.2,
                              rightmove_id="OUTCODE^1862",
                              openrent_term="NW6",
                              color_index=0)
        conn.close()
        client = _make_app(db_path)
        resp = client.delete(f"/api/zones/{zone_id}")
        assert resp.status_code == 200
        conn = get_connection(db_path)
        zones = get_zones(conn)
        conn.close()
        assert len(zones) == 0


def test_api_update_zone():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        conn = get_connection(db_path)
        zone_id = insert_zone(conn, "Old", json.dumps(SAMPLE_GEOMETRY),
                              centroid_lat=51.545, centroid_lng=-0.18,
                              covering_radius_km=1.2,
                              rightmove_id="OUTCODE^1862",
                              openrent_term="NW6",
                              color_index=0)
        conn.close()
        client = _make_app(db_path)
        new_geom = dict(SAMPLE_GEOMETRY)
        with patch("ui.main.resolve_postcode", return_value="NW6"), \
             patch("ui.main.resolve_rightmove_id", return_value="OUTCODE^1862"):
            resp = client.put(f"/api/zones/{zone_id}", json={
                "name": "Updated",
                "geometry": new_geom,
            })
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
```

**Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ui.py::test_api_get_zones_empty -v`
Expected: FAIL (404 -- route doesn't exist)

**Step 3: Implement zone API endpoints in ui/main.py**

Add imports to top of `ui/main.py`:

```python
from shared.models import get_zones, insert_zone, update_zone, delete_zone
from shared.zones import compute_zone_params, resolve_postcode, resolve_rightmove_id
```

Add API routes after existing API routes:

```python
# --- Zone API routes ---

@app.get("/api/zones")
def api_zones():
    conn = get_connection(UI_DB_PATH)
    zones = get_zones(conn)
    conn.close()
    for z in zones:
        z["color"] = POI_COLORS[z["color_index"] % len(POI_COLORS)]
    return zones


@app.post("/api/zones")
def api_create_zone(body: dict):
    geometry = body.get("geometry")
    name = body.get("name", "").strip()
    if not geometry or not name:
        raise HTTPException(400, "name and geometry required")
    params = compute_zone_params(geometry)
    postcode = resolve_postcode(params["centroid_lat"], params["centroid_lng"])
    rightmove_id = resolve_rightmove_id(postcode) if postcode else None
    conn = get_connection(UI_DB_PATH)
    existing_zones = get_zones(conn)
    color_index = len(existing_zones) % len(POI_COLORS)
    import json as _json
    zone_id = insert_zone(
        conn, name, _json.dumps(geometry),
        centroid_lat=params["centroid_lat"],
        centroid_lng=params["centroid_lng"],
        covering_radius_km=params["covering_radius_km"],
        rightmove_id=rightmove_id,
        openrent_term=postcode,
        color_index=color_index,
    )
    zones = get_zones(conn)
    zone = next(z for z in zones if z["id"] == zone_id)
    conn.close()
    zone["color"] = POI_COLORS[zone["color_index"] % len(POI_COLORS)]
    return zone


@app.put("/api/zones/{zone_id}")
def api_update_zone(zone_id: int, body: dict):
    geometry = body.get("geometry")
    name = body.get("name", "").strip()
    if not geometry or not name:
        raise HTTPException(400, "name and geometry required")
    params = compute_zone_params(geometry)
    postcode = resolve_postcode(params["centroid_lat"], params["centroid_lng"])
    rightmove_id = resolve_rightmove_id(postcode) if postcode else None
    import json as _json
    conn = get_connection(UI_DB_PATH)
    update_zone(conn, zone_id,
                name=name, geometry=_json.dumps(geometry),
                centroid_lat=params["centroid_lat"],
                centroid_lng=params["centroid_lng"],
                covering_radius_km=params["covering_radius_km"],
                rightmove_id=rightmove_id,
                openrent_term=postcode)
    zones = get_zones(conn)
    zone = next((z for z in zones if z["id"] == zone_id), None)
    conn.close()
    if not zone:
        raise HTTPException(404, "Zone not found")
    zone["color"] = POI_COLORS[zone["color_index"] % len(POI_COLORS)]
    return zone


@app.delete("/api/zones/{zone_id}")
def api_delete_zone(zone_id: int):
    conn = get_connection(UI_DB_PATH)
    delete_zone(conn, zone_id)
    conn.close()
    return {"ok": True}
```

**Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ui.py -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add ui/main.py tests/test_ui.py
git commit -m "feat: zone CRUD API endpoints"
```

---

### Task 6: Settings UI -- Zone Drawing Panel

**Files:**
- Modify: `ui/templates/settings.html`
- Modify: `ui/static/v2.css`
- Modify: `ui/static/v2.js`
- Modify: `ui/main.py` (settings_page route to pass zones)

**Skill:** Use `frontend-design` skill for this task -- the zone drawing panel, zone list with inline map previews, and overall integration with the existing warm minimal aesthetic.

**Step 1: Update settings_page route to pass zones**

In `ui/main.py`, modify the `settings_page` function to also load zones:

```python
@app.get("/settings", response_class=HTMLResponse, name="settings_page")
def settings_page(request: Request):
    conn = get_connection(UI_DB_PATH)
    pois = get_pois(conn)
    zones = get_zones(conn)
    conn.close()
    for poi in pois:
        poi["color"] = POI_COLORS[poi["color_index"] % len(POI_COLORS)]
    for zone in zones:
        zone["color"] = POI_COLORS[zone["color_index"] % len(POI_COLORS)]
    return templates.TemplateResponse(request, "settings.html", {"pois": pois, "zones": zones})
```

**Step 2: Add zone section to settings.html**

Below the POI section in `ui/templates/settings.html`, add a "Search Zones" section with:
- Zone list (color swatch, name, vertex count, resolved search info, delete button, inline map preview)
- "Add Zone" button that expands a map panel
- Map panel with Leaflet + Leaflet-Geoman for polygon drawing
- Name input + Save button
- Include Leaflet and Leaflet-Geoman CSS/JS from CDN in the `{% block head %}` section

Leaflet-Geoman CDN:
```html
<link rel="stylesheet" href="https://unpkg.com/@geoman-io/leaflet-geoman-free@2.18.4/dist/leaflet-geoman.css" />
<script src="https://unpkg.com/@geoman-io/leaflet-geoman-free@2.18.4/dist/leaflet-geoman.min.js"></script>
```

**Step 3: Add CSS for zone panel**

Add to `ui/static/v2.css`:
- `.settings__zone` styles matching `.settings__poi` pattern
- `.zone-map-panel` -- full-width map container, collapsible
- `.zone-map` -- the Leaflet map div (height ~400px)
- Zone inline previews (small static maps ~100x60px)

**Step 4: Add JS for zone CRUD**

Add to `ui/static/v2.js` (or inline in settings.html):
- Leaflet-Geoman initialization on the drawing map
- `pm:create` handler to capture polygon GeoJSON
- Save handler: POST `/flat/api/zones` with name + geometry
- Delete handler: DELETE `/flat/api/zones/{id}`
- Edit handler: click zone -> open map with existing polygon in edit mode
- On save with existing zone: PUT `/flat/api/zones/{id}`

**Step 5: Test with Playwright**

Use `playwright-skill` to verify:
- Settings page loads with zone section visible
- "Add Zone" expands the map panel
- Drawing tools are visible on the map
- Existing zones render in the list

**Step 6: Commit**

```bash
git add ui/templates/settings.html ui/static/v2.css ui/static/v2.js ui/main.py
git commit -m "feat: zone drawing UI on Settings page with Leaflet-Geoman"
```

---

### Task 7: Map View -- Zone Polygon Overlays

**Files:**
- Modify: `ui/templates/map.html`
- Modify: `ui/static/map.js`

**Skill:** Use `frontend-design` skill for overlay styling.

**Step 1: Add zone overlay toggle to map.html**

Add a "Zones" toggle button to the `.map-filters` div:
```html
<button id="filter-zones" class="active" onclick="toggleZones()">Zones</button>
```

**Step 2: Update map.js to fetch and render zones**

Add to `ui/static/map.js`:

```javascript
// --- Zone overlays ---
var zoneLayer = L.layerGroup().addTo(map);
var zonesVisible = true;

fetch("/flat/api/zones")
    .then(function (resp) { return resp.json(); })
    .then(function (zones) {
        zones.forEach(function (zone) {
            var geojson = JSON.parse(zone.geometry);
            var color = zone.color ? zone.color.color : "#0f766e";
            var layer = L.geoJSON(geojson, {
                style: {
                    color: color,
                    weight: 2,
                    fillColor: color,
                    fillOpacity: 0.12,
                },
            });
            // Label at centroid
            layer.bindTooltip(zone.name, {
                permanent: true,
                direction: "center",
                className: "zone-label",
            });
            zoneLayer.addLayer(layer);
        });
    });

window.toggleZones = function () {
    zonesVisible = !zonesVisible;
    if (zonesVisible) {
        map.addLayer(zoneLayer);
        document.getElementById("filter-zones").classList.add("active");
    } else {
        map.removeLayer(zoneLayer);
        document.getElementById("filter-zones").classList.remove("active");
    }
};
```

**Step 3: Add zone-label CSS to map.html**

```css
.zone-label {
    background: transparent;
    border: none;
    box-shadow: none;
    font-family: 'DM Sans', sans-serif;
    font-size: 12px;
    font-weight: 600;
    color: #666;
}
```

**Step 4: Test with Playwright**

Use `playwright-skill` to verify:
- Map page loads with zone polygons visible
- Zone toggle button hides/shows polygons
- Listing pins render on top of zone overlays

**Step 5: Commit**

```bash
git add ui/templates/map.html ui/static/map.js
git commit -m "feat: zone polygon overlays on listings map"
```

---

### Task 8: Docker Compose + Cleanup

**Files:**
- Modify: `docker-compose.yml` (remove zones.json mount)
- Modify: `shared/config.py` (remove legacy load_zones or keep as fallback)

**Step 1: Remove zones.json volume mount from docker-compose.yml**

Remove line 24 from `docker-compose.yml`:
```yaml
      - /opt/mediastack/config/flat-finder/zones.json:/app/config/zones.json:ro
```

**Step 2: Clean up shared/config.py**

Remove `load_zones()` function and `ZONES_FILE` constant since zones now come from the DB. Keep `ZONES_FILE` only as a reference for the migration (it's imported in `shared/models.py`).

Actually, keep `ZONES_FILE` for migration purposes but remove `load_zones()`:

```python
# Zones (legacy -- used only for migration)
ZONES_FILE = Path(get_env("ZONES_FILE", "/app/config/zones.json"))
```

Remove the `load_zones` function (lines 26-39) and its `import json` if no longer needed.

**Step 3: Update scraper imports**

In `scraper/scraper.py`, remove `load_zones` from the config import line.

**Step 4: Update test_zones.py**

Remove or update `tests/test_zones.py` since `load_zones()` no longer exists. These tests are replaced by `test_zone_migration.py`.

**Step 5: Run all tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All PASS

**Step 6: Commit**

```bash
git add docker-compose.yml shared/config.py scraper/scraper.py tests/test_zones.py
git commit -m "chore: remove zones.json mount, clean up legacy zone loading"
```

---

### Task 9: Fix OpenRent Radius Bug

**Files:**
- Modify: `scraper/openrent.py`
- Test: `tests/test_openrent.py`

**Step 1: Write test for radius conversion**

Add to `tests/test_openrent.py`:

```python
def test_build_search_url_uses_km():
    url = build_search_url("NW6", 2.0, 1, 2, 2200)
    assert "within=2" in url  # Should pass km directly, not convert
```

**Step 2: Rename parameter from `radius_miles` to `radius_km`**

In `scraper/openrent.py`, rename the parameter in `build_search_url` (line 14) and `fetch_openrent` (line 195) from `radius_miles` to `radius_km`. The `within` parameter already passes the value directly, so no conversion needed -- the rename just corrects the documentation.

**Step 3: Update scraper.py call site**

In the zone loop in `scraper/scraper.py`, ensure OpenRent receives km (which it already will from `covering_radius_km`).

**Step 4: Run tests**

Run: `.venv/bin/python -m pytest tests/ -v`
Expected: All PASS

**Step 5: Commit**

```bash
git add scraper/openrent.py scraper/scraper.py tests/test_openrent.py
git commit -m "fix: rename OpenRent radius param to km (was mislabeled as miles)"
```

---

### Task 10: End-to-End Verification

**Step 1: Rebuild and test locally**

Run: `docker compose up -d --build`

**Step 2: Verify migration**

Check scraper logs for zone migration message:
Run: `docker logs flat-finder-scraper 2>&1 | head -20`

**Step 3: Verify Settings UI**

Use `playwright-skill`:
- Navigate to `/flat/settings`
- Verify zone section is visible with migrated zones
- Test adding a new zone via drawing
- Test deleting a zone

**Step 4: Verify Map overlays**

Use `playwright-skill`:
- Navigate to `/flat/map`
- Verify zone polygons are visible
- Test the toggle button

**Step 5: Verify scraper post-filtering**

Check scraper logs for post-filter messages after next scrape cycle:
Run: `docker logs flat-finder-scraper --since 5m`

**Step 6: Final commit if any fixups needed**

```bash
git add -A
git commit -m "fix: end-to-end verification fixes"
```
