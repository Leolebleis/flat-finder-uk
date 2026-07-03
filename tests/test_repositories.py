"""E2E repository tests using a real in-memory SQLite DB via conftest fixtures."""

from datetime import UTC, datetime, timedelta

from flat_finder.listings.persistence import ListingRepository, ListingStateRepository
from flat_finder.pois.persistence import POICommuteRepository, POIRepository
from flat_finder.users.persistence import UserRepository
from flat_finder.zones.persistence import ListingZoneRepository, ZoneRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_listing_dict(
    listing_id: str = "rm_1",
    source: str = "rightmove",
    lat: float | None = 51.5,
    lng: float | None = -0.1,
) -> dict:
    return {
        "id": listing_id,
        "source": source,
        "url": f"https://example.com/{listing_id}",
        "title": "Nice flat",
        "address": "1 Test Street, London",
        "price_pcm": 1500,
        "bedrooms": 2,
        "latitude": lat,
        "longitude": lng,
        "first_seen": datetime.now(UTC).replace(tzinfo=None),
        "has_dishwasher": "unknown",
        "has_washer": "unknown",
        "has_outdoor": "unknown",
    }


def _make_zone(session, user_id: int = 1, name: str = "Zone A", color_index: int = 0) -> object:
    repo = ZoneRepository(session)
    return repo.create(
        user_id=user_id,
        name=name,
        geometry='{"type":"Polygon","coordinates":[]}',
        centroid_lat=51.5,
        centroid_lng=-0.1,
        covering_radius_km=2.0,
        rightmove_id=None,
        openrent_term=None,
        color_index=color_index,
    )


# ---------------------------------------------------------------------------
# TestUserRepository
# ---------------------------------------------------------------------------


class TestUserRepository:
    """Feature: User management"""

    def test_create_user_and_retrieve_by_username(self, db_session):
        """Given a new username
        When I create a user and retrieve by username
        Then I get back a User with matching fields.
        """
        repo = UserRepository(db_session)

        user = repo.create("alice")

        retrieved = repo.get_by_username("alice")
        assert retrieved is not None
        assert retrieved.id == user.id
        assert retrieved.username == "alice"
        assert retrieved.ntfy_topic is not None
        assert retrieved.ntfy_topic.startswith("flat-finder-")

    def test_create_user_and_retrieve_by_id(self, db_session):
        """Given a created user
        When I retrieve by id
        Then I get back the same user.
        """
        repo = UserRepository(db_session)
        user = repo.create("bob")

        retrieved = repo.get_by_id(user.id)

        assert retrieved is not None
        assert retrieved.username == "bob"

    def test_get_nonexistent_user_returns_none(self, db_session):
        """Given no users in the DB
        When I query by a non-existent id or username
        Then None is returned.
        """
        repo = UserRepository(db_session)

        assert repo.get_by_id(999) is None
        assert repo.get_by_username("ghost") is None

    def test_update_ntfy_topic(self, db_session):
        """Given an existing user
        When I set an ntfy_topic
        Then the topic is persisted.
        """
        repo = UserRepository(db_session)
        user = repo.create("carol")

        repo.update_ntfy_topic(user.id, "my-topic")

        updated = repo.get_by_id(user.id)
        assert updated is not None
        assert updated.ntfy_topic == "my-topic"

    def test_update_ntfy_topic_to_none_clears_it(self, db_session):
        """Given a user with an ntfy_topic
        When I update the topic to None
        Then the topic is cleared.
        """
        repo = UserRepository(db_session)
        user = repo.create("dan")
        repo.update_ntfy_topic(user.id, "remove-me")

        repo.update_ntfy_topic(user.id, None)

        updated = repo.get_by_id(user.id)
        assert updated is not None
        assert updated.ntfy_topic is None

    def test_get_all_with_ntfy(self, db_session):
        """Given multiple users, some with ntfy_topic set
        When I call get_all_with_ntfy
        Then only users with a topic are returned.
        """
        repo = UserRepository(db_session)
        u1 = repo.create("user1")
        u2 = repo.create("user2")
        u3 = repo.create("user3")

        repo.update_ntfy_topic(u1.id, "topic-1")
        repo.update_ntfy_topic(u2.id, "topic-2")
        repo.update_ntfy_topic(u3.id, None)

        results = repo.get_all_with_ntfy()

        usernames = {u.username for u in results}
        assert "user1" in usernames
        assert "user2" in usernames
        assert "user3" not in usernames


# ---------------------------------------------------------------------------
# TestZoneRepository
# ---------------------------------------------------------------------------


class TestZoneRepository:
    """Feature: Per-user zone management"""

    def test_create_zone(self, db_session):
        """Given a user and zone parameters
        When I create a zone
        Then the zone is returned with an id and all fields set.
        """
        repo = ZoneRepository(db_session)

        zone = repo.create(
            user_id=1,
            name="Hackney",
            geometry='{"type":"Polygon","coordinates":[]}',
            centroid_lat=51.55,
            centroid_lng=-0.05,
            covering_radius_km=1.5,
            rightmove_id="REGION^123",
            openrent_term="Hackney",
            color_index=2,
        )

        assert zone.id > 0
        assert zone.name == "Hackney"
        assert zone.user_id == 1
        assert zone.rightmove_id == "REGION^123"
        assert zone.openrent_term == "Hackney"

    def test_zones_scoped_to_user(self, db_session):
        """Given zones created for different users
        When I call get_by_user
        Then only that user's zones are returned.
        """
        repo = ZoneRepository(db_session)
        _make_zone(db_session, user_id=1, name="Zone A")
        _make_zone(db_session, user_id=1, name="Zone B")
        _make_zone(db_session, user_id=2, name="Zone C")

        user1_zones = repo.get_by_user(1)
        user2_zones = repo.get_by_user(2)

        assert len(user1_zones) == 2
        assert len(user2_zones) == 1
        assert user2_zones[0].name == "Zone C"

    def test_get_all_returns_all_users_zones(self, db_session):
        """Given zones for multiple users
        When I call get_all
        Then all zones are returned.
        """
        repo = ZoneRepository(db_session)
        _make_zone(db_session, user_id=1, name="Zone A")
        _make_zone(db_session, user_id=2, name="Zone B")

        all_zones = repo.get_all()

        assert len(all_zones) == 2

    def test_get_by_id(self, db_session):
        """Given an existing zone
        When I retrieve it by id
        Then the correct zone is returned.
        """
        repo = ZoneRepository(db_session)
        zone = _make_zone(db_session)

        retrieved = repo.get_by_id(zone.id)

        assert retrieved is not None
        assert retrieved.name == zone.name

    def test_get_by_id_nonexistent_returns_none(self, db_session):
        """Given no zones
        When I get_by_id with a missing id
        Then None is returned.
        """
        repo = ZoneRepository(db_session)
        assert repo.get_by_id(9999) is None

    def test_update_zone(self, db_session):
        """Given an existing zone
        When I update its name
        Then the change is persisted.
        """
        repo = ZoneRepository(db_session)
        zone = _make_zone(db_session, name="Old Name")

        repo.update(zone.id, name="New Name")

        updated = repo.get_by_id(zone.id)
        assert updated is not None
        assert updated.name == "New Name"

    def test_delete_zone(self, db_session):
        """Given an existing zone
        When I delete it
        Then it can no longer be retrieved.
        """
        repo = ZoneRepository(db_session)
        zone = _make_zone(db_session)

        repo.delete(zone.id)

        assert repo.get_by_id(zone.id) is None


# ---------------------------------------------------------------------------
# TestListingZoneRepository
# ---------------------------------------------------------------------------


class TestListingZoneRepository:
    """Feature: Listing-zone associations"""

    def test_link_listing_to_zone(self, db_session):
        """Given a listing id and zone id
        When I call link
        Then get_zone_ids_for_listing returns the zone.
        """
        lz_repo = ListingZoneRepository(db_session)
        listing_repo = ListingRepository(db_session)
        zone = _make_zone(db_session)

        listing_repo.insert(_make_listing_dict("rm_10"))
        lz_repo.link("rm_10", zone.id)

        zone_ids = lz_repo.get_zone_ids_for_listing("rm_10")
        assert zone.id in zone_ids

    def test_duplicate_link_ignored(self, db_session):
        """Given a listing already linked to a zone
        When I call link again with the same ids
        Then no error is raised and no duplicate is created.
        """
        lz_repo = ListingZoneRepository(db_session)
        listing_repo = ListingRepository(db_session)
        zone = _make_zone(db_session)

        listing_repo.insert(_make_listing_dict("rm_20"))
        lz_repo.link("rm_20", zone.id)
        lz_repo.link("rm_20", zone.id)  # second call — must not raise

        zone_ids = lz_repo.get_zone_ids_for_listing("rm_20")
        assert zone_ids.count(zone.id) == 1

    def test_get_listing_ids_for_zones(self, db_session):
        """Given listings linked to zones
        When I call get_listing_ids_for_zones with one zone id
        Then all listings in that zone are returned.
        """
        lz_repo = ListingZoneRepository(db_session)
        listing_repo = ListingRepository(db_session)
        zone = _make_zone(db_session)

        listing_repo.insert(_make_listing_dict("rm_30"))
        listing_repo.insert(_make_listing_dict("rm_31"))
        lz_repo.link("rm_30", zone.id)
        lz_repo.link("rm_31", zone.id)

        listing_ids = lz_repo.get_listing_ids_for_zones([zone.id])

        assert set(listing_ids) == {"rm_30", "rm_31"}

    def test_get_listing_ids_for_zones_empty_list(self, db_session):
        """Given an empty zone_ids list
        When I call get_listing_ids_for_zones
        Then an empty list is returned.
        """
        lz_repo = ListingZoneRepository(db_session)
        assert lz_repo.get_listing_ids_for_zones([]) == []

    def test_delete_for_listings(self, db_session):
        """Given listings linked to zones
        When I delete associations for those listings
        Then the links are removed.
        """
        lz_repo = ListingZoneRepository(db_session)
        listing_repo = ListingRepository(db_session)
        zone = _make_zone(db_session)

        listing_repo.insert(_make_listing_dict("rm_40"))
        lz_repo.link("rm_40", zone.id)

        lz_repo.delete_for_listings(["rm_40"])

        assert lz_repo.get_zone_ids_for_listing("rm_40") == []


# ---------------------------------------------------------------------------
# TestListingRepository
# ---------------------------------------------------------------------------


class TestListingRepository:
    """Feature: Listing persistence"""

    def test_insert_new_listing_returns_true(self, db_session):
        """Given a new listing dict
        When I insert it
        Then True is returned.
        """
        repo = ListingRepository(db_session)
        assert repo.insert(_make_listing_dict("rm_50")) is True

    def test_insert_duplicate_listing_returns_false(self, db_session):
        """Given a listing that already exists
        When I insert it again with the same id
        Then False is returned.
        """
        repo = ListingRepository(db_session)
        repo.insert(_make_listing_dict("rm_60"))

        result = repo.insert(_make_listing_dict("rm_60"))

        assert result is False

    def test_get_by_id(self, db_session):
        """Given an inserted listing
        When I retrieve it by id
        Then the correct Listing domain object is returned.
        """
        repo = ListingRepository(db_session)
        repo.insert(_make_listing_dict("rm_70", source="openrent"))

        listing = repo.get_by_id("rm_70")

        assert listing is not None
        assert listing.id == "rm_70"
        assert listing.source == "openrent"

    def test_get_by_id_missing_returns_none(self, db_session):
        """Given an empty DB
        When I get_by_id for a non-existent listing
        Then None is returned.
        """
        repo = ListingRepository(db_session)
        assert repo.get_by_id("no_such") is None

    def test_get_all_with_state_filters_by_zones(self, db_session):
        """Given two listings, only one linked to a zone
        When I call get_all_with_state with that zone
        Then only the linked listing is returned.
        """
        listing_repo = ListingRepository(db_session)
        lz_repo = ListingZoneRepository(db_session)
        zone = _make_zone(db_session)

        listing_repo.insert(_make_listing_dict("rm_80"))
        listing_repo.insert(_make_listing_dict("rm_81"))
        lz_repo.link("rm_80", zone.id)

        results = listing_repo.get_all_with_state(user_id=1, zone_ids=[zone.id])

        ids = [r["id"] for r in results]
        assert "rm_80" in ids
        assert "rm_81" not in ids

    def test_get_all_with_state_includes_user_state(self, db_session):
        """Given a listing with a user state entry
        When I call get_all_with_state
        Then the state fields (seen, favourite) are included.
        """
        listing_repo = ListingRepository(db_session)
        state_repo = ListingStateRepository(db_session)
        lz_repo = ListingZoneRepository(db_session)
        zone = _make_zone(db_session)

        listing_repo.insert(_make_listing_dict("rm_90"))
        lz_repo.link("rm_90", zone.id)
        state_repo.upsert(1, "rm_90", {"seen": True, "favourite": True})

        results = listing_repo.get_all_with_state(user_id=1, zone_ids=[zone.id])

        assert len(results) == 1
        assert results[0]["seen"] is True
        assert results[0]["favourite"] is True

    def test_get_all_with_state_empty_zones_returns_empty(self, db_session):
        """Given listings in the DB
        When zone_ids is empty
        Then an empty list is returned.
        """
        repo = ListingRepository(db_session)
        repo.insert(_make_listing_dict("rm_100"))

        results = repo.get_all_with_state(user_id=1, zone_ids=[])

        assert results == []

    def test_archive_old_rearchives_listing_still_live_on_site(self, db_session):
        """Given a listing that was archived, then re-scraped because the site
        still advertises it, and has aged past the retention window again
        When archive_old runs a second time
        Then it must not raise and the listing is archived again.
        """
        repo = ListingRepository(db_session)
        stale = _make_listing_dict("rm_120")
        stale["first_seen"] = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=20)
        repo.insert(stale)
        db_session.commit()
        repo.archive_old(14)
        db_session.commit()

        # The site still lists it, so the scraper re-inserts it
        rescraped = _make_listing_dict("rm_120")
        rescraped["first_seen"] = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=20)
        rescraped["price_pcm"] = 1600
        repo.insert(rescraped)
        db_session.commit()

        archived = repo.archive_old(14)

        assert archived == ["rm_120"]
        assert repo.get_by_id("rm_120") is None


# ---------------------------------------------------------------------------
# TestListingStateRepository
# ---------------------------------------------------------------------------


class TestListingStateRepository:
    """Feature: Per-user listing state"""

    def test_upsert_creates_new_state(self, db_session):
        """Given no existing state
        When I upsert with seen=True
        Then a new state row is created.
        """
        listing_repo = ListingRepository(db_session)
        state_repo = ListingStateRepository(db_session)
        listing_repo.insert(_make_listing_dict("rm_200"))

        state = state_repo.upsert(1, "rm_200", {"seen": True})

        assert state.user_id == 1
        assert state.listing_id == "rm_200"
        assert state.seen is True

    def test_state_independent_per_user(self, db_session):
        """Given two users with state on the same listing
        When I retrieve each user's state
        Then the states are independent.
        """
        listing_repo = ListingRepository(db_session)
        state_repo = ListingStateRepository(db_session)
        listing_repo.insert(_make_listing_dict("rm_210"))

        state_repo.upsert(1, "rm_210", {"seen": True})
        state_repo.upsert(2, "rm_210", {"favourite": True})

        state1 = state_repo.get(1, "rm_210")
        state2 = state_repo.get(2, "rm_210")

        assert state1 is not None
        assert state1.seen is True
        assert state1.favourite is False
        assert state2 is not None
        assert state2.favourite is True
        assert state2.seen is False

    def test_upsert_updates_existing(self, db_session):
        """Given an existing state entry
        When I upsert with a changed field
        Then the field is updated, others unchanged.
        """
        listing_repo = ListingRepository(db_session)
        state_repo = ListingStateRepository(db_session)
        listing_repo.insert(_make_listing_dict("rm_220"))

        state_repo.upsert(1, "rm_220", {"seen": True, "notes": "interesting"})
        updated = state_repo.upsert(1, "rm_220", {"favourite": True})

        assert updated.seen is True  # preserved
        assert updated.favourite is True  # updated
        assert updated.notes == "interesting"  # preserved

    def test_get_returns_none_for_missing_state(self, db_session):
        """Given no state for a listing
        When I call get
        Then None is returned.
        """
        state_repo = ListingStateRepository(db_session)
        assert state_repo.get(1, "no_listing") is None

    def test_delete_for_listings_removes_state(self, db_session):
        """Given state entries for listings
        When I delete_for_listings
        Then those entries are removed.
        """
        listing_repo = ListingRepository(db_session)
        state_repo = ListingStateRepository(db_session)
        listing_repo.insert(_make_listing_dict("rm_230"))

        state_repo.upsert(1, "rm_230", {"seen": True})
        state_repo.delete_for_listings(["rm_230"])

        assert state_repo.get(1, "rm_230") is None


# ---------------------------------------------------------------------------
# TestPOIRepository
# ---------------------------------------------------------------------------


class TestPOIRepository:
    """Feature: Per-user POIs"""

    def test_create_poi(self, db_session):
        """Given user_id and location data
        When I create a POI
        Then it is returned with a valid id.
        """
        repo = POIRepository(db_session)

        poi = repo.create(user_id=1, name="Office", lat=51.5, lng=-0.1, color_index=0)

        assert poi.id > 0
        assert poi.name == "Office"
        assert poi.user_id == 1

    def test_pois_scoped_to_user(self, db_session):
        """Given POIs for two users
        When I call get_by_user
        Then only that user's POIs are returned.
        """
        repo = POIRepository(db_session)
        repo.create(user_id=1, name="A", lat=51.5, lng=-0.1, color_index=0)
        repo.create(user_id=1, name="B", lat=51.5, lng=-0.2, color_index=1)
        repo.create(user_id=2, name="C", lat=51.6, lng=-0.1, color_index=0)

        user1 = repo.get_by_user(1)
        user2 = repo.get_by_user(2)

        assert len(user1) == 2
        assert len(user2) == 1
        assert user2[0].name == "C"

    def test_get_all_returns_all_pois(self, db_session):
        """Given POIs for multiple users
        When I call get_all
        Then all POIs are returned.
        """
        repo = POIRepository(db_session)
        repo.create(user_id=1, name="A", lat=51.5, lng=-0.1, color_index=0)
        repo.create(user_id=2, name="B", lat=51.6, lng=-0.2, color_index=1)

        all_pois = repo.get_all()

        assert len(all_pois) == 2

    def test_delete_poi_cascades_commutes(self, db_session):
        """Given a POI with commute entries
        When I delete the POI
        Then both the POI and its commute rows are removed.
        """
        listing_repo = ListingRepository(db_session)
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)

        listing_repo.insert(_make_listing_dict("rm_300"))
        poi = poi_repo.create(user_id=1, name="Office", lat=51.5, lng=-0.1, color_index=0)
        commute_repo.upsert("rm_300", poi.id, 30)

        poi_repo.delete(poi.id)

        # POI gone
        assert poi_repo.get_by_user(1) == []
        # Commute also gone
        result = commute_repo.get_for_listings(["rm_300"])
        assert result == {}


# ---------------------------------------------------------------------------
# TestPOICommuteRepository
# ---------------------------------------------------------------------------


class TestPOICommuteRepository:
    """Feature: Commute tracking"""

    def test_upsert_commute(self, db_session):
        """Given a listing and POI
        When I upsert a commute time
        Then it is retrievable via get_for_listings.
        """
        listing_repo = ListingRepository(db_session)
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)

        listing_repo.insert(_make_listing_dict("rm_400"))
        poi = poi_repo.create(user_id=1, name="Office", lat=51.5, lng=-0.1, color_index=0)

        commute_repo.upsert("rm_400", poi.id, 25)

        result = commute_repo.get_for_listings(["rm_400"])
        assert result == {"rm_400": {poi.id: 25}}

    def test_upsert_updates_existing_commute(self, db_session):
        """Given an existing commute entry
        When I upsert with a new value
        Then the commute is updated.
        """
        listing_repo = ListingRepository(db_session)
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)

        listing_repo.insert(_make_listing_dict("rm_410"))
        poi = poi_repo.create(user_id=1, name="Library", lat=51.5, lng=-0.1, color_index=0)

        commute_repo.upsert("rm_410", poi.id, 20)
        commute_repo.upsert("rm_410", poi.id, 35)

        result = commute_repo.get_for_listings(["rm_410"])
        assert result["rm_410"][poi.id] == 35

    def test_get_for_listings(self, db_session):
        """Given commute data for several listings and POIs
        When I call get_for_listings
        Then a nested dict is returned keyed by listing_id then poi_id.
        """
        listing_repo = ListingRepository(db_session)
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)

        listing_repo.insert(_make_listing_dict("rm_420"))
        listing_repo.insert(_make_listing_dict("rm_421"))
        poi1 = poi_repo.create(user_id=1, name="POI1", lat=51.5, lng=-0.1, color_index=0)
        poi2 = poi_repo.create(user_id=1, name="POI2", lat=51.6, lng=-0.2, color_index=1)

        commute_repo.upsert("rm_420", poi1.id, 10)
        commute_repo.upsert("rm_420", poi2.id, 20)
        commute_repo.upsert("rm_421", poi1.id, 15)

        result = commute_repo.get_for_listings(["rm_420", "rm_421"])

        assert result["rm_420"] == {poi1.id: 10, poi2.id: 20}
        assert result["rm_421"] == {poi1.id: 15}

    def test_get_for_listings_empty_returns_empty(self, db_session):
        """Given an empty listing_ids list
        When I call get_for_listings
        Then an empty dict is returned.
        """
        commute_repo = POICommuteRepository(db_session)
        assert commute_repo.get_for_listings([]) == {}

    def test_get_listings_missing_poi(self, db_session):
        """Given two geolocated listings, one with a commute for a POI and one without
        When I call get_listings_missing_poi
        Then only the listing without a commute is returned.
        """
        listing_repo = ListingRepository(db_session)
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)

        listing_repo.insert(_make_listing_dict("rm_430", lat=51.5, lng=-0.1))
        listing_repo.insert(_make_listing_dict("rm_431", lat=51.6, lng=-0.2))
        poi = poi_repo.create(user_id=1, name="Gym", lat=51.5, lng=-0.1, color_index=0)

        commute_repo.upsert("rm_430", poi.id, 5)

        missing = commute_repo.get_listings_missing_poi(poi.id)

        ids = [m["id"] for m in missing]
        assert "rm_430" not in ids
        assert "rm_431" in ids

    def test_get_listings_missing_poi_excludes_no_coordinates(self, db_session):
        """Given a listing without coordinates
        When I call get_listings_missing_poi
        Then listings without lat/lng are excluded.
        """
        listing_repo = ListingRepository(db_session)
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)

        listing_repo.insert(_make_listing_dict("rm_440", lat=None, lng=None))
        poi = poi_repo.create(user_id=1, name="Park", lat=51.5, lng=-0.1, color_index=0)

        missing = commute_repo.get_listings_missing_poi(poi.id)

        assert all(m["id"] != "rm_440" for m in missing)

    def test_delete_for_listings_removes_commutes(self, db_session):
        """Given commute entries for a listing
        When I call delete_for_listings
        Then those commute rows are removed.
        """
        listing_repo = ListingRepository(db_session)
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)

        listing_repo.insert(_make_listing_dict("rm_450"))
        poi = poi_repo.create(user_id=1, name="Cafe", lat=51.5, lng=-0.1, color_index=0)
        commute_repo.upsert("rm_450", poi.id, 12)

        commute_repo.delete_for_listings(["rm_450"])

        result = commute_repo.get_for_listings(["rm_450"])
        assert result == {}
