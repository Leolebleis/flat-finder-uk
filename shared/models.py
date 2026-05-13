import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

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

ZONES_SCHEMA = """
CREATE TABLE IF NOT EXISTS zones (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    geometry            TEXT NOT NULL,
    centroid_lat        REAL NOT NULL,
    centroid_lng        REAL NOT NULL,
    covering_radius_km  REAL NOT NULL,
    rightmove_id        TEXT,
    openrent_term       TEXT,
    color_index         INTEGER NOT NULL,
    created_at          TEXT NOT NULL
);
"""

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

# Columns added to user_state after the table existed. Idempotent thanks to
# the table_info check; older DBs missing these columns will get them added,
# fresh DBs are no-ops.
_USER_STATE_LATE_COLUMNS = [
    ("override_dishwasher", "TEXT"),
    ("override_washer", "TEXT"),
    ("override_outdoor", "TEXT"),
]


def _ensure_columns(conn: sqlite3.Connection, table: str, columns: list[tuple[str, str]]) -> None:
    """Idempotent ADD COLUMN guarded by PRAGMA table_info."""
    existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    for col, col_type in columns:
        if col not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}")


def init_db(db_path: Path) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(LISTINGS_SCHEMA)
    conn.execute(SCRAPER_STATE_SCHEMA)
    conn.execute(POIS_SCHEMA)
    conn.execute(POI_COMMUTES_SCHEMA)
    conn.execute(ZONES_SCHEMA)
    conn.execute(USER_STATE_SCHEMA)
    # Older listings DBs may carry the deprecated commute_mins/gym_commute_mins
    # columns. New columns to ensure: zone (which post-dates the first release).
    _ensure_columns(conn, "listings", [("zone", "TEXT")])
    _ensure_columns(conn, "user_state", _USER_STATE_LATE_COLUMNS)
    conn.commit()
    conn.close()


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    # Two writers (scraper + UI) share this DB in WAL mode; busy_timeout
    # lets SQLite spin internally on lock contention rather than raise.
    conn.execute("PRAGMA busy_timeout=5000")
    return conn


def insert_listing(conn: sqlite3.Connection, listing: dict) -> bool:
    """Insert a listing. Returns True if new, False if already existed."""
    listing.setdefault("zone", None)
    try:
        conn.execute(
            """INSERT INTO listings (id, source, url, title, price_pcm, bedrooms,
               address, latitude, longitude, description, image_url, property_type,
               furnishing, sqft, has_dishwasher, has_washer, has_outdoor, outdoor_type,
               zone, first_seen, listing_date)
               VALUES (:id, :source, :url, :title, :price_pcm, :bedrooms,
               :address, :latitude, :longitude, :description, :image_url, :property_type,
               :furnishing, :sqft, :has_dishwasher, :has_washer, :has_outdoor, :outdoor_type,
               :zone, :first_seen, :listing_date)""",
            listing,
        )
    except sqlite3.IntegrityError:
        return False
    conn.commit()
    return True


def get_listings(conn: sqlite3.Connection, since: str | None = None, limit: int = 50, offset: int = 0) -> list[dict]:
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


def prune_orphan_user_state(conn: sqlite3.Connection) -> None:
    """Remove user_state rows whose listing no longer exists."""
    conn.execute("DELETE FROM user_state WHERE listing_id NOT IN (SELECT id FROM listings)")


def prune_orphan_poi_commutes(conn: sqlite3.Connection) -> None:
    """Remove poi_commutes rows whose listing no longer exists."""
    conn.execute("DELETE FROM poi_commutes WHERE listing_id NOT IN (SELECT id FROM listings)")


# --- POI helpers ---


def get_pois(conn: sqlite3.Connection) -> list[dict]:
    """Return all POIs ordered by id."""
    rows = conn.execute("SELECT * FROM pois ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def insert_poi(conn: sqlite3.Connection, name: str, lat: float, lng: float, color_index: int) -> int:
    """Insert a new POI and return its id."""
    created_at = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        "INSERT INTO pois (name, lat, lng, color_index, created_at) VALUES (?, ?, ?, ?, ?)",
        (name, lat, lng, color_index, created_at),
    )
    conn.commit()
    if cursor.lastrowid is None:
        msg = "INSERT did not produce a lastrowid"
        raise RuntimeError(msg)
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
        f"SELECT listing_id, poi_id, commute_mins FROM poi_commutes WHERE listing_id IN ({placeholders})",  # noqa: S608
        listing_ids,
    ).fetchall()
    result: dict[str, dict[int, int]] = {}
    for row in rows:
        result.setdefault(row["listing_id"], {})[row["poi_id"]] = row["commute_mins"]
    return result


def upsert_poi_commute(conn: sqlite3.Connection, listing_id: str, poi_id: int, commute_mins: int) -> None:
    """Insert or update a commute time for a listing/POI pair."""
    conn.execute(
        "INSERT OR REPLACE INTO poi_commutes (listing_id, poi_id, commute_mins) VALUES (?, ?, ?)",
        (listing_id, poi_id, commute_mins),
    )
    conn.commit()


def listings_missing_poi_commute(
    conn: sqlite3.Connection,
    poi_id: int,
) -> list[sqlite3.Row]:
    """Return listings with coords that lack a poi_commute row for this POI."""
    return conn.execute(
        """SELECT l.id, l.latitude, l.longitude FROM listings l
           WHERE l.latitude IS NOT NULL AND l.longitude IS NOT NULL
           AND NOT EXISTS (
               SELECT 1 FROM poi_commutes pc
               WHERE pc.listing_id = l.id AND pc.poi_id = ?
           )""",
        (poi_id,),
    ).fetchall()


# --- User state helpers ---


_USER_STATE_FIELDS = ("seen", "favourite", "notes", "override_dishwasher", "override_washer", "override_outdoor")


def upsert_user_state(conn: sqlite3.Connection, listing_id: str, updates: dict[str, Any]) -> dict[str, Any]:
    """Upsert user_state for a listing, applying only keys present in `updates`.

    Returns the resulting row as a dict. Uses ON CONFLICT so values not in
    `updates` keep their previous value (no read-modify-write race).
    """
    fields = {k: updates[k] for k in _USER_STATE_FIELDS if k in updates}
    fields["updated_at"] = datetime.now(UTC).isoformat()
    cols = ["listing_id", *fields]
    placeholders = ",".join("?" for _ in cols)
    # COALESCE excluded against existing keeps prior value when the new value is
    # NULL; but we want explicit NULLs to take effect. Instead, only update keys
    # that were sent — drive the SET list from `fields` directly.
    set_clause = ", ".join(f"{k}=excluded.{k}" for k in fields)
    sql = (
        f"INSERT INTO user_state ({','.join(cols)}) VALUES ({placeholders}) "  # noqa: S608
        f"ON CONFLICT(listing_id) DO UPDATE SET {set_clause}"
    )
    with suppress(sqlite3.IntegrityError):
        conn.execute(sql, [listing_id, *fields.values()])
        conn.commit()
    row = conn.execute("SELECT * FROM user_state WHERE listing_id = ?", (listing_id,)).fetchone()
    return dict(row) if row else {}


# --- Zone helpers ---


def get_zones(conn: sqlite3.Connection) -> list[dict]:
    """Return all zones ordered by id."""
    rows = conn.execute("SELECT * FROM zones ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def insert_zone(  # noqa: PLR0913
    conn: sqlite3.Connection,
    name: str,
    geometry: str,
    centroid_lat: float,
    centroid_lng: float,
    covering_radius_km: float,
    rightmove_id: str | None,
    openrent_term: str | None,
    color_index: int,
) -> int:
    """Insert a new zone and return its id."""
    created_at = datetime.now(UTC).isoformat()
    cursor = conn.execute(
        """INSERT INTO zones (name, geometry, centroid_lat, centroid_lng,
           covering_radius_km, rightmove_id, openrent_term, color_index, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            name,
            geometry,
            centroid_lat,
            centroid_lng,
            covering_radius_km,
            rightmove_id,
            openrent_term,
            color_index,
            created_at,
        ),
    )
    conn.commit()
    if cursor.lastrowid is None:
        msg = "INSERT did not produce a lastrowid"
        raise RuntimeError(msg)
    return cursor.lastrowid


def update_zone(conn: sqlite3.Connection, zone_id: int, **kwargs: object) -> None:
    """Update zone fields. Pass only the fields to update."""
    allowed = {
        "name",
        "geometry",
        "centroid_lat",
        "centroid_lng",
        "covering_radius_km",
        "rightmove_id",
        "openrent_term",
    }
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    set_clause = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE zones SET {set_clause} WHERE id = ?", [*fields.values(), zone_id])  # noqa: S608
    conn.commit()


def delete_zone(conn: sqlite3.Connection, zone_id: int) -> None:
    """Delete a zone."""
    conn.execute("DELETE FROM zones WHERE id = ?", (zone_id,))
    conn.commit()
