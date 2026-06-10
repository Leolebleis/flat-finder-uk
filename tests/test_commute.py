"""Tests for commute client abstraction and backfill loop.

The CommuteClient protocol allows swapping transit providers. The backfill
loop (fetch_commutes_for_listings) must handle NO_JOURNEY sentinels,
transient failures, and per-upsert hooks regardless of the concrete client.
"""

from unittest.mock import Mock, patch

import requests
from flat_finder.pois.model import POI
from flat_finder.pois.persistence import POICommuteRepository, POIRepository
from flat_finder.scraper.commute import NO_JOURNEY, fetch_commutes_for_listings
from flat_finder.scraper.transitous import TransitousCommuteClient
from tests.test_repositories import ListingRepository, _make_listing_dict


def _http_error(status: int) -> requests.HTTPError:
    response = Mock(status_code=status)
    return requests.HTTPError(response=response)


class TestTransitousCommuteClient:
    """Feature: Transitous API returns journey minutes or failure sentinels"""

    def test_returns_shortest_journey_minutes(self):
        """Given Transitous returns multiple itineraries
        When journey_mins is called
        Then it returns the shortest duration in minutes.
        """
        resp = Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {
            "itineraries": [
                {"duration": 5940},
                {"duration": 7200},
            ]
        }
        with patch("flat_finder.scraper.transitous.requests.get", return_value=resp):
            client = TransitousCommuteClient()
            assert client.journey_mins(50.82, -0.14, 51.54, -0.17) == 99

    def test_empty_itineraries_returns_no_journey(self):
        """Given Transitous returns an empty itinerary list
        When journey_mins is called
        Then it returns NO_JOURNEY (permanent — no route exists).
        """
        resp = Mock()
        resp.raise_for_status.return_value = None
        resp.json.return_value = {"itineraries": []}
        with patch("flat_finder.scraper.transitous.requests.get", return_value=resp):
            client = TransitousCommuteClient()
            assert client.journey_mins(50.82, -0.14, 51.54, -0.17) == NO_JOURNEY

    def test_http_error_returns_none(self):
        """Given Transitous responds with an HTTP error
        When journey_mins is called
        Then it returns None (transient — worth retrying).
        """
        resp = Mock()
        resp.raise_for_status.side_effect = _http_error(500)
        with patch("flat_finder.scraper.transitous.requests.get", return_value=resp):
            client = TransitousCommuteClient()
            assert client.journey_mins(51.5, -0.1, 51.54, -0.17) is None

    def test_connection_error_returns_none(self):
        """Given the Transitous request fails at the network level
        When journey_mins is called
        Then it returns None (transient — worth retrying).
        """
        with patch(
            "flat_finder.scraper.transitous.requests.get",
            side_effect=requests.ConnectionError("boom"),
        ):
            client = TransitousCommuteClient()
            assert client.journey_mins(51.5, -0.1, 51.54, -0.17) is None


class TestFetchCommutesForListings:
    """Feature: shared backfill loop accepts any CommuteClient"""

    def _poi(self) -> POI:
        return POI(id=1, user_id=1, name="Work", lat=51.54, lng=-0.17, color_index=0, created_at="now")

    def _mock_client(self, return_value: int | None) -> Mock:
        client = Mock()
        client.journey_mins.return_value = return_value
        return client

    def test_stores_no_journey_sentinel(self):
        """Given a client returns NO_JOURNEY for a listing
        When fetch_commutes_for_listings runs
        Then the NO_JOURNEY sentinel is upserted (so it is not retried)."""
        dao = Mock()
        client = self._mock_client(NO_JOURNEY)
        rows = [{"id": "rm_1", "latitude": 50.82, "longitude": -0.14}]
        with patch("flat_finder.scraper.commute.time.sleep"):
            fetch_commutes_for_listings(dao, self._poi(), rows, client)
        dao.upsert.assert_called_once_with("rm_1", 1, NO_JOURNEY)

    def test_transient_failure_skips_upsert(self):
        """Given a client returns None (transient failure)
        When fetch_commutes_for_listings runs
        Then nothing is upserted so the lookup is retried next run."""
        dao = Mock()
        client = self._mock_client(None)
        rows = [{"id": "rm_1", "latitude": 51.5, "longitude": -0.1}]
        fetch_commutes_for_listings(dao, self._poi(), rows, client)
        dao.upsert.assert_not_called()

    def test_after_upsert_called_per_row(self):
        """Given multiple listings with successful lookups
        When fetch_commutes_for_listings runs with an after_upsert hook
        Then the hook (e.g. session.commit) runs once per upsert."""
        dao = Mock()
        hook = Mock()
        client = self._mock_client(25)
        rows = [
            {"id": "rm_1", "latitude": 51.5, "longitude": -0.1},
            {"id": "rm_2", "latitude": 51.6, "longitude": -0.2},
        ]
        with patch("flat_finder.scraper.commute.time.sleep"):
            fetch_commutes_for_listings(dao, self._poi(), rows, client, after_upsert=hook)
        assert hook.call_count == 2


class TestNoJourneySentinelReads:
    """Feature: sentinel rows are excluded from reads but stop the backfill"""

    def test_sentinel_excluded_from_get_for_listings(self, db_session):
        """Given a listing with a NO_JOURNEY commute and one real commute
        When get_for_listings is called
        Then only the real commute is returned."""
        listing_repo = ListingRepository(db_session)
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)

        listing_repo.insert(_make_listing_dict("rm_900"))
        poi1 = poi_repo.create(user_id=1, name="Work", lat=51.5, lng=-0.1, color_index=0)
        poi2 = poi_repo.create(user_id=1, name="Gym", lat=51.6, lng=-0.2, color_index=1)

        commute_repo.upsert("rm_900", poi1.id, NO_JOURNEY)
        commute_repo.upsert("rm_900", poi2.id, 25)

        result = commute_repo.get_for_listings(["rm_900"])
        assert result == {"rm_900": {poi2.id: 25}}

    def test_sentinel_stops_backfill_retries(self, db_session):
        """Given a listing with a NO_JOURNEY commute for a POI
        When get_listings_missing_poi is called for that POI
        Then the listing is no longer returned."""
        listing_repo = ListingRepository(db_session)
        poi_repo = POIRepository(db_session)
        commute_repo = POICommuteRepository(db_session)

        listing_repo.insert(_make_listing_dict("rm_910", lat=50.82, lng=-0.14))
        poi = poi_repo.create(user_id=1, name="Work", lat=51.5, lng=-0.1, color_index=0)

        assert any(r["id"] == "rm_910" for r in commute_repo.get_listings_missing_poi(poi.id))

        commute_repo.upsert("rm_910", poi.id, NO_JOURNEY)

        assert not any(r["id"] == "rm_910" for r in commute_repo.get_listings_missing_poi(poi.id))
