"""E2E tests for the feed page — user-scoped listing display."""
from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from flat_finder.listings.persistence import ListingRepository
from flat_finder.users.persistence import UserRepository
from flat_finder.zones.persistence import ListingZoneRepository, ZoneRepository


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_listing(
    listing_id: str,
    address: str = "1 Test St, London",
    price_pcm: int = 1500,
) -> dict[str, Any]:
    return {
        "id": listing_id,
        "source": "rightmove",
        "url": f"https://example.com/{listing_id}",
        "title": f"Flat {listing_id}",
        "address": address,
        "price_pcm": price_pcm,
        "bedrooms": 1,
        "latitude": 51.5,
        "longitude": -0.1,
        "has_dishwasher": "unknown",
        "has_washer": "unknown",
        "has_outdoor": "unknown",
        "first_seen": datetime.now(UTC).replace(tzinfo=None),
    }


def _make_zone(
    session: Session,
    user_id: int,
    name: str,
) -> dict:
    repo = ZoneRepository(session)
    zone = repo.create(
        user_id=user_id,
        name=name,
        geometry='{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}',
        centroid_lat=51.5,
        centroid_lng=-0.1,
        covering_radius_km=5.0,
        rightmove_id=None,
        openrent_term=None,
        color_index=0,
    )
    session.commit()
    return {"id": zone.id, "name": zone.name, "user_id": zone.user_id}


def _link_listing_to_zone(session: Session, listing_id: str, zone_id: int) -> None:
    repo = ListingZoneRepository(session)
    repo.link(listing_id, zone_id)
    session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def leo_client(app, db_session) -> TestClient:
    """Client logged in as leo."""
    repo = UserRepository(db_session)
    repo.create("leo")
    db_session.commit()
    with TestClient(app, root_path="/flat", raise_server_exceptions=True) as c:
        c.post("/login", data={"username": "leo"})
        yield c


@pytest.fixture
def amelie_client(app, db_session) -> TestClient:
    """Client logged in as amelie."""
    repo = UserRepository(db_session)
    repo.create("amelie")
    db_session.commit()
    with TestClient(app, root_path="/flat", raise_server_exceptions=True) as c:
        c.post("/login", data={"username": "amelie"})
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestFeedUserScoping:
    """Feature: Per-user feed
    As a user, I only see listings in my zones.
    """

    def test_user_sees_only_listings_in_their_zones(
        self, app, db_session, leo_client, amelie_client
    ) -> None:
        """Given Leo has zone A with listing 1, Amelie has zone B with listing 2
        When Leo views the feed
        Then he sees listing 1 but not listing 2.
        """
        leo = UserRepository(db_session).get_by_username("leo")
        amelie = UserRepository(db_session).get_by_username("amelie")

        listing_repo = ListingRepository(db_session)
        listing_repo.insert(_make_listing("rm_1", address="Leo Flat"))
        listing_repo.insert(_make_listing("rm_2", address="Amelie Flat"))
        db_session.commit()

        zone_a = _make_zone(db_session, leo.id, "Zone A")
        zone_b = _make_zone(db_session, amelie.id, "Zone B")
        _link_listing_to_zone(db_session, "rm_1", zone_a["id"])
        _link_listing_to_zone(db_session, "rm_2", zone_b["id"])

        resp = leo_client.get("/")
        assert resp.status_code == 200
        assert "Leo Flat" in resp.text
        assert "Amelie Flat" not in resp.text

    def test_zone_filter_shows_user_zones(self, app, db_session, leo_client) -> None:
        """Given Leo has two zones
        When he views the feed
        Then the zone filter shows his zone names.
        """
        leo = UserRepository(db_session).get_by_username("leo")
        _make_zone(db_session, leo.id, "North London")
        _make_zone(db_session, leo.id, "South London")

        resp = leo_client.get("/")
        assert resp.status_code == 200
        assert "North London" in resp.text
        assert "South London" in resp.text

    def test_favourite_state_independent_per_user(
        self, app, db_session, leo_client, amelie_client
    ) -> None:
        """Given a shared listing in both users' zones
        When Leo favourites it and Amelie views it
        Then Amelie does not see it as favourited.
        """
        leo = UserRepository(db_session).get_by_username("leo")
        amelie = UserRepository(db_session).get_by_username("amelie")

        listing_repo = ListingRepository(db_session)
        listing_repo.insert(_make_listing("shared_1", address="Shared Flat"))
        db_session.commit()

        zone_leo = _make_zone(db_session, leo.id, "Leo Zone")
        zone_amelie = _make_zone(db_session, amelie.id, "Amelie Zone")
        _link_listing_to_zone(db_session, "shared_1", zone_leo["id"])
        _link_listing_to_zone(db_session, "shared_1", zone_amelie["id"])

        # Leo favourites the listing
        leo_client.post("/api/state/shared_1", json={"favourite": True})

        # Check Leo sees it as favourite
        resp = leo_client.get("/api/state/shared_1", follow_redirects=True)
        # Verify via the state endpoint
        state_resp = leo_client.post("/api/state/shared_1", json={"favourite": True})
        assert state_resp.status_code == 200
        assert state_resp.json()["favourite"] is True

        # Amelie's state should be independent (not favourite)
        amelie_state = amelie_client.post("/api/state/shared_1", json={})
        assert amelie_state.status_code == 200
        assert amelie_state.json()["favourite"] is False

    def test_feed_renders_with_no_zones(self, leo_client) -> None:
        """Given Leo has no zones
        When he views the feed
        Then the page renders with an empty state message.
        """
        resp = leo_client.get("/")
        assert resp.status_code == 200
        assert "No listings yet" in resp.text

    def test_sort_options_work(self, app, db_session, leo_client) -> None:
        """Given Leo has listings in his zone
        When he requests different sort options
        Then the feed returns 200 for each.
        """
        leo = UserRepository(db_session).get_by_username("leo")

        listing_repo = ListingRepository(db_session)
        listing_repo.insert(_make_listing("rm_sort_1", price_pcm=1500))
        listing_repo.insert(_make_listing("rm_sort_2", price_pcm=2000))
        db_session.commit()

        zone = _make_zone(db_session, leo.id, "Sort Zone")
        _link_listing_to_zone(db_session, "rm_sort_1", zone["id"])
        _link_listing_to_zone(db_session, "rm_sort_2", zone["id"])

        for sort_key in ["newest", "price_asc", "price_desc", "size_desc", "best_match", "commute"]:
            resp = leo_client.get(f"/?sort={sort_key}")
            assert resp.status_code == 200, f"Sort '{sort_key}' returned {resp.status_code}"
