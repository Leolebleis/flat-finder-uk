import importlib
import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import shared.config
import ui.main
from fastapi.testclient import TestClient
from shared.models import (
    get_connection,
    get_pois,
    get_zones,
    init_db,
    insert_listing,
    insert_poi,
    insert_zone,
    upsert_poi_commute,
)

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

SAMPLE_LISTING = {
    "id": "rightmove_1",
    "source": "rightmove",
    "url": "https://example.com",
    "title": "1 bed flat",
    "price_pcm": 1800,
    "bedrooms": 1,
    "address": "NW6",
    "latitude": 51.54,
    "longitude": -0.17,
    "description": "Nice flat",
    "image_url": None,
    "property_type": "flat",
    "furnishing": "Furnished",
    "sqft": None,
    "has_dishwasher": "unknown",
    "has_washer": "unknown",
    "has_outdoor": "unknown",
    "outdoor_type": None,
    "first_seen": "2026-02-26T12:00:00+00:00",
    "listing_date": None,
}


def _make_app(db_path: Path):
    """Create a test client for the UI app with a temporary DB."""
    os.environ["FLAT_FINDER_UI_DB"] = str(db_path)
    importlib.reload(shared.config)
    importlib.reload(ui.main)
    return TestClient(ui.main.app)


def _setup_db(db_path: Path):
    """Init listings + user_state tables."""
    init_db(db_path)
    conn = get_connection(db_path)
    conn.execute(USER_STATE_SCHEMA)
    conn.commit()
    conn.close()


def _seed_listing(db_path: Path, listing: dict | None = None, gym_commute_mins: int | None = None):
    data = listing or dict(SAMPLE_LISTING)
    if gym_commute_mins is not None:
        data = {**data, "gym_commute_mins": gym_commute_mins}
    conn = get_connection(db_path)
    insert_listing(conn, data)
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
        row = conn.execute("SELECT * FROM user_state WHERE listing_id = ?", ("rightmove_1",)).fetchone()
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
        row = conn.execute("SELECT notes FROM user_state WHERE listing_id = ?", ("rightmove_1",)).fetchone()
        conn.close()
        assert row["notes"] == "Nice area"


def test_update_state_multiple_fields():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)

        resp = client.post("/api/state/rightmove_1", json={"seen": True, "favourite": True, "notes": "Great flat"})
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


def test_feed_page_shows_gym_commute():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path, gym_commute_mins=12)
        conn = get_connection(db_path)
        poi_id = insert_poi(conn, "Gym", 51.5445, -0.1762, 1)
        upsert_poi_commute(conn, "rightmove_1", poi_id, 12)
        conn.close()
        client = _make_app(db_path)

        resp = client.get("/")
        assert resp.status_code == 200
        assert "min to Gym" in resp.text


def test_feed_page_best_match_sort():
    """Best match sort should return listings sorted by combined score."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(
            db_path,
            {
                **SAMPLE_LISTING,
                "id": "close_gym",
                "latitude": 51.544,
                "longitude": -0.176,
                "commute_mins": 60,
            },
        )
        _seed_listing(
            db_path,
            {
                **SAMPLE_LISTING,
                "id": "short_commute",
                "latitude": 51.49,
                "longitude": -0.18,
                "commute_mins": 30,
            },
        )
        conn = get_connection(db_path)
        poi_id = insert_poi(conn, "Work", 51.4869, -0.1832, 0)
        upsert_poi_commute(conn, "close_gym", poi_id, 60)
        upsert_poi_commute(conn, "short_commute", poi_id, 30)
        conn.close()
        client = _make_app(db_path)

        resp = client.get("/?sort=best_match")
        assert resp.status_code == 200
        assert "score" in resp.text.lower()


def test_feed_page_best_match_sort_option_exists():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)

        resp = client.get("/")
        assert "best_match" in resp.text
        assert "Best match" in resp.text


def test_detail_page_404_for_missing():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        client = _make_app(db_path)

        resp = client.get("/listing/nonexistent")
        assert resp.status_code == 404


# --- Label override tests ---


def test_update_state_override_dishwasher():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)

        resp = client.post("/api/state/rightmove_1", json={"override_dishwasher": "yes"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["override_dishwasher"] == "yes"

        # Verify persisted
        conn = get_connection(db_path)
        row = conn.execute(
            "SELECT override_dishwasher FROM user_state WHERE listing_id = ?", ("rightmove_1",)
        ).fetchone()
        conn.close()
        assert row["override_dishwasher"] == "yes"


def test_update_state_override_clears_with_null():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        client = _make_app(db_path)

        client.post("/api/state/rightmove_1", json={"override_dishwasher": "yes"})
        resp = client.post("/api/state/rightmove_1", json={"override_dishwasher": None})
        assert resp.status_code == 200
        assert resp.json()["override_dishwasher"] is None


def test_feed_page_applies_overrides():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path, {**SAMPLE_LISTING, "has_dishwasher": "no"})
        client = _make_app(db_path)

        # Override dishwasher to yes
        client.post("/api/state/rightmove_1", json={"override_dishwasher": "yes"})

        resp = client.get("/")
        assert resp.status_code == 200
        assert "Dishwasher" in resp.text
        assert "No dishwasher" not in resp.text


# --- Settings page tests ---


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
        resp = client.post(
            "/settings/poi",
            data={"name": "Office", "maps_url": "https://www.google.com/maps/@51.4869,-0.1832,17z/"},
            follow_redirects=False,
        )
        assert resp.status_code == 303
        conn = get_connection(db_path)
        pois = get_pois(conn)
        conn.close()
        assert len(pois) == 1
        assert pois[0]["name"] == "Office"
        assert abs(pois[0]["lat"] - 51.4869) < 0.001
        assert abs(pois[0]["lng"] - (-0.1832)) < 0.001


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
        resp = client.post("/settings/poi", data={"name": "Bad", "maps_url": "not a url"}, follow_redirects=False)
        assert resp.status_code == 303
        conn = get_connection(db_path)
        pois = get_pois(conn)
        conn.close()
        assert len(pois) == 0


# --- Dynamic POI feed/detail tests ---


def test_feed_page_with_pois_shows_dynamic_metrics():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        conn = get_connection(db_path)
        poi_id = insert_poi(conn, "Rue's", 51.4869, -0.1832, 0)
        upsert_poi_commute(conn, "rightmove_1", poi_id, 35)
        conn.close()
        client = _make_app(db_path)
        resp = client.get("/")
        assert resp.status_code == 200
        assert "35 min to Rue" in resp.text
        assert "poi-weight-slider" in resp.text


def test_detail_page_with_pois_shows_dynamic_metrics():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        _seed_listing(db_path)
        conn = get_connection(db_path)
        poi_id = insert_poi(conn, "Office", 51.4869, -0.1832, 0)
        upsert_poi_commute(conn, "rightmove_1", poi_id, 22)
        conn.close()
        client = _make_app(db_path)
        resp = client.get("/listing/rightmove_1")
        assert resp.status_code == 200
        assert "22 min to Office" in resp.text


# --- Zone API tests ---

SAMPLE_GEOMETRY = {
    "type": "Polygon",
    "coordinates": [[[-0.19, 51.54], [-0.17, 51.54], [-0.17, 51.55], [-0.19, 51.55], [-0.19, 51.54]]],
}


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
        with (
            patch("ui.main.resolve_postcode", return_value="NW6"),
            patch("ui.main.resolve_rightmove_id", return_value="OUTCODE^1862"),
        ):
            resp = client.post(
                "/api/zones",
                json={
                    "name": "Test Zone",
                    "geometry": SAMPLE_GEOMETRY,
                },
            )
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Zone"
        assert data["rightmove_id"] == "OUTCODE^1862"
        assert data["openrent_term"] == "NW6"
        conn = get_connection(db_path)
        zones = get_zones(conn)
        conn.close()
        assert len(zones) == 1


def test_api_delete_zone():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        _setup_db(db_path)
        conn = get_connection(db_path)
        zone_id = insert_zone(
            conn,
            "Test",
            json.dumps(SAMPLE_GEOMETRY),
            centroid_lat=51.545,
            centroid_lng=-0.18,
            covering_radius_km=1.2,
            rightmove_id="OUTCODE^1862",
            openrent_term="NW6",
            color_index=0,
        )
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
        zone_id = insert_zone(
            conn,
            "Old",
            json.dumps(SAMPLE_GEOMETRY),
            centroid_lat=51.545,
            centroid_lng=-0.18,
            covering_radius_km=1.2,
            rightmove_id="OUTCODE^1862",
            openrent_term="NW6",
            color_index=0,
        )
        conn.close()
        client = _make_app(db_path)
        with (
            patch("ui.main.resolve_postcode", return_value="NW6"),
            patch("ui.main.resolve_rightmove_id", return_value="OUTCODE^1862"),
        ):
            resp = client.put(
                f"/api/zones/{zone_id}",
                json={
                    "name": "Updated",
                    "geometry": SAMPLE_GEOMETRY,
                },
            )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Updated"
