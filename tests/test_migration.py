import sqlite3
from pathlib import Path

from alembic import command
from alembic.config import Config


def _alembic_config(db_path: Path) -> Config:
    """Create an Alembic config pointing at the given DB."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


class TestFreshMigration:
    """Feature: Initial schema creation

    As the application starting with a fresh database,
    running alembic upgrade head creates all required tables.
    """

    def test_migration_creates_all_tables(self, tmp_path):
        """Given a fresh empty database
        When I run alembic upgrade head
        Then all 9 tables are created
        """
        db_path = tmp_path / "fresh.db"
        cfg = _alembic_config(db_path)
        command.upgrade(cfg, "head")

        conn = sqlite3.connect(db_path)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'alembic%'"
        ).fetchall()}
        conn.close()

        assert tables == {
            "users", "listings", "user_state", "listings_archive",
            "scraper_state", "zones", "listing_zones", "pois", "poi_commutes",
        }

    def test_user_state_has_composite_pk(self, tmp_path):
        """Given a fresh database after migration
        When I inspect user_state
        Then its PK is (user_id, listing_id)
        """
        db_path = tmp_path / "fresh.db"
        cfg = _alembic_config(db_path)
        command.upgrade(cfg, "head")

        conn = sqlite3.connect(db_path)
        pk_cols = [row[1] for row in conn.execute("PRAGMA table_info(user_state)").fetchall() if row[5] > 0]
        conn.close()
        assert set(pk_cols) == {"user_id", "listing_id"}

    def test_zones_has_user_id_column(self, tmp_path):
        """Given a fresh database after migration
        When I inspect zones
        Then user_id column exists and is NOT NULL
        """
        db_path = tmp_path / "fresh.db"
        cfg = _alembic_config(db_path)
        command.upgrade(cfg, "head")

        conn = sqlite3.connect(db_path)
        cols = {row[1]: row[3] for row in conn.execute("PRAGMA table_info(zones)").fetchall()}
        conn.close()
        assert "user_id" in cols
        assert cols["user_id"] == 1  # notnull = 1

    def test_listings_archive_has_analytics_indexes(self, tmp_path):
        """Given a fresh database after migration
        When I inspect listings_archive indexes
        Then analytics indexes exist
        """
        db_path = tmp_path / "fresh.db"
        cfg = _alembic_config(db_path)
        command.upgrade(cfg, "head")

        conn = sqlite3.connect(db_path)
        indexes = {row[1] for row in conn.execute(
            "SELECT * FROM sqlite_master WHERE type='index' AND tbl_name='listings_archive'"
        ).fetchall()}
        conn.close()
        assert len(indexes) >= 2  # at least the two analytics indexes

    def test_downgrade_drops_all_tables(self, tmp_path):
        """Given a migrated database
        When I run alembic downgrade base
        Then all application tables are removed
        """
        db_path = tmp_path / "fresh.db"
        cfg = _alembic_config(db_path)
        command.upgrade(cfg, "head")
        command.downgrade(cfg, "base")

        conn = sqlite3.connect(db_path)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'alembic%'"
        ).fetchall()}
        conn.close()
        assert len(tables) == 0
