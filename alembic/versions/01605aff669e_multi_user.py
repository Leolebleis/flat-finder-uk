"""multi_user

Revision ID: 01605aff669e
Revises:
Create Date: 2026-06-09 10:45:35.766487

"""

from collections.abc import Sequence
from datetime import UTC, datetime

import sqlalchemy as sa
from alembic import op

revision: str = "01605aff669e"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _table_exists(name: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return name in inspector.get_table_names()


def _column_exists(table: str, column: str) -> bool:
    conn = op.get_bind()
    inspector = sa.inspect(conn)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    """Create multi-user schema. Handles both fresh and existing databases."""
    is_existing_db = _table_exists("listings")

    # --- Always create new tables ---

    if not _table_exists("users"):
        op.create_table(
            "users",
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("username", sa.Text, nullable=False, unique=True),
            sa.Column("ntfy_topic", sa.Text, nullable=True),
            sa.Column("created_at", sa.Text, nullable=False),
        )

    if not _table_exists("listing_zones"):
        op.create_table(
            "listing_zones",
            sa.Column("listing_id", sa.Text, nullable=False),
            sa.Column("zone_id", sa.Integer, nullable=False),
            sa.PrimaryKeyConstraint("listing_id", "zone_id"),
        )

    if not _table_exists("listings_archive"):
        op.create_table(
            "listings_archive",
            sa.Column("id", sa.Text, primary_key=True),
            sa.Column("source", sa.Text, nullable=False),
            sa.Column("url", sa.Text, nullable=False),
            sa.Column("title", sa.Text, nullable=True),
            sa.Column("address", sa.Text, nullable=True),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column("image_url", sa.Text, nullable=True),
            sa.Column("property_type", sa.Text, nullable=True),
            sa.Column("furnishing", sa.Text, nullable=True),
            sa.Column("outdoor_type", sa.Text, nullable=True),
            sa.Column("listing_date", sa.Text, nullable=True),
            sa.Column("price_pcm", sa.Integer, nullable=True),
            sa.Column("bedrooms", sa.Integer, nullable=True),
            sa.Column("sqft", sa.Integer, nullable=True),
            sa.Column("latitude", sa.Float, nullable=True),
            sa.Column("longitude", sa.Float, nullable=True),
            sa.Column("has_dishwasher", sa.Text, nullable=False, server_default="unknown"),
            sa.Column("has_washer", sa.Text, nullable=False, server_default="unknown"),
            sa.Column("has_outdoor", sa.Text, nullable=False, server_default="unknown"),
            sa.Column("zone", sa.Text, nullable=True),
            sa.Column("first_seen", sa.DateTime, nullable=False),
        )
        op.create_index(
            "ix_listings_archive_time_zone_price",
            "listings_archive",
            ["first_seen", "zone", "bedrooms", "price_pcm"],
        )
        op.create_index(
            "ix_listings_archive_coords",
            "listings_archive",
            ["latitude", "longitude"],
        )

    if is_existing_db:
        _upgrade_existing_db()
    else:
        _create_fresh_db()


def _create_fresh_db() -> None:
    """Fresh database: create all tables from scratch."""
    op.create_table(
        "listings",
        sa.Column("id", sa.Text, primary_key=True),
        sa.Column("source", sa.Text, nullable=False),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("title", sa.Text, nullable=True),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("image_url", sa.Text, nullable=True),
        sa.Column("property_type", sa.Text, nullable=True),
        sa.Column("furnishing", sa.Text, nullable=True),
        sa.Column("outdoor_type", sa.Text, nullable=True),
        sa.Column("listing_date", sa.Text, nullable=True),
        sa.Column("price_pcm", sa.Integer, nullable=True),
        sa.Column("bedrooms", sa.Integer, nullable=True),
        sa.Column("sqft", sa.Integer, nullable=True),
        sa.Column("latitude", sa.Float, nullable=True),
        sa.Column("longitude", sa.Float, nullable=True),
        sa.Column("has_dishwasher", sa.Text, nullable=False, server_default="unknown"),
        sa.Column("has_washer", sa.Text, nullable=False, server_default="unknown"),
        sa.Column("has_outdoor", sa.Text, nullable=False, server_default="unknown"),
        sa.Column("zone", sa.Text, nullable=True),
        sa.Column("first_seen", sa.DateTime, nullable=False),
    )

    op.create_table(
        "user_state",
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("listing_id", sa.Text, nullable=False),
        sa.Column("seen", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("favourite", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("override_dishwasher", sa.Text, nullable=True),
        sa.Column("override_washer", sa.Text, nullable=True),
        sa.Column("override_outdoor", sa.Text, nullable=True),
        sa.Column("updated_at", sa.DateTime, nullable=True),
        sa.PrimaryKeyConstraint("user_id", "listing_id"),
    )

    op.create_table(
        "scraper_state",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
    )

    op.create_table(
        "zones",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("geometry", sa.Text, nullable=False),
        sa.Column("centroid_lat", sa.Float, nullable=False),
        sa.Column("centroid_lng", sa.Float, nullable=False),
        sa.Column("covering_radius_km", sa.Float, nullable=False),
        sa.Column("rightmove_id", sa.Text, nullable=True),
        sa.Column("openrent_term", sa.Text, nullable=True),
        sa.Column("color_index", sa.Integer, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
    )

    op.create_table(
        "pois",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer, nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("lat", sa.Float, nullable=False),
        sa.Column("lng", sa.Float, nullable=False),
        sa.Column("color_index", sa.Integer, nullable=False),
        sa.Column("created_at", sa.Text, nullable=False),
    )

    op.create_table(
        "poi_commutes",
        sa.Column("listing_id", sa.Text, nullable=False),
        sa.Column("poi_id", sa.Integer, nullable=False),
        sa.Column("commute_mins", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("listing_id", "poi_id"),
    )


def _upgrade_existing_db() -> None:
    """Existing database: add user_id columns, recreate user_state, backfill data."""
    conn = op.get_bind()
    now = datetime.now(UTC).isoformat()

    # 1. Create default "leo" user
    conn.execute(
        sa.text("INSERT INTO users (username, created_at) VALUES (:u, :t)"),
        {"u": "leo", "t": now},
    )
    leo_id = conn.execute(sa.text("SELECT id FROM users WHERE username = 'leo'")).scalar()

    # 2. Add user_id to zones (if missing)
    if not _column_exists("zones", "user_id"):
        with op.batch_alter_table("zones") as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.Integer, nullable=True))
        conn.execute(sa.text("UPDATE zones SET user_id = :uid"), {"uid": leo_id})
        with op.batch_alter_table("zones") as batch_op:
            batch_op.alter_column("user_id", nullable=False)

    # 3. Add user_id to pois (if missing)
    if not _column_exists("pois", "user_id"):
        with op.batch_alter_table("pois") as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.Integer, nullable=True))
        conn.execute(sa.text("UPDATE pois SET user_id = :uid"), {"uid": leo_id})
        with op.batch_alter_table("pois") as batch_op:
            batch_op.alter_column("user_id", nullable=False)

    # 4. Recreate user_state with composite PK (user_id, listing_id)
    #    Old PK was just listing_id. Batch mode handles the CREATE-COPY-DROP-RENAME.
    conn.execute(sa.text("""
        CREATE TABLE user_state_new (
            user_id INTEGER NOT NULL,
            listing_id TEXT NOT NULL,
            seen BOOLEAN DEFAULT 0 NOT NULL,
            favourite BOOLEAN DEFAULT 0 NOT NULL,
            notes TEXT,
            override_dishwasher TEXT,
            override_washer TEXT,
            override_outdoor TEXT,
            updated_at DATETIME,
            PRIMARY KEY (user_id, listing_id)
        )
    """))
    conn.execute(sa.text("""
        INSERT INTO user_state_new (user_id, listing_id, seen, favourite, notes,
            override_dishwasher, override_washer, override_outdoor, updated_at)
        SELECT :uid, listing_id, COALESCE(seen, 0), COALESCE(favourite, 0), notes,
            override_dishwasher, override_washer, override_outdoor, updated_at
        FROM user_state
    """), {"uid": leo_id})
    conn.execute(sa.text("DROP TABLE user_state"))
    conn.execute(sa.text("ALTER TABLE user_state_new RENAME TO user_state"))

    # 5. Backfill listing_zones from the zone column on listings
    conn.execute(sa.text("""
        INSERT OR IGNORE INTO listing_zones (listing_id, zone_id)
        SELECT l.id, z.id
        FROM listings l JOIN zones z ON l.zone = z.name
        WHERE l.zone IS NOT NULL
    """))


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("poi_commutes")
    op.drop_table("pois")
    op.drop_table("listing_zones")
    op.drop_table("zones")
    if _table_exists("scraper_state"):
        op.drop_table("scraper_state")
    op.drop_index("ix_listings_archive_coords", table_name="listings_archive")
    op.drop_index("ix_listings_archive_time_zone_price", table_name="listings_archive")
    op.drop_table("listings_archive")
    op.drop_table("user_state")
    op.drop_table("listings")
    op.drop_table("users")
