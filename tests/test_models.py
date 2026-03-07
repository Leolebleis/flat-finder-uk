# tests/test_models.py
import sqlite3
import tempfile
from pathlib import Path
from shared.models import (
    init_db,
    get_pois,
    insert_poi,
    delete_poi,
    get_poi_commutes_for_listings,
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
        expected = {"id", "source", "url", "title", "price_pcm", "bedrooms",
                    "address", "latitude", "longitude", "description", "image_url",
                    "property_type", "furnishing", "sqft", "has_dishwasher",
                    "has_washer", "has_outdoor", "outdoor_type", "zone", "commute_mins",
                    "gym_commute_mins", "first_seen", "listing_date"}
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

def test_migrate_seeds_pois_from_legacy_columns():
    """When pois table is empty but listings have commute_mins, seed Work and Gym POIs."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        conn.execute(
            "INSERT INTO listings (id, source, url, first_seen, commute_mins, gym_commute_mins) "
            "VALUES ('test1', 'rightmove', 'http://x', '2026-01-01', 35, 12)"
        )
        conn.commit()
        conn.close()
        # Re-init triggers migration
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        pois = conn.execute("SELECT * FROM pois ORDER BY id").fetchall()
        assert len(pois) == 2
        assert pois[0]["name"] == "Work"
        assert pois[1]["name"] == "Gym"
        commutes = conn.execute("SELECT * FROM poi_commutes WHERE listing_id = 'test1'").fetchall()
        assert len(commutes) == 2
        vals = {row["poi_id"]: row["commute_mins"] for row in commutes}
        assert vals[pois[0]["id"]] == 35
        assert vals[pois[1]["id"]] == 12
        conn.close()

def test_migrate_is_idempotent():
    """Running init_db multiple times after migration should not duplicate POIs."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        conn.execute(
            "INSERT INTO listings (id, source, url, first_seen, commute_mins) "
            "VALUES ('test1', 'rightmove', 'http://x', '2026-01-01', 20)"
        )
        conn.commit()
        conn.close()
        init_db(db_path)
        init_db(db_path)  # Third call
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM pois").fetchone()[0]
        assert count == 2
        conn.close()

def test_migrate_skips_when_no_legacy_data():
    """When no listings have commute data, no POIs should be seeded."""
    with tempfile.NamedTemporaryFile(suffix=".db") as f:
        db_path = Path(f.name)
        init_db(db_path)
        conn = sqlite3.connect(db_path)
        count = conn.execute("SELECT COUNT(*) FROM pois").fetchone()[0]
        assert count == 0
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
