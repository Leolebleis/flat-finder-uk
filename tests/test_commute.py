"""Tests for TfL commute fetching: 404 sentinel + per-upsert hook.

Listings outside the TfL network (e.g. Brighton) get a 404 from Journey
Planner on every lookup. Those must be recorded as NO_JOURNEY so the
backfill stops retrying them forever, and excluded from UI/scoring reads.
"""

from unittest.mock import Mock, patch

import requests
from flat_finder.pois.model import POI
from flat_finder.pois.persistence import POICommuteRepository, POIRepository
from flat_finder.scraper.commute import NO_JOURNEY, fetch_commutes_for_listings, tfl_journey_mins
from tests.test_repositories import ListingRepository, _make_listing_dict


def _http_error(status: int) -> requests.HTTPError:
    response = Mock(status_code=status)
    return requests.HTTPError(response=response)


class TestTflJourneyMins:
    """Feature: TfL lookup distinguishes permanent vs transient failures"""

    def test_404_returns_no_journey_sentinel(self):
        """Given TfL responds 404 (coords outside the network)
        When tfl_journey_mins is called
        Then it returns NO_JOURNEY rather than None.
        """
        resp = Mock()
        resp.raise_for_status.side_effect = _http_error(404)
        with patch("flat_finder.scraper.commute.requests.get", return_value=resp):
            assert tfl_journey_mins(50.82, -0.14, 51.54, -0.17) == NO_JOURNEY

    def test_server_error_returns_none(self):
        """Given TfL responds 500 (transient)
        When tfl_journey_mins is called
        Then it returns None so the lookup is retried later.
        """
        resp = Mock()
        resp.raise_for_status.side_effect = _http_error(500)
        with patch("flat_finder.scraper.commute.requests.get", return_value=resp):
            assert tfl_journey_mins(51.5, -0.1, 51.54, -0.17) is None

    def test_connection_error_returns_none(self):
        """Given the TfL request fails at the network level
        When tfl_journey_mins is called
        Then it returns None so the lookup is retried later.
        """
        with patch(
            "flat_finder.scraper.commute.requests.get",
            side_effect=requests.ConnectionError("boom"),
        ):
            assert tfl_journey_mins(51.5, -0.1, 51.54, -0.17) is None


class TestFetchCommutesForListings:
    """Feature: shared backfill loop"""

    def _poi(self) -> POI:
        return POI(id=1, user_id=1, name="Work", lat=51.54, lng=-0.17, color_index=0, created_at="now")

    def test_stores_no_journey_sentinel_on_404(self):
        """Given a listing whose TfL lookup 404s
        When fetch_commutes_for_listings runs
        Then the NO_JOURNEY sentinel is upserted (so it is not retried)."""
        dao = Mock()
        rows = [{"id": "rm_1", "latitude": 50.82, "longitude": -0.14}]
        with (
            patch("flat_finder.scraper.commute.tfl_journey_mins", return_value=NO_JOURNEY),
            patch("flat_finder.scraper.commute.time.sleep"),
        ):
            fetch_commutes_for_listings(dao, self._poi(), rows)
        dao.upsert.assert_called_once_with("rm_1", 1, NO_JOURNEY)

    def test_transient_failure_skips_upsert(self):
        """Given a listing whose TfL lookup fails transiently (None)
        When fetch_commutes_for_listings runs
        Then nothing is upserted so the lookup is retried next run."""
        dao = Mock()
        rows = [{"id": "rm_1", "latitude": 51.5, "longitude": -0.1}]
        with patch("flat_finder.scraper.commute.tfl_journey_mins", return_value=None):
            fetch_commutes_for_listings(dao, self._poi(), rows)
        dao.upsert.assert_not_called()

    def test_after_upsert_called_per_row(self):
        """Given multiple listings with successful lookups
        When fetch_commutes_for_listings runs with an after_upsert hook
        Then the hook (e.g. session.commit) runs once per upsert."""
        dao = Mock()
        hook = Mock()
        rows = [
            {"id": "rm_1", "latitude": 51.5, "longitude": -0.1},
            {"id": "rm_2", "latitude": 51.6, "longitude": -0.2},
        ]
        with (
            patch("flat_finder.scraper.commute.tfl_journey_mins", return_value=25),
            patch("flat_finder.scraper.commute.time.sleep"),
        ):
            fetch_commutes_for_listings(dao, self._poi(), rows, after_upsert=hook)
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
