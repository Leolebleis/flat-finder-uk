from flat_finder.database import Base, get_engine
from flat_finder.listings.persistence import (
    ListingArchiveDB,
    ListingDB,
    ListingStateDB,
    ScraperStateDB,
)
from flat_finder.pois.persistence import POIDB, POICommuteDB
from flat_finder.users.persistence import UserDB
from flat_finder.zones.persistence import ListingZoneDB, ZoneDB


class TestORMModels:
    """Feature: Database schema
    As the application, the ORM models create
    the correct tables with the correct columns.
    """

    def test_all_tables_created(self, tmp_path):
        """Given all ORM models are imported
        When I create_all on a fresh database
        Then all 9 tables exist
        """
        engine = get_engine(tmp_path / "test.db")
        Base.metadata.create_all(engine)
        table_names = set(Base.metadata.tables.keys())
        assert table_names == {
            "listings",
            "listing_zones",
            "listings_archive",
            "scraper_state",
            "zones",
            "pois",
            "poi_commutes",
            "users",
            "user_state",
        }

    def test_user_state_has_composite_pk(self, tmp_path):
        """Given the user_state table
        When I inspect its primary key
        Then it is (user_id, listing_id)
        """
        engine = get_engine(tmp_path / "test.db")
        Base.metadata.create_all(engine)
        pk_cols = [c.name for c in ListingStateDB.__table__.primary_key.columns]
        assert pk_cols == ["user_id", "listing_id"]

    def test_zones_has_user_id(self):
        """Given the zones table
        When I inspect the user_id column
        Then it is not nullable
        """
        col = ZoneDB.__table__.c.user_id
        assert not col.nullable

    def test_pois_has_user_id(self):
        """Given the pois table
        When I inspect the user_id column
        Then it is not nullable
        """
        col = POIDB.__table__.c.user_id
        assert not col.nullable

    def test_listing_zones_composite_pk(self):
        """Given the listing_zones table
        When I inspect its primary key
        Then it is (listing_id, zone_id)
        """
        pk_cols = [c.name for c in ListingZoneDB.__table__.primary_key.columns]
        assert pk_cols == ["listing_id", "zone_id"]

    def test_listings_archive_same_columns_as_listings(self):
        """Given the listings and listings_archive tables
        When I compare their column names
        Then they are identical
        """
        listing_cols = {c.name for c in ListingDB.__table__.columns}
        archive_cols = {c.name for c in ListingArchiveDB.__table__.columns}
        assert listing_cols == archive_cols

    def test_users_table_has_expected_columns(self):
        """Given the users table
        When I inspect its columns
        Then it has id, username, ntfy_topic, search params, created_at
        """
        col_names = {c.name for c in UserDB.__table__.columns}
        expected = {
            "id", "username", "ntfy_topic", "max_rent_pcm",
            "min_bedrooms", "max_bedrooms", "created_at",
        }
        assert col_names == expected

    def test_users_username_is_unique(self):
        """Given the users table
        When I inspect the username column
        Then it has a unique constraint
        """
        col = UserDB.__table__.c.username
        assert col.unique

    def test_scraper_state_pk_is_key(self):
        """Given the scraper_state table
        When I inspect its primary key
        Then it is the 'key' column
        """
        pk_cols = [c.name for c in ScraperStateDB.__table__.primary_key.columns]
        assert pk_cols == ["key"]

    def test_listings_has_first_seen(self):
        """Given the listings table
        When I inspect columns
        Then first_seen is present and not nullable
        """
        col = ListingDB.__table__.c.first_seen
        assert not col.nullable

    def test_poi_commutes_composite_pk(self):
        """Given the poi_commutes table
        When I inspect its primary key
        Then it is (listing_id, poi_id)
        """
        pk_cols = [c.name for c in POICommuteDB.__table__.primary_key.columns]
        assert pk_cols == ["listing_id", "poi_id"]
