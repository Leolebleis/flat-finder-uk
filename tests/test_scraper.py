# tests/test_scraper.py
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from shared.models import init_db, get_connection, insert_listing, get_state, set_state
from scraper.scraper import process_new_listings, is_first_run, _listing_fingerprint, _normalize_address

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


def test_normalize_address_strips_london_and_punctuation():
    assert _normalize_address("Goldhurst Terrace, London, NW6") == "goldhurst terrace nw6"
    assert _normalize_address("Goldhurst Terrace, NW6") == "goldhurst terrace nw6"


def test_listing_fingerprint_matches_cross_source():
    rm = _make_listing("rightmove_1")
    rm["address"] = "Goldhurst Terrace, London, NW6"
    rm["price_pcm"] = 2100
    rm["bedrooms"] = 1

    orr = _make_listing("openrent_1")
    orr["address"] = "Goldhurst Terrace, NW6"
    orr["price_pcm"] = 2100
    orr["bedrooms"] = 1

    assert _listing_fingerprint(rm) == _listing_fingerprint(orr)


def test_listing_fingerprint_differs_on_price():
    a = _make_listing("rm_1")
    a["address"] = "Goldhurst Terrace, NW6"
    a["price_pcm"] = 2100
    a["bedrooms"] = 1

    b = _make_listing("or_1")
    b["address"] = "Goldhurst Terrace, NW6"
    b["price_pcm"] = 1800
    b["bedrooms"] = 1

    assert _listing_fingerprint(a) != _listing_fingerprint(b)


def test_listing_fingerprint_none_when_missing_fields():
    l = _make_listing("rm_1")
    l["address"] = None
    assert _listing_fingerprint(l) is None
