"""Tests for the new flat_finder scraper (runner.py).

All external HTTP calls (Rightmove, OpenRent, TfL, ntfy) are mocked.
Uses a real SQLite DB via the conftest db_session fixture.
"""
import json
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from flat_finder.listings.persistence import (
    ListingArchiveDB,
    ListingDB,
    ListingRepository,
    ListingStateDB,
    ListingStateRepository,
    ScraperStateDB,
)
from flat_finder.pois.persistence import POICommuteDB, POICommuteRepository, POIRepository
from flat_finder.scraper.runner import (
    PRUNE_AFTER_DAYS,
    _filter_listings_by_zone,
    _listing_fingerprint,
    _normalize_address,
    run,
)
from flat_finder.users.persistence import UserRepository
from flat_finder.zones.persistence import ListingZoneDB, ListingZoneRepository, ZoneRepository
from sqlalchemy.orm import sessionmaker

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_listing_dict(  # noqa: PLR0913
    listing_id: str = "rightmove_1",
    source: str = "rightmove",
    lat: float | None = 51.55,
    lng: float | None = -0.18,
    price: int = 1800,
    address: str = "1 Test Street, NW6",
) -> dict:
    return {
        "id": listing_id,
        "source": source,
        "url": f"https://example.com/{listing_id}",
        "title": "Nice flat",
        "price_pcm": price,
        "bedrooms": 2,
        "address": address,
        "latitude": lat,
        "longitude": lng,
        "description": "A nice flat",
        "image_url": None,
        "property_type": "flat",
        "furnishing": "Furnished",
        "sqft": None,
        "has_dishwasher": "unknown",
        "has_washer": "unknown",
        "has_outdoor": "unknown",
        "outdoor_type": None,
        "zone": None,
        "first_seen": datetime.now(UTC).isoformat(),
        "listing_date": None,
    }


# Zone polygon that covers lat 51.54-51.56, lng -0.19 to -0.17
ZONE_GEOM = json.dumps(
    {
        "type": "Polygon",
        "coordinates": [[[-0.19, 51.54], [-0.17, 51.54], [-0.17, 51.56], [-0.19, 51.56], [-0.19, 51.54]]],
    }
)


def _create_user_with_zone(db_session, username: str, ntfy_topic: str | None = None) -> tuple:
    """Create a user and a zone. Returns (user, zone)."""
    user_repo = UserRepository(db_session)
    zone_repo = ZoneRepository(db_session)

    user = user_repo.create(username)
    if ntfy_topic:
        user_repo.update_ntfy_topic(user.id, ntfy_topic)
        user = user_repo.get_by_id(user.id)

    zone = zone_repo.create(
        user_id=user.id,
        name=f"{username}-zone",
        geometry=ZONE_GEOM,
        centroid_lat=51.55,
        centroid_lng=-0.18,
        covering_radius_km=2.0,
        rightmove_id="OUTCODE^2171",
        openrent_term="NW6",
        color_index=0,
    )
    db_session.commit()
    return user, zone


def _make_session_factory(db_session):
    return sessionmaker(bind=db_session.bind)


def _scraper_run_mocked(
    db_session,
    rm_listings: list | None = None,
    or_listings: list | None = None,
    tfl_mins: int | None = None,
):
    """Run the scraper with all external HTTP mocked. Returns the mock_ntfy object."""
    if rm_listings is None:
        rm_listings = []
    if or_listings is None:
        or_listings = []

    with (
        patch("flat_finder.scraper.runner.fetch_rightmove", return_value=rm_listings),
        patch("flat_finder.scraper.runner.fetch_openrent", return_value=or_listings),
        patch("flat_finder.scraper.runner.tfl_journey_mins", return_value=tfl_mins),
        patch("flat_finder.scraper.runner.send_ntfy") as mock_ntfy,
        patch("flat_finder.scraper.runner.send_email"),
        patch("flat_finder.scraper.runner.get_engine") as mock_engine,
        patch("flat_finder.scraper.runner.get_session") as mock_get_session,
        patch("flat_finder.database.Base.metadata.create_all"),
    ):
        mock_engine.return_value = db_session.bind
        mock_get_session.return_value = _make_session_factory(db_session)
        run()
    return mock_ntfy


# ---------------------------------------------------------------------------
# Pure-function tests (no DB needed)
# ---------------------------------------------------------------------------


class TestNormalizeAddress:
    def test_strips_london_and_punctuation(self):
        assert _normalize_address("Goldhurst Terrace, London, NW6") == "goldhurst terrace nw6"
        assert _normalize_address("Goldhurst Terrace, NW6") == "goldhurst terrace nw6"


class TestListingFingerprint:
    def test_matches_cross_source(self):
        rm = _make_listing_dict("rightmove_1")
        rm["address"] = "Goldhurst Terrace, London, NW6"
        rm["price_pcm"] = 2100
        rm["bedrooms"] = 1

        orr = _make_listing_dict("openrent_1")
        orr["address"] = "Goldhurst Terrace, NW6"
        orr["price_pcm"] = 2100
        orr["bedrooms"] = 1

        assert _listing_fingerprint(rm) == _listing_fingerprint(orr)

    def test_differs_on_price(self):
        a = _make_listing_dict("rm_1", price=2100)
        b = _make_listing_dict("or_1", price=1800)
        assert _listing_fingerprint(a) != _listing_fingerprint(b)

    def test_none_when_missing_fields(self):
        listing = _make_listing_dict("rm_1")
        listing["address"] = None
        assert _listing_fingerprint(listing) is None


class TestFilterListingsByZone:
    def test_keeps_listing_inside(self):
        listing = _make_listing_dict("rm_1", lat=51.55, lng=-0.18)
        result = _filter_listings_by_zone([listing], ZONE_GEOM)
        assert len(result) == 1

    def test_removes_listing_outside(self):
        listing = _make_listing_dict("rm_1", lat=52.0, lng=-0.18)
        result = _filter_listings_by_zone([listing], ZONE_GEOM)
        assert len(result) == 0

    def test_keeps_listing_without_coords(self):
        listing = _make_listing_dict("rm_1", lat=None, lng=None)
        result = _filter_listings_by_zone([listing], ZONE_GEOM)
        assert len(result) == 1

    def test_no_filter_when_no_geometry(self):
        listing = _make_listing_dict("rm_1", lat=99.0, lng=99.0)
        result = _filter_listings_by_zone([listing], None)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# TestListingZonesPopulation
# ---------------------------------------------------------------------------


class TestListingZonesPopulation:
    """Feature: Scraper tags listings with zones"""

    def test_new_listing_gets_listing_zone_row(self, db_session):
        """Given zone X exists
        When the scraper finds a new listing in zone X
        Then a listing_zones(listing_id, zone_id) row is created
        """
        _, zone = _create_user_with_zone(db_session, "leo", ntfy_topic=None)

        listing = _make_listing_dict("rightmove_100", lat=51.55, lng=-0.18)

        _scraper_run_mocked(db_session, rm_listings=[listing])

        listing_zone_repo = ListingZoneRepository(db_session)
        zone_ids = listing_zone_repo.get_zone_ids_for_listing("rightmove_100")
        assert zone.id in zone_ids

    def test_deduped_listing_still_gets_zone_link(self, db_session):
        """Given listing Y already exists (found via zone A)
        When zone B also finds listing Y
        Then listing_zones gets rows for both (Y, A) and (Y, B)
        """
        user_repo = UserRepository(db_session)
        zone_repo = ZoneRepository(db_session)

        user = user_repo.create("leo")

        zone_a = zone_repo.create(
            user_id=user.id,
            name="zone-a",
            geometry=ZONE_GEOM,
            centroid_lat=51.55,
            centroid_lng=-0.18,
            covering_radius_km=2.0,
            rightmove_id="RM_A",
            openrent_term="NW6",
            color_index=0,
        )
        zone_b = zone_repo.create(
            user_id=user.id,
            name="zone-b",
            geometry=ZONE_GEOM,
            centroid_lat=51.55,
            centroid_lng=-0.18,
            covering_radius_km=2.0,
            rightmove_id="RM_B",
            openrent_term="NW7",
            color_index=1,
        )
        db_session.commit()

        listing = _make_listing_dict("rightmove_200", lat=51.55, lng=-0.18)

        # Both zones return the same listing
        with (
            patch("flat_finder.scraper.runner.fetch_rightmove", return_value=[listing]),
            patch("flat_finder.scraper.runner.fetch_openrent", return_value=[]),
            patch("flat_finder.scraper.runner.tfl_journey_mins", return_value=None),
            patch("flat_finder.scraper.runner.send_ntfy"),
            patch("flat_finder.scraper.runner.send_email"),
            patch("flat_finder.scraper.runner.get_engine") as mock_engine,
            patch("flat_finder.scraper.runner.get_session") as mock_get_session,
            patch("flat_finder.database.Base.metadata.create_all"),
        ):
            mock_engine.return_value = db_session.bind
            mock_get_session.return_value = _make_session_factory(db_session)
            run()

        listing_zone_repo = ListingZoneRepository(db_session)
        zone_ids = listing_zone_repo.get_zone_ids_for_listing("rightmove_200")
        assert zone_a.id in zone_ids
        assert zone_b.id in zone_ids


# ---------------------------------------------------------------------------
# TestPerUserNotifications
# ---------------------------------------------------------------------------


class TestPerUserNotifications:
    """Feature: Notifications sent per-user"""

    def test_user_with_ntfy_topic_gets_notification(self, db_session):
        """Given Leo has ntfy_topic "leo-flats" and new listings in his zones
        When the scraper finishes
        Then ntfy is called with topic "leo-flats"
        """
        _create_user_with_zone(db_session, "leo", ntfy_topic="leo-flats")
        # Mark as already initialised so new listings trigger per-user notifications
        db_session.add(ScraperStateDB(key="initialised", value="true"))
        db_session.commit()

        listing = _make_listing_dict("rightmove_300", lat=51.55, lng=-0.18)

        mock_ntfy = _scraper_run_mocked(db_session, rm_listings=[listing])

        topics = [call.args[0] for call in mock_ntfy.call_args_list]
        assert "leo-flats" in topics

    def test_user_without_topic_gets_no_notification(self, db_session):
        """Given Amelie has no ntfy_topic
        When new listings are found
        Then no ntfy call is made for her
        """
        _create_user_with_zone(db_session, "amelie", ntfy_topic=None)
        # Mark as already initialised so new listings trigger per-user notifications
        db_session.add(ScraperStateDB(key="initialised", value="true"))
        db_session.commit()

        listing = _make_listing_dict("rightmove_400", lat=51.55, lng=-0.18)

        mock_ntfy = _scraper_run_mocked(db_session, rm_listings=[listing])

        # No ntfy calls at all (no one has a topic)
        mock_ntfy.assert_not_called()

    def test_each_user_gets_only_their_zone_listings(self, db_session):
        """Given Leo's zone has listing A, Amelie's zone has listing B
        When both have ntfy_topic set
        Then Leo's notification includes A, Amelie's includes B
        """
        user_repo = UserRepository(db_session)
        zone_repo = ZoneRepository(db_session)

        leo = user_repo.create("leo")
        user_repo.update_ntfy_topic(leo.id, "leo-flats")
        amelie = user_repo.create("amelie")
        user_repo.update_ntfy_topic(amelie.id, "amelie-flats")

        # Two distinct zones with distinct rightmove_id/openrent_term
        zone_repo.create(
            user_id=leo.id,
            name="leo-zone",
            geometry=ZONE_GEOM,
            centroid_lat=51.55,
            centroid_lng=-0.18,
            covering_radius_km=2.0,
            rightmove_id="RM_LEO",
            openrent_term="NW6",
            color_index=0,
        )
        zone_repo.create(
            user_id=amelie.id,
            name="amelie-zone",
            geometry=ZONE_GEOM,
            centroid_lat=51.55,
            centroid_lng=-0.18,
            covering_radius_km=2.0,
            rightmove_id="RM_AME",
            openrent_term="NW8",
            color_index=1,
        )
        # Mark as already initialised so we get per-user notifications, not first-run message
        db_session.add(ScraperStateDB(key="initialised", value="true"))
        db_session.commit()

        listing_a = _make_listing_dict(
            "rightmove_leo_1", lat=51.55, lng=-0.18, address="10 Leo Street, NW6", price=1800
        )
        listing_b = _make_listing_dict(
            "rightmove_ame_1", lat=51.55, lng=-0.18, address="20 Amelie Street, NW8", price=1900
        )

        # Each zone returns only its own listing (keyed by rightmove_id)
        def mock_fetch_rm(location_id, *_args, **_kwargs):
            if location_id == "RM_LEO":
                return [listing_a]
            if location_id == "RM_AME":
                return [listing_b]
            return []

        with (
            patch("flat_finder.scraper.runner.fetch_rightmove", side_effect=mock_fetch_rm),
            patch("flat_finder.scraper.runner.fetch_openrent", return_value=[]),
            patch("flat_finder.scraper.runner.tfl_journey_mins", return_value=None),
            patch("flat_finder.scraper.runner.send_ntfy") as mock_ntfy,
            patch("flat_finder.scraper.runner.send_email"),
            patch("flat_finder.scraper.runner.get_engine") as mock_engine,
            patch("flat_finder.scraper.runner.get_session") as mock_get_session,
            patch("flat_finder.database.Base.metadata.create_all"),
        ):
            mock_engine.return_value = db_session.bind
            mock_get_session.return_value = _make_session_factory(db_session)
            run()

        # Collect calls per topic
        calls_by_topic: dict[str, list] = {}
        for call in mock_ntfy.call_args_list:
            topic = call.args[0]
            calls_by_topic.setdefault(topic, []).append(call)

        # Leo should have been notified (has new listing in his zone)
        assert "leo-flats" in calls_by_topic
        # Amelie should have been notified (has new listing in her zone)
        assert "amelie-flats" in calls_by_topic

        # Verify the body content (ntfy body is 3rd positional arg: topic, title, body)
        leo_call = calls_by_topic["leo-flats"][0]
        amelie_call = calls_by_topic["amelie-flats"][0]

        # Leo's notification body should contain listing A's address, not B's
        assert listing_a["address"] in leo_call.args[2]
        assert listing_b["address"] not in leo_call.args[2]

        # Amelie's notification body should contain listing B's address, not A's
        assert listing_b["address"] in amelie_call.args[2]
        assert listing_a["address"] not in amelie_call.args[2]


# ---------------------------------------------------------------------------
# TestListingArchival
# ---------------------------------------------------------------------------


class TestListingArchival:
    """Feature: Old listings archived, not deleted"""

    def test_old_listings_moved_to_archive(self, db_session):
        """Given a listing older than 14 days
        When archive_old runs
        Then the listing is in listings_archive and removed from listings
        """
        listing_repo = ListingRepository(db_session)
        old_listing = _make_listing_dict("rightmove_old")

        # Insert and then manually backdate first_seen
        listing_repo.insert(old_listing)
        db_session.flush()
        old_date = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=PRUNE_AFTER_DAYS + 1)
        db_session.query(ListingDB).filter_by(id="rightmove_old").update({"first_seen": old_date})
        db_session.flush()

        archived_ids = listing_repo.archive_old(PRUNE_AFTER_DAYS)

        assert "rightmove_old" in archived_ids

        # No longer in listings
        assert db_session.get(ListingDB, "rightmove_old") is None

        # Present in archive
        archived = db_session.get(ListingArchiveDB, "rightmove_old")
        assert archived is not None
        assert archived.address == old_listing["address"]

    def test_recent_listing_not_archived(self, db_session):
        """Given a listing added today
        When archive_old runs
        Then the listing is NOT archived
        """
        listing_repo = ListingRepository(db_session)
        new_listing = _make_listing_dict("rightmove_new")
        listing_repo.insert(new_listing)
        db_session.flush()

        archived_ids = listing_repo.archive_old(PRUNE_AFTER_DAYS)

        assert "rightmove_new" not in archived_ids
        assert db_session.get(ListingDB, "rightmove_new") is not None

    def test_archived_listing_orphans_cleaned(self, db_session):
        """Given a listing with user_state, poi_commutes, listing_zones
        When it is archived
        Then those relational rows are removed
        """
        user_repo = UserRepository(db_session)
        zone_repo = ZoneRepository(db_session)
        listing_repo = ListingRepository(db_session)
        listing_state_repo = ListingStateRepository(db_session)
        listing_zone_repo = ListingZoneRepository(db_session)
        poi_repo = POIRepository(db_session)
        poi_commute_repo = POICommuteRepository(db_session)

        user = user_repo.create("orphan-test-user")
        zone = zone_repo.create(
            user_id=user.id,
            name="test-zone",
            geometry=ZONE_GEOM,
            centroid_lat=51.55,
            centroid_lng=-0.18,
            covering_radius_km=2.0,
            rightmove_id=None,
            openrent_term=None,
            color_index=0,
        )
        poi = poi_repo.create(user_id=user.id, name="Work", lat=51.50, lng=-0.12, color_index=0)
        db_session.commit()

        old_listing = _make_listing_dict("rightmove_orphan", lat=51.55, lng=-0.18)
        listing_repo.insert(old_listing)
        db_session.flush()

        # Create related rows
        listing_state_repo.upsert(user.id, "rightmove_orphan", {"seen": True})
        poi_commute_repo.upsert("rightmove_orphan", poi.id, 30)
        listing_zone_repo.link("rightmove_orphan", zone.id)
        db_session.flush()

        # Backdate listing
        old_date = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=PRUNE_AFTER_DAYS + 1)
        db_session.query(ListingDB).filter_by(id="rightmove_orphan").update({"first_seen": old_date})
        db_session.flush()

        # Archive
        archived_ids = listing_repo.archive_old(PRUNE_AFTER_DAYS)
        assert "rightmove_orphan" in archived_ids

        listing_state_repo.delete_for_listings(archived_ids)
        poi_commute_repo.delete_for_listings(archived_ids)
        listing_zone_repo.delete_for_listings(archived_ids)
        db_session.flush()

        # Verify orphan rows removed
        assert db_session.get(ListingStateDB, (user.id, "rightmove_orphan")) is None
        assert db_session.get(POICommuteDB, ("rightmove_orphan", poi.id)) is None
        lz_rows = db_session.query(ListingZoneDB).filter_by(listing_id="rightmove_orphan").all()
        assert len(lz_rows) == 0

    def test_scraper_run_archives_old_listings(self, db_session):
        """Integration: run() archives old listings via the scraper loop."""
        user_repo = UserRepository(db_session)
        zone_repo = ZoneRepository(db_session)
        listing_repo = ListingRepository(db_session)

        user = user_repo.create("leo")
        zone_repo.create(
            user_id=user.id,
            name="leo-zone",
            geometry=ZONE_GEOM,
            centroid_lat=51.55,
            centroid_lng=-0.18,
            covering_radius_km=2.0,
            rightmove_id="RM_LEO",
            openrent_term="NW6",
            color_index=0,
        )
        db_session.commit()

        # Insert an old listing directly
        old_listing = _make_listing_dict("rightmove_stale", lat=51.55, lng=-0.18)
        listing_repo.insert(old_listing)
        db_session.flush()
        old_date = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=PRUNE_AFTER_DAYS + 1)
        db_session.query(ListingDB).filter_by(id="rightmove_stale").update({"first_seen": old_date})
        db_session.commit()

        _scraper_run_mocked(db_session)

        # Old listing should be gone from listings
        assert db_session.get(ListingDB, "rightmove_stale") is None


# suppress unused-import warning for pytest fixture (used implicitly)
_ = pytest
