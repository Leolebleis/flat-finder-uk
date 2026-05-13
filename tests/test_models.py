# tests/test_models.py
import sqlite3
import tempfile
from pathlib import Path

from shared.models import (
    delete_poi,
    delete_zone,
    get_poi_commutes_for_listings,
    get_pois,
    get_zones,
    init_db,
    insert_poi,
    insert_zone,
    update_zone,
    upsert_poi_commute,
)


def test_init_db_creates_listings_table():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='listings'")
        assert cursor.fetchone() is not None
        conn.close()


def test_init_db_creates_scraper_state_table():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='scraper_state'")
        assert cursor.fetchone() is not None
        conn.close()


def test_listings_table_has_expected_columns():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("PRAGMA table_info(listings)")
        columns = {row[1] for row in cursor.fetchall()}
        expected = {
            "id",
            "source",
            "url",
            "title",
            "price_pcm",
            "bedrooms",
            "address",
            "latitude",
            "longitude",
            "description",
            "image_url",
            "property_type",
            "furnishing",
            "sqft",
            "has_dishwasher",
            "has_washer",
            "has_outdoor",
            "outdoor_type",
            "zone",
            "first_seen",
            "listing_date",
        }
        assert expected == columns
        conn.close()


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


def test_init_db_creates_user_state_table():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_state'")
        assert cursor.fetchone() is not None
        conn.close()


def test_insert_and_get_pois():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        poi_id = insert_poi(conn, "Office", 51.5, -0.1, 0)
        assert isinstance(poi_id, int)
        pois = get_pois(conn)
        assert len(pois) == 1
        assert pois[0]["name"] == "Office"
        assert pois[0]["lat"] == 51.5
        assert pois[0]["lng"] == -0.1
        assert pois[0]["color_index"] == 0
        assert pois[0]["created_at"] is not None
        conn.close()


def test_delete_poi_cascades_commutes():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        poi_id = insert_poi(conn, "Office", 51.5, -0.1, 0)
        upsert_poi_commute(conn, "listing1", poi_id, 25)
        delete_poi(conn, poi_id)
        assert len(get_pois(conn)) == 0
        commutes = conn.execute("SELECT * FROM poi_commutes WHERE poi_id = ?", (poi_id,)).fetchall()
        assert len(commutes) == 0
        conn.close()


def test_upsert_poi_commute_insert_and_update():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        poi_id = insert_poi(conn, "Office", 51.5, -0.1, 0)
        upsert_poi_commute(conn, "listing1", poi_id, 25)
        result = get_poi_commutes_for_listings(conn, ["listing1"])
        assert result["listing1"][poi_id] == 25
        # Update
        upsert_poi_commute(conn, "listing1", poi_id, 30)
        result = get_poi_commutes_for_listings(conn, ["listing1"])
        assert result["listing1"][poi_id] == 30
        conn.close()


def test_get_poi_commutes_for_multiple_listings():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        poi1 = insert_poi(conn, "Work", 51.5, -0.1, 0)
        poi2 = insert_poi(conn, "Gym", 51.6, -0.2, 1)
        upsert_poi_commute(conn, "L1", poi1, 10)
        upsert_poi_commute(conn, "L1", poi2, 20)
        upsert_poi_commute(conn, "L2", poi1, 15)
        result = get_poi_commutes_for_listings(conn, ["L1", "L2", "L3"])
        assert result["L1"][poi1] == 10
        assert result["L1"][poi2] == 20
        assert result["L2"][poi1] == 15
        assert "L3" not in result
        conn.close()


def test_get_poi_commutes_empty_list():
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        result = get_poi_commutes_for_listings(conn, [])
        assert result == {}
        conn.close()


SAMPLE_GEOMETRY = (
    '{"type":"Polygon","coordinates":[[[-0.19,51.54],[-0.17,51.54],[-0.17,51.55],[-0.19,51.55],[-0.19,51.54]]]}'
)


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
        zone_id = insert_zone(
            conn,
            "NW6 Area",
            SAMPLE_GEOMETRY,
            centroid_lat=51.545,
            centroid_lng=-0.18,
            covering_radius_km=1.2,
            rightmove_id="OUTCODE^1862",
            openrent_term="NW6",
            color_index=0,
        )
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
        zone_id = insert_zone(
            conn,
            "Old Name",
            SAMPLE_GEOMETRY,
            centroid_lat=51.545,
            centroid_lng=-0.18,
            covering_radius_km=1.2,
            rightmove_id="OUTCODE^1862",
            openrent_term="NW6",
            color_index=0,
        )
        new_geom = SAMPLE_GEOMETRY.replace("51.54", "51.55")
        update_zone(
            conn,
            zone_id,
            name="New Name",
            geometry=new_geom,
            centroid_lat=51.55,
            centroid_lng=-0.18,
            covering_radius_km=1.5,
            rightmove_id="OUTCODE^1862",
            openrent_term="NW6",
        )
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
        zone_id = insert_zone(
            conn,
            "Test",
            SAMPLE_GEOMETRY,
            centroid_lat=51.545,
            centroid_lng=-0.18,
            covering_radius_km=1.2,
            rightmove_id="OUTCODE^1862",
            openrent_term="NW6",
            color_index=0,
        )
        delete_zone(conn, zone_id)
        assert len(get_zones(conn)) == 0
        conn.close()
