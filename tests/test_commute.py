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


def _ok(itineraries: list[dict]) -> Mock:
    resp = Mock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = {"itineraries": itineraries}
    return resp


def _err(exc: Exception) -> Mock:
    resp = Mock()
    resp.raise_for_status.side_effect = exc
    return resp


class TestTransitousCommuteClient:
    """Feature: Transitous API returns journey minutes or failure sentinels"""

    def test_returns_shortest_journey_minutes(self):
        """Given Transitous returns multiple itineraries
        When journey_mins is called
        Then it returns the shortest duration in minutes.
        """
        resp = _ok([{"duration": 5940}, {"duration": 7200}])
        with patch("flat_finder.scraper.transitous.requests.get", return_value=resp):
            client = TransitousCommuteClient()
            assert client.journey_mins(50.82, -0.14, 51.54, -0.17) == 99

    def test_all_origins_empty_returns_no_journey(self):
        """Given the exact origin AND every nudged origin return no itineraries
        When journey_mins is called
        Then it returns NO_JOURNEY (genuinely unroutable).
        """
        with (
            patch("flat_finder.scraper.transitous.requests.get", return_value=_ok([])),
            patch("flat_finder.scraper.transitous.time.sleep"),
        ):
            client = TransitousCommuteClient()
            assert client.journey_mins(50.82, -0.14, 51.54, -0.17) == NO_JOURNEY

    def test_nudged_origin_recovers_snapping_deadspot(self):
        """Given the exact origin returns no itineraries (MOTIS can't snap it)
        When a nudged origin ~150m away routes successfully
        Then the recovered journey time is returned instead of NO_JOURNEY.
        """
        # First call (exact origin) empty; second call (first nudge) routes.
        with (
            patch(
                "flat_finder.scraper.transitous.requests.get",
                side_effect=[_ok([]), _ok([{"duration": 6000}])],
            ),
            patch("flat_finder.scraper.transitous.time.sleep"),
        ):
            client = TransitousCommuteClient()
            assert client.journey_mins(50.8218, -0.1437, 51.48, -0.17) == 100

    def test_transient_error_during_nudge_returns_none(self):
        """Given the origin is empty and a nudge hits a transient error
        When journey_mins is called
        Then it returns None so the pair is retried next run (no permanent sentinel).
        """
        # exact origin empty; nudges: empty, 500-error, empty, empty (1 + 4 = 5 calls)
        with (
            patch(
                "flat_finder.scraper.transitous.requests.get",
                side_effect=[_ok([]), _ok([]), _err(_http_error(500)), _ok([]), _ok([])],
            ),
            patch("flat_finder.scraper.transitous.time.sleep"),
        ):
            client = TransitousCommuteClient()
            assert client.journey_mins(50.8218, -0.1437, 51.48, -0.17) is None

    def test_http_error_returns_none(self):
        """Given Transitous responds with an HTTP error on the exact origin
        When journey_mins is called
        Then it returns None immediately (transient — worth retrying, no nudging).
        """
        with patch("flat_finder.scraper.transitous.requests.get", return_value=_err(_http_error(500))):
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

    def test_shared_coordinate_queries_api_once_but_upserts_all(self):
        """Given several listings sharing a coordinate (to ~1m)
        When fetch_commutes_for_listings runs
        Then the commute API is queried once per distinct coordinate,
        but every listing still gets its own upserted row."""
        dao = Mock()
        client = self._mock_client(25)
        rows = [
            {"id": "rm_1", "latitude": 51.50000, "longitude": -0.10000},
            {"id": "rm_2", "latitude": 51.500004, "longitude": -0.100002},  # same coord at 5dp
            {"id": "rm_3", "latitude": 51.60000, "longitude": -0.20000},  # distinct
        ]
        with patch("flat_finder.scraper.commute.time.sleep"):
            fetch_commutes_for_listings(dao, self._poi(), rows, client)
        assert client.journey_mins.call_count == 2  # one per distinct coordinate
        assert dao.upsert.call_count == 3  # one per listing
        dao.upsert.assert_any_call("rm_2", 1, 25)  # shared-coord listing still upserted

    def test_shared_coordinate_no_journey_fans_out_to_all(self):
        """Given listings sharing an unroutable coordinate
        When the single query returns NO_JOURNEY
        Then every co-located listing gets the sentinel (one API call)."""
        dao = Mock()
        client = self._mock_client(NO_JOURNEY)
        rows = [
            {"id": "rm_1", "latitude": 50.82176, "longitude": -0.14370},
            {"id": "rm_2", "latitude": 50.82176, "longitude": -0.14370},
        ]
        with patch("flat_finder.scraper.commute.time.sleep"):
            fetch_commutes_for_listings(dao, self._poi(), rows, client)
        assert client.journey_mins.call_count == 1
        assert dao.upsert.call_count == 2


class TestMaxCallsBudget:
    """Feature: cap the upstream requests a single pass may spend

    The cap exists so commute lookups sitting in front of user notifications
    cannot delay them without bound.
    """

    def _poi(self) -> POI:
        return POI(id=1, user_id=1, name="Work", lat=51.54, lng=-0.17, color_index=0, created_at="now")

    def _mock_client(self, return_value: int | None) -> Mock:
        client = Mock()
        client.journey_mins.return_value = return_value
        return client

    def test_caps_upstream_requests(self):
        """Given more distinct coordinates than the budget
        When fetch_commutes_for_listings runs with max_calls
        Then only that many upstream requests are made."""
        dao = Mock()
        client = self._mock_client(25)
        rows = [{"id": f"rm_{i}", "latitude": 51.5 + i / 1000, "longitude": -0.1} for i in range(10)]
        with patch("flat_finder.scraper.commute.time.sleep"):
            fetch_commutes_for_listings(dao, self._poi(), rows, client, max_calls=3)
        assert client.journey_mins.call_count == 3
        assert dao.upsert.call_count == 3

    def test_budget_counts_requests_not_listings(self):
        """Given many listings that collapse onto few coordinates
        When the budget is smaller than the listing count but not the coord count
        Then all of them are fetched, because they cost only two requests.

        A listing-denominated cap would have skipped most of these for no
        latency saving.
        """
        dao = Mock()
        client = self._mock_client(25)
        rows = [{"id": f"rm_{i}", "latitude": 51.50000, "longitude": -0.10000} for i in range(9)]
        rows.append({"id": "rm_other", "latitude": 51.60000, "longitude": -0.20000})
        with patch("flat_finder.scraper.commute.time.sleep"):
            fetch_commutes_for_listings(dao, self._poi(), rows, client, max_calls=2)
        assert client.journey_mins.call_count == 2
        assert dao.upsert.call_count == 10  # every listing still gets a row

    def test_never_splits_a_coordinate_group(self):
        """Given a coordinate shared by several listings
        When the budget cuts off mid-batch
        Then the group is included whole or not at all.

        A split group would leave siblings for the later backfill pass, which
        would re-request the identical coordinate.
        """
        dao = Mock()
        client = self._mock_client(25)
        rows = [
            {"id": "a1", "latitude": 51.50000, "longitude": -0.10000},
            {"id": "a2", "latitude": 51.50000, "longitude": -0.10000},
            {"id": "b1", "latitude": 51.60000, "longitude": -0.20000},
        ]
        with patch("flat_finder.scraper.commute.time.sleep"):
            fetch_commutes_for_listings(dao, self._poi(), rows, client, max_calls=1)
        upserted = {call.args[0] for call in dao.upsert.call_args_list}
        assert upserted == {"a1", "a2"}, "the whole first coordinate, and nothing from the second"

    def test_zero_budget_makes_no_requests(self):
        """Given a zero budget
        When fetch_commutes_for_listings runs
        Then nothing is fetched or upserted."""
        dao = Mock()
        client = self._mock_client(25)
        rows = [{"id": "rm_1", "latitude": 51.5, "longitude": -0.1}]
        with patch("flat_finder.scraper.commute.time.sleep"):
            fetch_commutes_for_listings(dao, self._poi(), rows, client, max_calls=0)
        assert client.journey_mins.call_count == 0
        assert dao.upsert.call_count == 0

    def test_no_budget_fetches_everything(self):
        """Given max_calls is not supplied
        When fetch_commutes_for_listings runs
        Then behaviour is unchanged: every coordinate is queried."""
        dao = Mock()
        client = self._mock_client(25)
        rows = [{"id": f"rm_{i}", "latitude": 51.5 + i / 1000, "longitude": -0.1} for i in range(4)]
        with patch("flat_finder.scraper.commute.time.sleep"):
            fetch_commutes_for_listings(dao, self._poi(), rows, client)
        assert client.journey_mins.call_count == 4


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
