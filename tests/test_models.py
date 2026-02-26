# tests/test_models.py
import sqlite3
import tempfile
from pathlib import Path
from shared.models import init_db

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
