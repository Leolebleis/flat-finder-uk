# tests/test_api.py
import tempfile
import os
from pathlib import Path
from fastapi.testclient import TestClient
from shared.models import init_db, get_connection, insert_listing

def _make_app(db_path: Path):
    os.environ["FLAT_FINDER_DB"] = str(db_path)
    os.environ["FLAT_FINDER_API_KEY"] = "test-key"
    import importlib
    import shared.config
    importlib.reload(shared.config)
    import api.main
    importlib.reload(api.main)
    return TestClient(api.main.app)

def _seed_listing(db_path, id="rightmove_1", price=1800):
    conn = get_connection(db_path)
    insert_listing(conn, {
        "id": id, "source": "rightmove", "url": "https://example.com",
        "title": "1 bed flat", "price_pcm": price, "bedrooms": 1,
        "address": "NW6", "latitude": 51.54, "longitude": -0.17,
        "description": "Nice flat", "image_url": None, "property_type": "flat",
        "furnishing": "Furnished", "sqft": None, "has_dishwasher": "unknown",
        "has_washer": "unknown", "has_outdoor": "unknown", "outdoor_type": None,
        "first_seen": "2026-02-26T12:00:00+00:00", "listing_date": None,
    })
    conn.close()

def test_listings_requires_api_key():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        client = _make_app(db_path)
        resp = client.get("/listings")
        assert resp.status_code == 401

def test_listings_returns_data_with_valid_key():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)
        resp = client.get("/listings", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["id"] == "rightmove_1"

def test_listings_since_filter():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)
        resp = client.get("/listings?since=2026-12-01T00:00:00", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        assert len(resp.json()) == 0

def test_stats_endpoint():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)
        resp = client.get("/stats", headers={"X-API-Key": "test-key"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_listings"] == 1
