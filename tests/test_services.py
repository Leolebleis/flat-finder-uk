"""Unit tests for service layer business logic.

Services are tested with real repository implementations backed by a test SQLite DB,
as set up by the conftest fixtures. No mocks — the business logic is the subject
under test, not the data access.
"""

from datetime import UTC, datetime
from typing import Any

from flat_finder.listings.persistence import ListingRepository, ListingStateRepository
from flat_finder.listings.service import ListingService, _compute_scores, _min_commute
from flat_finder.pois.persistence import POICommuteRepository, POIRepository
from flat_finder.pois.service import POIService
from flat_finder.users.persistence import UserRepository
from flat_finder.users.service import UserService
from flat_finder.zones.persistence import ListingZoneRepository, ZoneRepository
from flat_finder.zones.service import ZoneService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_listing_dict(  # noqa: PLR0913
    listing_id: str = "rm_1",
    source: str = "rightmove",
    price_pcm: int | None = 1500,
    sqft: int | None = None,
    lat: float | None = 51.5,
    lng: float | None = -0.1,
) -> dict[str, Any]:
    return {
        "id": listing_id,
        "source": source,
        "url": f"https://example.com/{listing_id}",
        "title": "Nice flat",
        "address": "1 Test Street, London",
        "price_pcm": price_pcm,
        "bedrooms": 2,
        "sqft": sqft,
        "latitude": lat,
        "longitude": lng,
        "first_seen": datetime.now(UTC).replace(tzinfo=None),
        "has_dishwasher": "unknown",
        "has_washer": "unknown",
        "has_outdoor": "unknown",
    }


def _insert_listing(session, **kwargs: Any) -> str:
    repo = ListingRepository(session)
    d = _make_listing_dict(**kwargs)
    repo.insert(d)
    return d["id"]


def _make_zone(session, user_id: int = 1, name: str = "Zone A") -> object:
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
        color_index=0,
    )


def _link_listing_to_zone(session, listing_id: str, zone_id: int) -> None:
    ListingZoneRepository(session).link(listing_id, zone_id)


# ---------------------------------------------------------------------------
# TestUserServiceLogin
# ---------------------------------------------------------------------------


class TestUserServiceLogin:
    """Feature: User login"""

    def test_login_existing_user(self, db_session):
        """Given a user that already exists in the DB
        When I call login with their username
        Then the existing user is returned (no duplicate created).
        """
        repo = UserRepository(db_session)
        repo.create("alice")

        svc = UserService(repo)
        user = svc.login("alice")

        assert user.username == "alice"
        assert repo.get_by_username("alice") is not None

    def test_login_new_user_creates_account(self, db_session):
        """Given a username that does not exist
        When I call login
        Then a new user is created and returned.
        """
        repo = UserRepository(db_session)
        svc = UserService(repo)

        user = svc.login("bob")

        assert user.username == "bob"
        assert user.id is not None
        assert repo.get_by_username("bob") is not None

    def test_login_normalizes_username(self, db_session):
        """Given a username with mixed case
        When I call login
        Then the stored username is lowercased.
        """
        repo = UserRepository(db_session)
        svc = UserService(repo)

        user = svc.login("Alice")

        assert user.username == "alice"

    def test_login_empty_spaces_normalized(self, db_session):
        """Given a username with surrounding whitespace
        When I call login
        Then the stored username has whitespace stripped and is lowercased.
        """
        repo = UserRepository(db_session)
        svc = UserService(repo)

        user = svc.login("  Carol  ")

        assert user.username == "carol"

    def test_login_returns_same_user_on_repeated_calls(self, db_session):
        """Given the same username used to log in twice
        When I call login twice
        Then both calls return the same user ID.
        """
        repo = UserRepository(db_session)
        svc = UserService(repo)

        first = svc.login("dave")
        second = svc.login("dave")

        assert first.id == second.id

    def test_get_by_id_returns_user(self, db_session):
        """Given a user created in the DB
        When I call get_by_id with their ID
        Then the correct user is returned.
        """
        repo = UserRepository(db_session)
        svc = UserService(repo)
        created = svc.login("eve")

        retrieved = svc.get_by_id(created.id)

        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.username == "eve"

    def test_get_by_id_unknown_returns_none(self, db_session):
        """Given a user ID that does not exist
        When I call get_by_id
        Then None is returned.
        """
        repo = UserRepository(db_session)
        svc = UserService(repo)

        result = svc.get_by_id(9999)

        assert result is None

    def test_update_ntfy_topic_sets_value(self, db_session):
        """Given an existing user
        When I update their ntfy_topic
        Then the stored topic matches.
        """
        repo = UserRepository(db_session)
        svc = UserService(repo)
        user = svc.login("frank")

        svc.update_ntfy_topic(user.id, "my-topic")

        updated = svc.get_by_id(user.id)
        assert updated is not None
        assert updated.ntfy_topic == "my-topic"

    def test_update_ntfy_topic_strips_whitespace(self, db_session):
        """Given a topic with surrounding whitespace
        When I update ntfy_topic
        Then the stored value is stripped.
        """
        repo = UserRepository(db_session)
        svc = UserService(repo)
        user = svc.login("grace")

        svc.update_ntfy_topic(user.id, "  topic  ")

        updated = svc.get_by_id(user.id)
        assert updated is not None
        assert updated.ntfy_topic == "topic"

    def test_update_ntfy_topic_empty_string_becomes_none(self, db_session):
        """Given an empty string topic
        When I update ntfy_topic
        Then the stored value is None (empty string coerced).
        """
        repo = UserRepository(db_session)
        svc = UserService(repo)
        user = svc.login("henry")

        svc.update_ntfy_topic(user.id, "")

        updated = svc.get_by_id(user.id)
        assert updated is not None
        assert updated.ntfy_topic is None


# ---------------------------------------------------------------------------
# TestListingServiceScoring
# ---------------------------------------------------------------------------


class TestListingServiceScoring:
    """Feature: Weighted match scoring"""

    def test_no_pois_means_no_score(self, db_session):
        """Given listings with commute data but no POIs provided
        When get_feed_data is called with an empty POI list
        Then all listings have match_score=None.
        """
        user_repo = UserRepository(db_session)
        user = user_repo.create("user1")
        zone = _make_zone(db_session, user_id=user.id)
        listing_id = _insert_listing(db_session, listing_id="rm_score_1")
        _link_listing_to_zone(db_session, listing_id, zone.id)

        svc = ListingService(
            ListingRepository(db_session),
            ListingStateRepository(db_session),
            POICommuteRepository(db_session),
        )

        result = svc.get_feed_data(user.id, [zone.id], pois=[])

        assert len(result["listings"]) == 1
        assert result["listings"][0]["match_score"] is None

    def test_score_computed_from_poi_commutes(self, db_session):
        """Given two listings with different commute times to the same POI
        When get_feed_data is called
        Then the listing with the shorter commute gets a higher match_score.
        """
        user_repo = UserRepository(db_session)
        user = user_repo.create("user2")
        zone = _make_zone(db_session, user_id=user.id)

        listing_a_id = _insert_listing(db_session, listing_id="rm_a", price_pcm=1500)
        listing_b_id = _insert_listing(db_session, listing_id="rm_b", price_pcm=1600)
        _link_listing_to_zone(db_session, listing_a_id, zone.id)
        _link_listing_to_zone(db_session, listing_b_id, zone.id)

        poi_repo = POIRepository(db_session)
        poi = poi_repo.create(user.id, "Office", 51.5, -0.1, 0)
        commute_repo = POICommuteRepository(db_session)
        commute_repo.upsert(listing_a_id, poi.id, 10)  # shorter
        commute_repo.upsert(listing_b_id, poi.id, 40)  # longer

        svc = ListingService(
            ListingRepository(db_session),
            ListingStateRepository(db_session),
            commute_repo,
        )
        pois_dicts = [{"id": poi.id, "name": poi.name, "color_index": poi.color_index}]

        result = svc.get_feed_data(user.id, [zone.id], pois=pois_dicts)

        listings_by_id = {lst["id"]: lst for lst in result["listings"]}
        assert listings_by_id[listing_a_id]["match_score"] > listings_by_id[listing_b_id]["match_score"]

    def test_equal_weights_by_default(self):
        """Given two POIs and a single listing with equal commute times
        When scores are computed with default weights
        Then the score equals 100 (both POIs at minimum = max score).

        With a single listing val == min for each POI, so each term = w * 100 * 1.
        Two equal-weight POIs: 0.5*100 + 0.5*100 = 100.
        """
        listings: list[dict[str, Any]] = [
            {"id": "x", "poi_commutes": {1: 30, 2: 20}},
        ]
        _compute_scores(listings, poi_ids=[1, 2])
        assert listings[0]["match_score"] == 100

    def test_listing_missing_commute_for_one_poi_scored_partially(self):
        """Given a listing that has commute data for only one of two POIs
        When scores are computed
        Then the missing POI contributes 0 to the score.
        """
        listings: list[dict[str, Any]] = [
            {"id": "has_both", "poi_commutes": {1: 10, 2: 10}},
            {"id": "has_one", "poi_commutes": {1: 10}},  # no commute for POI 2
        ]
        _compute_scores(listings, poi_ids=[1, 2])
        # has_both gets a full 100; has_one gets only the contribution from POI 1
        assert listings[0]["match_score"] == 100
        assert listings[1]["match_score"] == 50  # 0.5 * 100 * 1 (POI 1 only)

    def test_min_commute_helper(self):
        """Given a listing with multiple POI commutes
        When _min_commute is called
        Then the minimum value across all POIs is returned.
        """
        listing = {"poi_commutes": {1: 30, 2: 15, 3: 45}}
        assert _min_commute(listing) == 15

    def test_min_commute_no_data_returns_none(self):
        """Given a listing with no POI commutes
        When _min_commute is called
        Then None is returned.
        """
        listing: dict[str, Any] = {"poi_commutes": {}}
        assert _min_commute(listing) is None


# ---------------------------------------------------------------------------
# TestListingServiceSorting
# ---------------------------------------------------------------------------


class TestListingServiceSorting:
    """Feature: Feed sorting"""

    def _make_svc(self, db_session: Any) -> tuple[ListingService, Any, Any]:
        user_repo = UserRepository(db_session)
        user = user_repo.create("sorter")
        zone = _make_zone(db_session, user_id=user.id, name="Sort Zone")
        return (
            ListingService(
                ListingRepository(db_session),
                ListingStateRepository(db_session),
                POICommuteRepository(db_session),
            ),
            user,
            zone,
        )

    def test_sort_by_price_ascending(self, db_session):
        """Given three listings with prices 2000, 1000, 1500
        When sorted by price_asc
        Then listings are in ascending price order.
        """
        svc, user, zone = self._make_svc(db_session)
        for lid, price in [("p1", 2000), ("p2", 1000), ("p3", 1500)]:
            _insert_listing(db_session, listing_id=lid, price_pcm=price)
            _link_listing_to_zone(db_session, lid, zone.id)

        result = svc.get_feed_data(user.id, [zone.id], pois=[], sort="price_asc")

        prices = [lst["price_pcm"] for lst in result["listings"]]
        assert prices == sorted(prices)

    def test_sort_by_price_descending(self, db_session):
        """Given three listings with prices 2000, 1000, 1500
        When sorted by price_desc
        Then listings are in descending price order.
        """
        svc, user, zone = self._make_svc(db_session)
        for lid, price in [("pd1", 2000), ("pd2", 1000), ("pd3", 1500)]:
            _insert_listing(db_session, listing_id=lid, price_pcm=price)
            _link_listing_to_zone(db_session, lid, zone.id)

        result = svc.get_feed_data(user.id, [zone.id], pois=[], sort="price_desc")

        prices = [lst["price_pcm"] for lst in result["listings"]]
        assert prices == sorted(prices, reverse=True)

    def test_sort_by_size_desc(self, db_session):
        """Given three listings with sqft 600, 900, 750
        When sorted by size_desc
        Then listings are in descending size order.
        """
        svc, user, zone = self._make_svc(db_session)
        for lid, sqft in [("s1", 600), ("s2", 900), ("s3", 750)]:
            _insert_listing(db_session, listing_id=lid, sqft=sqft)
            _link_listing_to_zone(db_session, lid, zone.id)

        result = svc.get_feed_data(user.id, [zone.id], pois=[], sort="size_desc")

        sizes = [lst["sqft"] for lst in result["listings"]]
        assert sizes == sorted(sizes, reverse=True)

    def test_sort_by_best_match(self, db_session):
        """Given two listings where one has a better commute score
        When sorted by best_match
        Then the higher-scoring listing comes first.
        """
        svc, user, zone = self._make_svc(db_session)
        poi_repo = POIRepository(db_session)
        poi = poi_repo.create(user.id, "Work", 51.5, -0.1, 0)
        commute_repo = POICommuteRepository(db_session)

        _insert_listing(db_session, listing_id="bm_near", price_pcm=2000)
        _insert_listing(db_session, listing_id="bm_far", price_pcm=1000)
        _link_listing_to_zone(db_session, "bm_near", zone.id)
        _link_listing_to_zone(db_session, "bm_far", zone.id)
        commute_repo.upsert("bm_near", poi.id, 5)  # very short commute
        commute_repo.upsert("bm_far", poi.id, 60)  # long commute

        pois_dicts = [{"id": poi.id, "name": poi.name, "color_index": poi.color_index}]
        result = svc.get_feed_data(user.id, [zone.id], pois=pois_dicts, sort="best_match")

        ids = [lst["id"] for lst in result["listings"]]
        assert ids[0] == "bm_near"

    def test_invalid_sort_falls_back_to_newest(self, db_session):
        """Given an unrecognized sort value
        When get_feed_data is called
        Then the sort falls back to 'newest' without raising.
        """
        svc, user, zone = self._make_svc(db_session)
        _insert_listing(db_session, listing_id="ns1")
        _link_listing_to_zone(db_session, "ns1", zone.id)

        result = svc.get_feed_data(user.id, [zone.id], pois=[], sort="nonexistent_sort")

        assert result["sort"] == "newest"
        assert len(result["listings"]) == 1


# ---------------------------------------------------------------------------
# TestListingServiceDetail
# ---------------------------------------------------------------------------


class TestListingServiceDetail:
    """Feature: Listing detail page data"""

    def test_detail_returns_none_for_unknown_listing(self, db_session):
        """Given a listing ID that does not exist
        When get_detail_data is called
        Then None is returned.
        """
        svc = ListingService(
            ListingRepository(db_session),
            ListingStateRepository(db_session),
            POICommuteRepository(db_session),
        )

        result = svc.get_detail_data(user_id=1, listing_id="nonexistent", pois=[])

        assert result is None

    def test_detail_returns_listing_with_no_state(self, db_session):
        """Given an existing listing with no user state
        When get_detail_data is called
        Then seen=False, favourite=False, notes=None.
        """
        listing_id = _insert_listing(db_session, listing_id="d1")
        svc = ListingService(
            ListingRepository(db_session),
            ListingStateRepository(db_session),
            POICommuteRepository(db_session),
        )

        result = svc.get_detail_data(user_id=1, listing_id=listing_id, pois=[])

        assert result is not None
        listing = result["listing"]
        assert listing["seen"] is False
        assert listing["favourite"] is False
        assert listing["notes"] is None

    def test_detail_applies_override_fields(self, db_session):
        """Given a listing with has_dishwasher='no' and a user override of 'yes'
        When get_detail_data is called
        Then has_dishwasher is 'yes' (override applied) and original_dishwasher is 'no'.
        """
        listing_id = _insert_listing(db_session, listing_id="override1")
        state_repo = ListingStateRepository(db_session)
        state_repo.upsert(1, listing_id, {"override_dishwasher": "yes"})

        svc = ListingService(
            ListingRepository(db_session),
            state_repo,
            POICommuteRepository(db_session),
        )

        result = svc.get_detail_data(user_id=1, listing_id=listing_id, pois=[])

        assert result is not None
        listing = result["listing"]
        assert listing["has_dishwasher"] == "yes"
        assert listing["original_dishwasher"] == "unknown"


# ---------------------------------------------------------------------------
# TestListingServiceUpdateState
# ---------------------------------------------------------------------------


class TestListingServiceUpdateState:
    """Feature: Listing state updates"""

    def test_update_state_marks_listing_seen(self, db_session):
        """Given an existing listing
        When update_state is called with seen=True
        Then the stored state has seen=True.
        """
        listing_id = _insert_listing(db_session, listing_id="us1")
        svc = ListingService(
            ListingRepository(db_session),
            ListingStateRepository(db_session),
            POICommuteRepository(db_session),
        )

        result = svc.update_state(user_id=1, listing_id=listing_id, updates={"seen": True})

        assert result["seen"] is True

    def test_update_state_partial_update(self, db_session):
        """Given a listing state with seen=True
        When update_state is called with only favourite=True
        Then seen is preserved and favourite is set.
        """
        listing_id = _insert_listing(db_session, listing_id="us2")
        state_repo = ListingStateRepository(db_session)
        state_repo.upsert(1, listing_id, {"seen": True})

        svc = ListingService(
            ListingRepository(db_session),
            state_repo,
            POICommuteRepository(db_session),
        )

        result = svc.update_state(user_id=1, listing_id=listing_id, updates={"favourite": True})

        assert result["seen"] is True
        assert result["favourite"] is True


# ---------------------------------------------------------------------------
# TestZoneServiceOwnership
# ---------------------------------------------------------------------------


class TestZoneServiceOwnership:
    """Feature: Zone ownership enforcement"""

    def test_delete_own_zone_succeeds(self, db_session):
        """Given a zone owned by user A
        When user A deletes it
        Then delete_zone returns True and the zone is gone.
        """
        zone_repo = ZoneRepository(db_session)
        zone = zone_repo.create(
            user_id=1,
            name="My Zone",
            geometry='{"type":"Polygon","coordinates":[]}',
            centroid_lat=51.5,
            centroid_lng=-0.1,
            covering_radius_km=1.0,
            rightmove_id=None,
            openrent_term=None,
            color_index=0,
        )
        svc = ZoneService(zone_repo)

        deleted = svc.delete_zone(user_id=1, zone_id=zone.id)

        assert deleted is True
        assert zone_repo.get_by_id(zone.id) is None

    def test_delete_other_users_zone_fails(self, db_session):
        """Given a zone owned by user A
        When user B attempts to delete it
        Then delete_zone returns False and the zone still exists.
        """
        zone_repo = ZoneRepository(db_session)
        zone = zone_repo.create(
            user_id=1,
            name="User A Zone",
            geometry='{"type":"Polygon","coordinates":[]}',
            centroid_lat=51.5,
            centroid_lng=-0.1,
            covering_radius_km=1.0,
            rightmove_id=None,
            openrent_term=None,
            color_index=0,
        )
        svc = ZoneService(zone_repo)

        deleted = svc.delete_zone(user_id=2, zone_id=zone.id)

        assert deleted is False
        assert zone_repo.get_by_id(zone.id) is not None

    def test_delete_nonexistent_zone_returns_false(self, db_session):
        """Given a zone ID that does not exist
        When delete_zone is called
        Then False is returned.
        """
        zone_repo = ZoneRepository(db_session)
        svc = ZoneService(zone_repo)

        deleted = svc.delete_zone(user_id=1, zone_id=9999)

        assert deleted is False

    def test_update_own_zone_succeeds(self, db_session):
        """Given a zone owned by user A
        When user A updates its name
        Then update_zone returns True.
        """
        zone_repo = ZoneRepository(db_session)
        zone = zone_repo.create(
            user_id=1,
            name="Old Name",
            geometry='{"type":"Polygon","coordinates":[]}',
            centroid_lat=51.5,
            centroid_lng=-0.1,
            covering_radius_km=1.0,
            rightmove_id=None,
            openrent_term=None,
            color_index=0,
        )
        svc = ZoneService(zone_repo)

        updated = svc.update_zone(user_id=1, zone_id=zone.id, name="New Name")

        assert updated is True

    def test_update_other_users_zone_fails(self, db_session):
        """Given a zone owned by user A
        When user B attempts to update it
        Then update_zone returns False.
        """
        zone_repo = ZoneRepository(db_session)
        zone = zone_repo.create(
            user_id=1,
            name="Protected Zone",
            geometry='{"type":"Polygon","coordinates":[]}',
            centroid_lat=51.5,
            centroid_lng=-0.1,
            covering_radius_km=1.0,
            rightmove_id=None,
            openrent_term=None,
            color_index=0,
        )
        svc = ZoneService(zone_repo)

        updated = svc.update_zone(user_id=2, zone_id=zone.id, name="Stolen Name")

        assert updated is False

    def test_create_zone_auto_assigns_color(self, db_session):
        """Given a user with no existing zones
        When create_zone is called
        Then the returned dict includes a 'color' dict from POI_COLORS.
        """
        zone_repo = ZoneRepository(db_session)
        svc = ZoneService(zone_repo)

        zone_dict = svc.create_zone(
            user_id=1,
            name="Colorful Zone",
            geometry='{"type":"Polygon","coordinates":[]}',
            centroid_lat=51.5,
            centroid_lng=-0.1,
            covering_radius_km=1.0,
            rightmove_id=None,
            openrent_term=None,
        )

        assert "color" in zone_dict
        assert "color" in zone_dict["color"]  # the color dict has a 'color' key (hex string)

    def test_get_user_zones_includes_color(self, db_session):
        """Given a user with an existing zone
        When get_user_zones is called
        Then each zone dict has a 'color' key attached.
        """
        zone_repo = ZoneRepository(db_session)
        zone_repo.create(
            user_id=1,
            name="Zone With Color",
            geometry='{"type":"Polygon","coordinates":[]}',
            centroid_lat=51.5,
            centroid_lng=-0.1,
            covering_radius_km=1.0,
            rightmove_id=None,
            openrent_term=None,
            color_index=2,
        )
        svc = ZoneService(zone_repo)

        zones = svc.get_user_zones(user_id=1)

        assert len(zones) == 1
        assert "color" in zones[0]


# ---------------------------------------------------------------------------
# TestPOIServiceOwnership
# ---------------------------------------------------------------------------


class TestPOIServiceOwnership:
    """Feature: POI ownership enforcement"""

    def test_delete_own_poi_succeeds(self, db_session):
        """Given a POI owned by user A
        When user A deletes it
        Then delete_poi returns True and the POI is gone.
        """
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)
        poi = poi_repo.create(user_id=1, name="Office", lat=51.5, lng=-0.1, color_index=0)
        svc = POIService(poi_repo, commute_repo)

        deleted = svc.delete_poi(user_id=1, poi_id=poi.id)

        assert deleted is True
        assert not poi_repo.get_by_user(1)

    def test_delete_other_users_poi_fails(self, db_session):
        """Given a POI owned by user A
        When user B attempts to delete it
        Then delete_poi returns False and the POI still exists.
        """
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)
        poi = poi_repo.create(user_id=1, name="User A POI", lat=51.5, lng=-0.1, color_index=0)
        svc = POIService(poi_repo, commute_repo)

        deleted = svc.delete_poi(user_id=2, poi_id=poi.id)

        assert deleted is False
        assert len(poi_repo.get_by_user(1)) == 1

    def test_delete_nonexistent_poi_returns_false(self, db_session):
        """Given a POI ID that does not exist
        When delete_poi is called
        Then False is returned.
        """
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)
        svc = POIService(poi_repo, commute_repo)

        deleted = svc.delete_poi(user_id=1, poi_id=9999)

        assert deleted is False

    def test_add_poi_auto_assigns_color(self, db_session):
        """Given a user with no existing POIs
        When add_poi is called
        Then the returned dict includes a 'color' dict from POI_COLORS.
        """
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)
        svc = POIService(poi_repo, commute_repo)

        poi_dict = svc.add_poi(user_id=1, name="Gym", lat=51.5, lng=-0.1)

        assert "color" in poi_dict
        assert "color" in poi_dict["color"]

    def test_add_poi_increments_color_index(self, db_session):
        """Given a user with one existing POI at color_index 0
        When add_poi is called again
        Then the new POI gets color_index 1.
        """
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)
        svc = POIService(poi_repo, commute_repo)

        first = svc.add_poi(user_id=1, name="First", lat=51.5, lng=-0.1)
        second = svc.add_poi(user_id=1, name="Second", lat=51.5, lng=-0.1)

        assert first["color_index"] == 0
        assert second["color_index"] == 1

    def test_get_user_pois_includes_color(self, db_session):
        """Given a user with an existing POI
        When get_user_pois is called
        Then each POI dict has a 'color' key attached.
        """
        poi_repo = POIRepository(db_session)
        poi_repo.create(user_id=1, name="Park", lat=51.5, lng=-0.1, color_index=3)
        commute_repo = POICommuteRepository(db_session)
        svc = POIService(poi_repo, commute_repo)

        pois = svc.get_user_pois(user_id=1)

        assert len(pois) == 1
        assert "color" in pois[0]

    def test_delete_poi_cascades_commutes(self, db_session):
        """Given a POI with commute records for some listings
        When the POI is deleted via POIService
        Then the commute records are also removed.
        """
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)
        listing_id = _insert_listing(db_session, listing_id="cascade_l1")
        poi = poi_repo.create(user_id=1, name="Cascade POI", lat=51.5, lng=-0.1, color_index=0)
        commute_repo.upsert(listing_id, poi.id, 20)

        svc = POIService(poi_repo, commute_repo)
        svc.delete_poi(user_id=1, poi_id=poi.id)

        # After deletion, commutes for this POI should be gone
        commutes = commute_repo.get_for_listings([listing_id])
        assert poi.id not in commutes.get(listing_id, {})
