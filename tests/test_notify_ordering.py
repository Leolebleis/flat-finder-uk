"""Tests that notifications are not held up by rate-limited commute lookups.

An influx of new listings once delayed every alert by ~100 minutes, because the
whole batch's commute times were fetched before any push went out.
"""

from unittest.mock import Mock, patch

import pytest
from flat_finder.pois.persistence import POIRepository
from flat_finder.scraper.health import set_scraper_state
from flat_finder.scraper.runner import run
from sqlalchemy.orm import sessionmaker
from tests.test_scraper import _create_user_with_zone, _make_listing_dict


@pytest.fixture
def timeline(db_session):
    """Run the scraper with externals mocked, recording the order of events.

    Yields a callable taking the listings Rightmove should return; it returns an
    ordered log where each entry is ("commute", n_calls_allowed) or ("ntfy", None).
    """

    def _run(rm_listings):
        events: list[tuple[str, int | None]] = []

        def _record_commutes(_dao, _poi, _rows, _client, max_calls=None, **_kw):
            events.append(("commute", max_calls))

        with (
            patch("flat_finder.scraper.runner.fetch_rightmove", return_value=rm_listings),
            patch("flat_finder.scraper.runner.fetch_openrent", return_value=[]),
            patch(
                "flat_finder.scraper.runner.TransitousCommuteClient",
                return_value=Mock(journey_mins=Mock(return_value=20)),
            ),
            patch("flat_finder.scraper.runner.fetch_commutes_for_listings", side_effect=_record_commutes),
            patch("flat_finder.scraper.runner.send_ntfy", side_effect=lambda *_a, **_kw: events.append(("ntfy", None))),
            patch("flat_finder.scraper.runner.send_email"),
            patch("flat_finder.scraper.runner.get_engine") as mock_engine,
            patch("flat_finder.scraper.runner.get_session") as mock_get_session,
        ):
            mock_engine.return_value = db_session.bind
            mock_get_session.return_value = sessionmaker(bind=db_session.bind)
            run()
        return events

    return _run


def _seed(db_session):
    """One user with an ntfy topic, one zone, one POI, past the first run."""
    user, _zone = _create_user_with_zone(db_session, "notify-order", ntfy_topic="topic-a")
    POIRepository(db_session).create(user_id=user.id, name="Work", lat=51.50, lng=-0.12, color_index=0)
    set_scraper_state(db_session, "initialised", "true")
    db_session.commit()


def _listings(n):
    """n listings with distinct fingerprints and distinct coordinates."""
    return [
        _make_listing_dict(
            f"rightmove_{i}", lat=51.545 + i / 10000, lng=-0.18, price=1800 + i, address=f"{i} Test Street, NW6"
        )
        for i in range(n)
    ]


class TestNotifyBeforeBackfill:
    """Feature: alerts go out before the rate-limited backfill runs"""

    def test_backfill_runs_after_notifications(self, db_session, timeline):
        """Given new listings and a POI
        When the scraper runs
        Then the bounded prefetch precedes the pushes and the backfill follows them.
        """
        _seed(db_session)
        kinds = [kind for kind, _ in timeline(_listings(3))]

        assert "ntfy" in kinds, "expected notifications"
        first_ntfy, last_ntfy = kinds.index("ntfy"), len(kinds) - 1 - kinds[::-1].index("ntfy")
        first_commute, last_commute = kinds.index("commute"), len(kinds) - 1 - kinds[::-1].index("commute")
        assert first_commute < first_ntfy, "bounded prefetch should precede the pushes"
        assert last_commute > last_ntfy, "backfill should follow the pushes"

    @pytest.mark.parametrize("budget", [40, 5, 0])
    def test_prefetch_is_capped_at_the_call_budget(self, db_session, timeline, budget):
        """Given a configured pre-notify call budget
        When the scraper runs with one POI
        Then that POI's prefetch is capped at the budget.

        The cap counts upstream requests, not listings: cost is one request per
        distinct coordinate per POI, so a listing-denominated limit would
        silently multiply by the number of POIs.
        """
        _seed(db_session)
        with patch("flat_finder.scraper.runner.config.COMMUTE_PRENOTIFY_CALLS", budget):
            events = timeline(_listings(30))

        first_ntfy = next(i for i, (kind, _) in enumerate(events) if kind == "ntfy")
        assert [cap for kind, cap in events[:first_ntfy] if kind == "commute"] == [budget]
