# tests/test_ui.py
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient
from shared.models import init_db, get_connection, insert_listing


USER_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS user_state (
    listing_id TEXT PRIMARY KEY,
    seen       BOOLEAN DEFAULT 0,
    favourite  BOOLEAN DEFAULT 0,
    notes      TEXT,
    updated_at DATETIME
);
"""

SAMPLE_LISTING = {
    "id": "rightmove_1", "source": "rightmove", "url": "https://example.com",
    "title": "1 bed flat", "price_pcm": 1800, "bedrooms": 1,
    "address": "NW6", "latitude": 51.54, "longitude": -0.17,
    "description": "Nice flat", "image_url": None, "property_type": "flat",
    "furnishing": "Furnished", "sqft": None, "has_dishwasher": "unknown",
    "has_washer": "unknown", "has_outdoor": "unknown", "outdoor_type": None,
    "first_seen": "2026-02-26T12:00:00+00:00", "listing_date": None,
}


def _make_app(db_path: Path):
    """Create a test client for the UI app with a temporary DB."""
    os.environ["FLAT_FINDER_UI_DB"] = str(db_path)
    import importlib
    import shared.config
    importlib.reload(shared.config)
    import ui.main
    importlib.reload(ui.main)
    return TestClient(ui.main.app)


def _setup_db(db_path: Path):
    """Init listings + user_state tables."""
    init_db(db_path)
    conn = get_connection(db_path)
    conn.execute(USER_STATE_SCHEMA)
    conn.commit()
    conn.close()


def _seed_listing(db_path: Path, listing: dict | None = None):
    conn = get_connection(db_path)
    insert_listing(conn, listing or SAMPLE_LISTING)
    conn.close()


# --- POST /api/state/{id} tests ---

def test_update_state_seen():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)

        resp = client.post("/api/state/rightmove_1", json={"seen": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["listing_id"] == "rightmove_1"
        assert data["seen"] is True
        assert data["favourite"] is False

        # Verify persisted
        conn = get_connection(db_path)
        row = conn.execute(
            "SELECT * FROM user_state WHERE listing_id = ?", ("rightmove_1",)
        ).fetchone()
        conn.close()
        assert row is not None
        assert row["seen"] == 1


def test_update_state_favourite():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)

        resp = client.post("/api/state/rightmove_1", json={"favourite": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["favourite"] is True


def test_update_state_notes():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)

        resp = client.post("/api/state/rightmove_1", json={"notes": "Nice area"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["notes"] == "Nice area"

        # Verify persisted
        conn = get_connection(db_path)
        row = conn.execute(
            "SELECT notes FROM user_state WHERE listing_id = ?", ("rightmove_1",)
        ).fetchone()
        conn.close()
        assert row["notes"] == "Nice area"


def test_update_state_multiple_fields():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)

        resp = client.post("/api/state/rightmove_1", json={
            "seen": True, "favourite": True, "notes": "Great flat"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["seen"] is True
        assert data["favourite"] is True
        assert data["notes"] == "Great flat"


def test_update_state_overwrites_previous():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)

        client.post("/api/state/rightmove_1", json={"notes": "First note"})
        resp = client.post("/api/state/rightmove_1", json={"notes": "Updated note"})
        assert resp.status_code == 200
        assert resp.json()["notes"] == "Updated note"


def test_update_state_nonexistent_listing():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)

        resp = client.post("/api/state/nonexistent_id", json={"seen": True})
        assert resp.status_code == 404


# --- GET /api/listings tests ---

def test_api_listings_returns_json():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)

        resp = client.get("/api/listings")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["id"] == "rightmove_1"
        assert data[0]["latitude"] == 51.54
        assert data[0]["longitude"] == -0.17


def test_api_listings_empty():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)

        resp = client.get("/api/listings")
        assert resp.status_code == 200
        assert resp.json() == []


def test_api_listings_includes_user_state():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)

        # Set some state first
        client.post("/api/state/rightmove_1", json={"seen": True, "favourite": True})

        resp = client.get("/api/listings")
        data = resp.json()
        assert data[0]["seen"] is True
        assert data[0]["favourite"] is True


# --- Template route smoke tests ---

def test_feed_page_returns_html():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)

        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


def test_map_page_returns_html():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)

        resp = client.get("/map")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


def test_detail_page_returns_html():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)

        resp = client.get("/listing/rightmove_1")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]


def test_detail_page_404_for_missing():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)

        resp = client.get("/listing/nonexistent")
        assert resp.status_code == 404
