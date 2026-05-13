import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from scraper.scraper import (
    _filter_listings_by_zone,
    _listing_fingerprint,
    _normalize_address,
    is_first_run,
    process_new_listings,
    run,
)
from shared.models import get_connection, init_db, insert_listing, insert_poi, insert_zone, set_state


def _make_listing(listing_id: str = "rightmove_1", price: int = 1800) -> dict:
    return {
        "id": listing_id,
        "source": "rightmove",
        "url": "https://example.com",
        "title": "1 bed flat",
        "price_pcm": price,
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
        "zone": None,
        "first_seen": datetime.now(UTC).isoformat(),
        "listing_date": None,
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
    listing = _make_listing("rm_1")
    listing["address"] = None
    assert _listing_fingerprint(listing) is None


def test_scraper_fetches_commutes_for_all_pois():
    """run() should fetch commute times for each POI in the DB."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = get_connection(db_path)

        poi_id = insert_poi(conn, "Test Place", 51.50, -0.12, 0)
        # Insert a zone that covers the listing location
        zone_geom = json.dumps(
            {
                "type": "Polygon",
                "coordinates": [[[-0.20, 51.50], [-0.10, 51.50], [-0.10, 51.60], [-0.20, 51.60], [-0.20, 51.50]]],
            }
        )
        insert_zone(
            conn,
            "Test Zone",
            zone_geom,
            centroid_lat=51.55,
            centroid_lng=-0.15,
            covering_radius_km=5.0,
            rightmove_id="X",
            openrent_term="X",
            color_index=0,
        )
        conn.close()
        listing = _make_listing("rm_new")
        listing["latitude"] = 51.54
        listing["longitude"] = -0.17
        with (
            patch("scraper.scraper.fetch_rightmove", return_value=[listing]),
            patch("scraper.scraper.fetch_openrent", return_value=[]),
            patch("scraper.scraper.tfl_journey_mins", return_value=25),
            patch("scraper.scraper.DB_PATH", db_path),
            patch("scraper.scraper.NTFY_TOPIC", ""),
            patch("scraper.scraper.GMAIL_ADDRESS", ""),
            patch("scraper.scraper.GMAIL_APP_PASSWORD", ""),
        ):
            run()
        conn = get_connection(db_path)
        commutes = conn.execute("SELECT * FROM poi_commutes WHERE listing_id = 'rm_new'").fetchall()
        conn.close()
        assert len(commutes) == 1
        assert commutes[0]["poi_id"] == poi_id
        assert commutes[0]["commute_mins"] == 25


ZONE_GEOM = json.dumps(
    {
        "type": "Polygon",
        "coordinates": [[[-0.19, 51.54], [-0.17, 51.54], [-0.17, 51.56], [-0.19, 51.56], [-0.19, 51.54]]],
    }
)


def test_filter_listings_keeps_inside():
    listings = [_make_listing("rm_1")]
    listings[0]["latitude"] = 51.55
    listings[0]["longitude"] = -0.18
    zone = {"geometry": ZONE_GEOM}
    result = _filter_listings_by_zone(listings, zone)
    assert len(result) == 1


def test_filter_listings_removes_outside():
    listings = [_make_listing("rm_1")]
    listings[0]["latitude"] = 52.0
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
    assert len(result) == 1
