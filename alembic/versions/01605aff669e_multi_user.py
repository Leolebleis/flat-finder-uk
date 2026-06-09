"""multi_user

Revision ID: 01605aff669e
Revises:
Create Date: 2026-06-09 10:45:35.766487

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "01605aff669e"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create the full multi-user schema from scratch."""
    # users — one row per user account
    op.create_table(
        "users",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("username", sa.Text, nullable=False, unique=True),
        sa.Column("ntfy_topic", sa.Text, nullable=True),
        sa.Column("created_at", sa.Text, nullable=False),
    )

    # listings — active property listings
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

    # user_state — per-user state for each listing (composite PK)
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

    # listings_archive — expired listings kept for analytics
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

    # Analytics indexes on listings_archive
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

    # scraper_state — key/value store for scraper bookmarks
    op.create_table(
        "scraper_state",
        sa.Column("key", sa.Text, primary_key=True),
        sa.Column("value", sa.Text, nullable=False),
    )

    # zones — user-drawn search polygons
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

    # listing_zones — many-to-many between listings and zones
    op.create_table(
        "listing_zones",
        sa.Column("listing_id", sa.Text, nullable=False),
        sa.Column("zone_id", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("listing_id", "zone_id"),
    )

    # pois — Points of Interest (places users commute to)
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

    # poi_commutes — cached TfL commute times from listings to POIs
    op.create_table(
        "poi_commutes",
        sa.Column("listing_id", sa.Text, nullable=False),
        sa.Column("poi_id", sa.Integer, nullable=False),
        sa.Column("commute_mins", sa.Integer, nullable=False),
        sa.PrimaryKeyConstraint("listing_id", "poi_id"),
    )


def downgrade() -> None:
    """Drop all tables in reverse dependency order."""
    op.drop_table("poi_commutes")
    op.drop_table("pois")
    op.drop_table("listing_zones")
    op.drop_table("zones")
    op.drop_table("scraper_state")
    op.drop_index("ix_listings_archive_coords", table_name="listings_archive")
    op.drop_index("ix_listings_archive_time_zone_price", table_name="listings_archive")
    op.drop_table("listings_archive")
    op.drop_table("user_state")
    op.drop_table("listings")
    op.drop_table("users")
