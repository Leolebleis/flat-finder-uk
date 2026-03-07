import json
import sqlite3
import tempfile
from pathlib import Path
from unittest.mock import patch
from shared.models import init_db, get_connection, get_zones


def _write_zones_json(path: Path, zones: list[dict]):
    with open(path, "w") as f:
        json.dump(zones, f)


LEGACY_ZONES = [
    {
        "name": "Finchley Road",
        "rightmove_id": "STATION^3509",
        "openrent_term": "Finchley Road Station",
        "radius_miles": 1.0,
        "lat": 51.5472,
        "lng": -0.1803,
    },
    {
        "name": "St John's Wood",
        "rightmove_id": "STATION^8627",
        "openrent_term": "St John's Wood Station",
        "radius_miles": 0.75,
        "lat": 51.5347,
        "lng": -0.1743,
    },
]


def test_migration_imports_zones_from_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        zones_path = Path(tmpdir) / "zones.json"
        _write_zones_json(zones_path, LEGACY_ZONES)
        with patch("shared.models.ZONES_FILE", zones_path):
            init_db(db_path)
        conn = get_connection(db_path)
        zones = get_zones(conn)
        conn.close()
        assert len(zones) == 2
        assert zones[0]["name"] == "Finchley Road"
        assert zones[0]["rightmove_id"] == "STATION^3509"
        assert zones[0]["openrent_term"] == "Finchley Road Station"
        geom = json.loads(zones[0]["geometry"])
        assert geom["type"] == "Polygon"
        assert len(geom["coordinates"][0]) == 33  # 32 vertices + closing


def test_migration_is_idempotent():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        zones_path = Path(tmpdir) / "zones.json"
        _write_zones_json(zones_path, LEGACY_ZONES)
        with patch("shared.models.ZONES_FILE", zones_path):
            init_db(db_path)
            init_db(db_path)  # Second call
        conn = get_connection(db_path)
        zones = get_zones(conn)
        conn.close()
        assert len(zones) == 2  # Not 4


def test_migration_skips_when_no_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        with patch("shared.models.ZONES_FILE", Path(tmpdir) / "nonexistent.json"):
            init_db(db_path)
        conn = get_connection(db_path)
        zones = get_zones(conn)
        conn.close()
        assert len(zones) == 0
