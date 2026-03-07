import sqlite3
from datetime import datetime, timezone
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
    zone            TEXT,
    commute_mins    INTEGER,
    gym_commute_mins INTEGER,
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

POIS_SCHEMA = """
CREATE TABLE IF NOT EXISTS pois (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT NOT NULL,
    lat         REAL NOT NULL,
    lng         REAL NOT NULL,
    color_index INTEGER NOT NULL,
    created_at  TEXT NOT NULL
);
"""

POI_COMMUTES_SCHEMA = """
CREATE TABLE IF NOT EXISTS poi_commutes (
    listing_id  TEXT NOT NULL,
    poi_id      INTEGER NOT NULL,
    commute_mins INTEGER NOT NULL,
    PRIMARY KEY (listing_id, poi_id)
);
"""

def init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(LISTINGS_SCHEMA)
    conn.execute(SCRAPER_STATE_SCHEMA)
    conn.execute(POIS_SCHEMA)
    conn.execute(POI_COMMUTES_SCHEMA)
    # Migrate existing databases: add new columns if missing
    for col, col_type in [("zone", "TEXT"), ("commute_mins", "INTEGER"),
                          ("gym_commute_mins", "INTEGER")]:
        try:
            conn.execute(f"ALTER TABLE listings ADD COLUMN {col} {col_type}")
        except sqlite3.OperationalError:
            pass  # Column already exists
    _migrate_legacy_commutes(conn)
    conn.commit()
    conn.close()

def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def insert_listing(conn: sqlite3.Connection, listing: dict) -> bool:
    """Insert a listing. Returns True if new, False if already existed."""
    listing.setdefault("zone", None)
    listing.setdefault("commute_mins", None)
    listing.setdefault("gym_commute_mins", None)
    try:
        conn.execute(
            """INSERT INTO listings (id, source, url, title, price_pcm, bedrooms,
               address, latitude, longitude, description, image_url, property_type,
               furnishing, sqft, has_dishwasher, has_washer, has_outdoor, outdoor_type,
               zone, commute_mins, gym_commute_mins, first_seen, listing_date)
               VALUES (:id, :source, :url, :title, :price_pcm, :bedrooms,
               :address, :latitude, :longitude, :description, :image_url, :property_type,
               :furnishing, :sqft, :has_dishwasher, :has_washer, :has_outdoor, :outdoor_type,
               :zone, :commute_mins, :gym_commute_mins, :first_seen, :listing_date)""",
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


# --- POI helpers ---

def _migrate_legacy_commutes(conn: sqlite3.Connection) -> None:
    """Seed Work and Gym POIs from legacy commute columns. Idempotent."""
    count = conn.execute("SELECT COUNT(*) FROM pois").fetchone()[0]
    if count > 0:
        return  # Already migrated

    has_legacy = conn.execute(
        "SELECT COUNT(*) FROM listings WHERE commute_mins IS NOT NULL OR gym_commute_mins IS NOT NULL"
    ).fetchone()[0]
    if has_legacy == 0:
        return  # No legacy data to migrate

    now = datetime.now(timezone.utc).isoformat()
    conn.execute(
        "INSERT INTO pois (name, lat, lng, color_index, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Work", 51.4869, -0.1832, 0, now),
    )
    work_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.execute(
        "INSERT INTO pois (name, lat, lng, color_index, created_at) VALUES (?, ?, ?, ?, ?)",
        ("Gym", 51.5445, -0.1762, 1, now),
    )
    gym_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    # Copy legacy commute_mins -> poi_commutes for Work
    conn.execute(
        "INSERT INTO poi_commutes (listing_id, poi_id, commute_mins) "
        "SELECT id, ?, commute_mins FROM listings WHERE commute_mins IS NOT NULL",
        (work_id,),
    )
    # Copy legacy gym_commute_mins -> poi_commutes for Gym
    conn.execute(
        "INSERT INTO poi_commutes (listing_id, poi_id, commute_mins) "
        "SELECT id, ?, gym_commute_mins FROM listings WHERE gym_commute_mins IS NOT NULL",
        (gym_id,),
    )


def get_pois(conn: sqlite3.Connection) -> list[dict]:
    """Return all POIs ordered by id."""
    rows = conn.execute("SELECT * FROM pois ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def insert_poi(conn: sqlite3.Connection, name: str, lat: float, lng: float, color_index: int) -> int:
    """Insert a new POI and return its id."""
    created_at = datetime.now(timezone.utc).isoformat()
    cursor = conn.execute(
        "INSERT INTO pois (name, lat, lng, color_index, created_at) VALUES (?, ?, ?, ?, ?)",
        (name, lat, lng, color_index, created_at),
    )
    conn.commit()
    return cursor.lastrowid


def delete_poi(conn: sqlite3.Connection, poi_id: int) -> None:
    """Delete a POI and its associated commute data."""
    conn.execute("DELETE FROM poi_commutes WHERE poi_id = ?", (poi_id,))
    conn.execute("DELETE FROM pois WHERE id = ?", (poi_id,))
    conn.commit()


def get_poi_commutes_for_listings(conn: sqlite3.Connection, listing_ids: list[str]) -> dict[str, dict[int, int]]:
    """Return {listing_id: {poi_id: commute_mins}} for the given listing ids."""
    if not listing_ids:
        return {}
    placeholders = ",".join("?" for _ in listing_ids)
    rows = conn.execute(
        f"SELECT listing_id, poi_id, commute_mins FROM poi_commutes WHERE listing_id IN ({placeholders})",
        listing_ids,
    ).fetchall()
    result: dict[str, dict[int, int]] = {}
    for row in rows:
        lid = row["listing_id"] if isinstance(row, sqlite3.Row) else row[0]
        pid = row["poi_id"] if isinstance(row, sqlite3.Row) else row[1]
        mins = row["commute_mins"] if isinstance(row, sqlite3.Row) else row[2]
        result.setdefault(lid, {})[pid] = mins
    return result


def upsert_poi_commute(conn: sqlite3.Connection, listing_id: str, poi_id: int, commute_mins: int) -> None:
    """Insert or update a commute time for a listing/POI pair."""
    conn.execute(
        "INSERT OR REPLACE INTO poi_commutes (listing_id, poi_id, commute_mins) VALUES (?, ?, ?)",
        (listing_id, poi_id, commute_mins),
    )
    conn.commit()
