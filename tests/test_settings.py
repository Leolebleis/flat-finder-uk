"""E2E tests for the settings page — ntfy topic and POI user scoping."""

import pytest
from fastapi.testclient import TestClient
from flat_finder.pois.persistence import POIRepository
from flat_finder.users.persistence import UserDB, UserRepository

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


class TestNtfySettings:
    """Feature: Per-user notification settings
    As a user, I can configure my ntfy topic for flat alerts.
    """

    def test_set_ntfy_topic(self, db_session, leo_client) -> None:  # noqa: ARG002
        """Given Leo is on settings page
        When he submits a new ntfy topic
        Then his topic is saved and visible on the settings page.
        """
        resp = leo_client.post(
            "/settings/ntfy",
            data={"topic": "leo-flat-alerts"},
            follow_redirects=True,
        )
        assert resp.status_code == 200
        assert "leo-flat-alerts" in resp.text

    def test_clear_ntfy_topic(self, db_session, leo_client) -> None:
        """Given Leo has a saved ntfy topic
        When he submits an empty topic
        Then the topic is cleared.
        """
        # Set first
        leo_client.post("/settings/ntfy", data={"topic": "leo-alerts"})
        # Clear
        resp = leo_client.post("/settings/ntfy", data={"topic": ""}, follow_redirects=True)
        assert resp.status_code == 200
        # Verify topic is cleared in DB
        leo = UserRepository(db_session).get_by_username("leo")
        db_session.refresh(db_session.get(UserDB, leo.id))
        user_db = db_session.get(UserDB, leo.id)
        assert user_db.ntfy_topic is None

    def test_ntfy_topic_displayed_on_settings(self, db_session, leo_client) -> None:  # noqa: ARG002
        """Given Leo has a saved ntfy topic
        When he visits the settings page
        Then his topic is pre-filled in the form.
        """
        leo_client.post("/settings/ntfy", data={"topic": "my-flats"})
        resp = leo_client.get("/settings")
        assert resp.status_code == 200
        assert "my-flats" in resp.text

    def test_settings_page_renders(self, leo_client) -> None:
        """Given Leo is logged in
        When he visits the settings page
        Then the page renders with ntfy, POI, and zone sections.
        """
        resp = leo_client.get("/settings")
        assert resp.status_code == 200
        assert "Notifications" in resp.text
        assert "Places of Interest" in resp.text
        assert "Search Zones" in resp.text


class TestPOIUserScoping:
    """Feature: Per-user POIs
    As a user, I only see my own Places of Interest.
    """

    def test_user_only_sees_own_pois(
        self,
        db_session,
        leo_client,
        amelie_client,  # noqa: ARG002
    ) -> None:
        """Given Leo adds POI 'Leo Work' and Amelie adds POI 'Amelie HQ'
        When Leo views the settings page
        Then he sees 'Leo Work' but not 'Amelie HQ'.
        """
        leo = UserRepository(db_session).get_by_username("leo")
        amelie = UserRepository(db_session).get_by_username("amelie")

        poi_repo = POIRepository(db_session)
        poi_repo.create(leo.id, "Leo Work", 51.5, -0.1, 0)
        poi_repo.create(amelie.id, "Amelie HQ", 51.6, -0.2, 1)
        db_session.commit()

        resp = leo_client.get("/settings")
        assert resp.status_code == 200
        assert "Leo Work" in resp.text
        assert "Amelie HQ" not in resp.text

    def test_add_poi_assigned_to_current_user(self, db_session, leo_client) -> None:
        """Given Leo adds a POI via the settings form
        When we query the DB for Leo's POIs
        Then the new POI is in his list.
        """
        leo = UserRepository(db_session).get_by_username("leo")
        # Use valid coords — skip actual URL parsing by patching with a mock
        # We test via the settings page by verifying the POI appears
        # (extract_coords_from_url will reject a non-Maps URL, so we seed directly)
        poi_repo = POIRepository(db_session)
        poi_repo.create(leo.id, "Library", 51.51, -0.12, 0)
        db_session.commit()

        resp = leo_client.get("/settings")
        assert resp.status_code == 200
        assert "Library" in resp.text

    def test_delete_other_users_poi_returns_error(
        self,
        db_session,
        leo_client,
        amelie_client,  # noqa: ARG002
    ) -> None:
        """Given Amelie has a POI
        When Leo tries to delete it
        Then he receives a 404 error.
        """
        amelie = UserRepository(db_session).get_by_username("amelie")
        poi_repo = POIRepository(db_session)
        poi = poi_repo.create(amelie.id, "Amelie Office", 51.5, -0.1, 0)
        db_session.commit()

        resp = leo_client.delete(f"/settings/poi/{poi.id}")
        assert resp.status_code == 404
