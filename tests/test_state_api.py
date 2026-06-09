"""E2E tests for the state API — per-user listing state."""

from datetime import UTC, datetime
from typing import Any

import pytest
from fastapi.testclient import TestClient
from flat_finder.listings.persistence import ListingRepository
from flat_finder.users.persistence import UserRepository
from flat_finder.zones.persistence import ListingZoneRepository, ZoneRepository

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_listing(listing_id: str) -> dict[str, Any]:
    return {
        "id": listing_id,
        "source": "rightmove",
        "url": f"https://example.com/{listing_id}",
        "title": f"Flat {listing_id}",
        "address": f"Address {listing_id}",
        "price_pcm": 1500,
        "bedrooms": 1,
        "latitude": 51.5,
        "longitude": -0.1,
        "has_dishwasher": "unknown",
        "has_washer": "unknown",
        "has_outdoor": "unknown",
        "first_seen": datetime.now(UTC).replace(tzinfo=None),
    }


def _seed_listing_in_zone(db_session, user_id: int, listing_id: str) -> None:
    """Insert a listing and link it to a new zone owned by user_id."""
    listing_repo = ListingRepository(db_session)
    listing_repo.insert(_make_listing(listing_id))

    zone_repo = ZoneRepository(db_session)
    zone = zone_repo.create(
        user_id=user_id,
        name=f"Zone for {listing_id}",
        geometry='{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}',
        centroid_lat=51.5,
        centroid_lng=-0.1,
        covering_radius_km=5.0,
        rightmove_id=None,
        openrent_term=None,
        color_index=0,
    )
    link_repo = ListingZoneRepository(db_session)
    link_repo.link(listing_id, zone.id)
    db_session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def leo_client(app, db_session) -> TestClient:
    repo = UserRepository(db_session)
    repo.create("leo")
    db_session.commit()
    with TestClient(app, root_path="/flat", raise_server_exceptions=True) as c:
        c.post("/login", data={"username": "leo"})
        yield c


@pytest.fixture
def amelie_client(app, db_session) -> TestClient:
    repo = UserRepository(db_session)
    repo.create("amelie")
    db_session.commit()
    with TestClient(app, root_path="/flat", raise_server_exceptions=True) as c:
        c.post("/login", data={"username": "amelie"})
        yield c


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestStateAPIUserScoping:
    """Feature: Per-user listing state
    As a user, my seen/favourite/notes state is independent from other users.
    """

    def test_favourite_listing(self, db_session, leo_client) -> None:
        """Given a listing exists
        When Leo marks it as favourite
        Then the API confirms the favourite state.
        """
        leo = UserRepository(db_session).get_by_username("leo")
        _seed_listing_in_zone(db_session, leo.id, "rm_fav_1")

        resp = leo_client.post("/api/state/rm_fav_1", json={"favourite": True})
        assert resp.status_code == 200
        data = resp.json()
        assert data["favourite"] is True
        assert data["listing_id"] == "rm_fav_1"

    def test_mark_seen(self, db_session, leo_client) -> None:
        """Given a listing exists
        When Leo marks it as seen
        Then the API confirms the seen state.
        """
        leo = UserRepository(db_session).get_by_username("leo")
        _seed_listing_in_zone(db_session, leo.id, "rm_seen_1")

        resp = leo_client.post("/api/state/rm_seen_1", json={"seen": True})
        assert resp.status_code == 200
        assert resp.json()["seen"] is True

    def test_state_independent_between_users(self, db_session, leo_client, amelie_client) -> None:
        """Given Leo and Amelie both have the same listing in their zones
        When Leo favourites it
        Then Amelie's state is unaffected (not favourited).
        """
        leo = UserRepository(db_session).get_by_username("leo")
        amelie = UserRepository(db_session).get_by_username("amelie")

        # Insert listing once
        listing_repo = ListingRepository(db_session)
        listing_repo.insert(_make_listing("shared_listing"))

        # Link to both users' zones
        zone_repo = ZoneRepository(db_session)
        lz_repo = ListingZoneRepository(db_session)

        leo_zone = zone_repo.create(
            leo.id,
            "Leo Zone",
            '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}',
            51.5,
            -0.1,
            5.0,
            None,
            None,
            0,
        )
        amelie_zone = zone_repo.create(
            amelie.id,
            "Amelie Zone",
            '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}',
            51.5,
            -0.1,
            5.0,
            None,
            None,
            1,
        )
        lz_repo.link("shared_listing", leo_zone.id)
        lz_repo.link("shared_listing", amelie_zone.id)
        db_session.commit()

        # Leo favourites it
        leo_client.post("/api/state/shared_listing", json={"favourite": True})

        # Amelie checks state — should not be favourite
        amelie_resp = amelie_client.post("/api/state/shared_listing", json={})
        assert amelie_resp.status_code == 200
        assert amelie_resp.json()["favourite"] is False

    def test_state_update_returns_404_for_unknown_listing(
        self,
        db_session,  # noqa: ARG002
        leo_client,
    ) -> None:
        """Given a listing does not exist
        When Leo tries to update its state
        Then he receives a 404 error.
        """
        resp = leo_client.post("/api/state/nonexistent_listing", json={"seen": True})
        assert resp.status_code == 404

    def test_notes_saved_per_user(self, db_session, leo_client, amelie_client) -> None:
        """Given a shared listing
        When Leo adds a note and Amelie adds a different note
        Then each user sees only their own note.
        """
        leo = UserRepository(db_session).get_by_username("leo")
        amelie = UserRepository(db_session).get_by_username("amelie")

        listing_repo = ListingRepository(db_session)
        listing_repo.insert(_make_listing("shared_notes"))

        zone_repo = ZoneRepository(db_session)
        lz_repo = ListingZoneRepository(db_session)
        leo_zone = zone_repo.create(
            leo.id,
            "L Zone",
            '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}',
            51.5,
            -0.1,
            5.0,
            None,
            None,
            0,
        )
        amelie_zone = zone_repo.create(
            amelie.id,
            "A Zone",
            '{"type":"Polygon","coordinates":[[[0,0],[1,0],[1,1],[0,1],[0,0]]]}',
            51.5,
            -0.1,
            5.0,
            None,
            None,
            1,
        )
        lz_repo.link("shared_notes", leo_zone.id)
        lz_repo.link("shared_notes", amelie_zone.id)
        db_session.commit()

        leo_client.post("/api/state/shared_notes", json={"notes": "Leo's note"})
        amelie_client.post("/api/state/shared_notes", json={"notes": "Amelie's note"})

        leo_resp = leo_client.post("/api/state/shared_notes", json={})
        amelie_resp = amelie_client.post("/api/state/shared_notes", json={})

        assert leo_resp.json()["notes"] == "Leo's note"
        assert amelie_resp.json()["notes"] == "Amelie's note"
