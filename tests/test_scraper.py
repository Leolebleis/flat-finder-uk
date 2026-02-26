# tests/test_scraper.py
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from shared.models import init_db, get_connection, insert_listing, get_state, set_state
from scraper.scraper import process_new_listings, is_first_run

def _make_listing(id="rightmove_1", price=1800):
    return {
        "id": id, "source": "rightmove", "url": "https://example.com",
        "title": "1 bed flat", "price_pcm": price, "bedrooms": 1,
        "address": "NW6", "latitude": 51.54, "longitude": -0.17,
        "description": "Nice flat", "image_url": None, "property_type": "flat",
        "furnishing": "Furnished", "sqft": None, "has_dishwasher": "unknown",
        "has_washer": "unknown", "has_outdoor": "unknown", "outdoor_type": None,
        "zone": None, "commute_mins": None,
        "first_seen": "2026-02-26T12:00:00+00:00", "listing_date": None,
    }

def test_is_first_run_true_on_empty_db():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = get_connection(db_path)
        assert is_first_run(conn) is True
        conn.close()

def test_is_first_run_false_after_initialised():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = get_connection(db_path)
        set_state(conn, "initialised", "true")
        assert is_first_run(conn) is False
        conn.close()

def test_process_new_listings_returns_only_new():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = get_connection(db_path)
        existing = _make_listing("rightmove_1")
        insert_listing(conn, existing)
        fetched = [_make_listing("rightmove_1"), _make_listing("rightmove_2")]
        new = process_new_listings(conn, fetched)
        assert len(new) == 1
        assert new[0]["id"] == "rightmove_2"
        conn.close()

def test_process_new_listings_preserves_zone():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = get_connection(db_path)
        listing = _make_listing("rightmove_1")
        listing["zone"] = "St John's Wood"
        new = process_new_listings(conn, [listing])
        assert len(new) == 1
        row = conn.execute("SELECT zone FROM listings WHERE id = ?", ("rightmove_1",)).fetchone()
        assert row["zone"] == "St John's Wood"
        conn.close()
