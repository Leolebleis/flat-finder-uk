import sqlite3
from pathlib import Path

LISTINGS_SCHEMA = """
CREATE TABLE IF NOT EXISTS listings (
    id              TEXT PRIMARY KEY,
    source          TEXT NOT NULL,
    url             TEXT NOT NULL,
    title           TEXT,
    price_pcm       INTEGER,
    bedrooms        INTEGER,
    address         TEXT,
    latitude        REAL,
    longitude       REAL,
    description     TEXT,
    image_url       TEXT,
    property_type   TEXT,
    furnishing      TEXT,
    sqft            INTEGER,
    has_dishwasher  TEXT DEFAULT 'unknown',
    has_washer      TEXT DEFAULT 'unknown',
    has_outdoor     TEXT DEFAULT 'unknown',
    outdoor_type    TEXT,
    first_seen      DATETIME NOT NULL,
    listing_date    TEXT
);
"""

SCRAPER_STATE_SCHEMA = """
CREATE TABLE IF NOT EXISTS scraper_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

def init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(LISTINGS_SCHEMA)
    conn.execute(SCRAPER_STATE_SCHEMA)
    conn.commit()
    conn.close()

def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def insert_listing(conn: sqlite3.Connection, listing: dict) -> bool:
    """Insert a listing. Returns True if new, False if already existed."""
    try:
        conn.execute(
            """INSERT INTO listings (id, source, url, title, price_pcm, bedrooms,
               address, latitude, longitude, description, image_url, property_type,
               furnishing, sqft, has_dishwasher, has_washer, has_outdoor, outdoor_type,
               first_seen, listing_date)
               VALUES (:id, :source, :url, :title, :price_pcm, :bedrooms,
               :address, :latitude, :longitude, :description, :image_url, :property_type,
               :furnishing, :sqft, :has_dishwasher, :has_washer, :has_outdoor, :outdoor_type,
               :first_seen, :listing_date)""",
            listing,
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False

def get_listings(conn: sqlite3.Connection, since: str | None = None,
                 limit: int = 50, offset: int = 0) -> list[dict]:
    query = "SELECT * FROM listings"
    params: list = []
    if since:
        query += " WHERE first_seen > ?"
        params.append(since)
    query += " ORDER BY first_seen DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = conn.execute(query, params).fetchall()
    return [dict(row) for row in rows]

def get_state(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM scraper_state WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else None

def set_state(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO scraper_state (key, value) VALUES (?, ?)",
        (key, value),
    )
    conn.commit()
