"""Tests for scraper source-health latching and re-alerting.

A permanently broken source used to alert exactly once and then look identical
to a healthy one — Rightmove returned nothing for 8 days that way.
"""

from datetime import UTC, datetime, timedelta
from unittest.mock import patch

import pytest
from flat_finder.scraper.health import get_scraper_state, handle_source_health, set_scraper_state

TOPIC = "test-topic"
SOURCE = "rightmove/North London"
REASON = "Could not find __NEXT_DATA__ in Rightmove HTML"
T0 = datetime(2026, 7, 20, 8, 0, tzinfo=UTC)
INTERVAL_H = 6
STATE_KEY = f"{SOURCE}_failing"


@pytest.fixture
def sent():
    """Capture ntfy pushes as (title, body) pairs, with a known re-alert interval."""
    calls = []
    with (
        patch("flat_finder.scraper.health.send_ntfy", side_effect=lambda _t, ti, b: calls.append((ti, b))),
        patch("flat_finder.scraper.health.config.SCRAPER_REALERT_HOURS", INTERVAL_H),
    ):
        yield calls


def _fail(session, at, reason=REASON, topic=TOPIC):
    handle_source_health(session, topic, SOURCE, reason, now=at)


def _succeed(session, at, topic=TOPIC):
    handle_source_health(session, topic, SOURCE, None, now=at)


class TestFirstFailureAndRecovery:
    """Feature: alert when a source's health changes"""

    def test_first_failure_alerts_and_latches(self, db_session, sent):
        """Given a healthy source
        When a scrape fails
        Then a failure push is sent and the state is latched.
        """
        _fail(db_session, T0)
        assert len(sent) == 1
        assert "scrape failed" in sent[0][0]
        assert get_scraper_state(db_session, STATE_KEY) is not None

    def test_recovery_alerts_and_clears(self, db_session, sent):
        """Given a latched failing source
        When a scrape succeeds
        Then a recovery push is sent and the state is cleared.
        """
        _fail(db_session, T0)
        sent.clear()
        _succeed(db_session, T0 + timedelta(hours=1))
        assert len(sent) == 1
        assert "recovered" in sent[0][0]
        assert get_scraper_state(db_session, STATE_KEY) is None

    def test_healthy_source_stays_quiet(self, db_session, sent):
        """Given a source that was never failing
        When a scrape succeeds
        Then nothing is sent.
        """
        _succeed(db_session, T0)
        assert sent == []

    def test_latches_without_a_topic(self, db_session, sent):
        """Given no ntfy topic configured
        When a scrape fails
        Then the state still latches and nothing is sent.
        """
        _fail(db_session, T0, topic=None)
        assert sent == []
        assert get_scraper_state(db_session, STATE_KEY) is not None


class TestRealerting:
    """Feature: keep reminding while a source stays broken"""

    def test_one_push_per_interval_not_per_cycle(self, db_session, sent):
        """Given a source failing on every 15-minute cycle
        When a full day passes
        Then exactly one push is sent per interval, not per cycle.
        """
        _fail(db_session, T0)
        sent.clear()
        for cycle in range(1, 24 * 4 + 1):  # 24h of 15-minute cycles
            _fail(db_session, T0 + timedelta(minutes=15 * cycle))
        assert len(sent) == 24 // INTERVAL_H

    def test_realert_reports_elapsed_duration(self, db_session, sent):
        """Given a source that has been failing for over a day
        When the re-alert fires
        Then it names the duration and the reason.
        """
        _fail(db_session, T0)
        sent.clear()
        _fail(db_session, T0 + timedelta(days=1))
        assert len(sent) == 1
        title, body = sent[0]
        assert "still failing" in title
        assert "1d" in title
        assert REASON in body

    def test_zero_disables_realerts(self, db_session, sent):
        """Given re-alerting disabled
        When a source keeps failing for two weeks
        Then no further push is sent.
        """
        _fail(db_session, T0)
        sent.clear()
        with patch("flat_finder.scraper.health.config.SCRAPER_REALERT_HOURS", 0):
            for day in range(1, 15):
                _fail(db_session, T0 + timedelta(days=day))
        assert sent == []

    def test_recovery_after_realerts_still_fires(self, db_session, sent):
        """Given a source that has re-alerted several times
        When it finally succeeds
        Then a recovery push is sent.
        """
        _fail(db_session, T0)
        for day in range(1, 4):
            _fail(db_session, T0 + timedelta(days=day))
        sent.clear()
        _succeed(db_session, T0 + timedelta(days=4))
        assert len(sent) == 1
        assert "recovered" in sent[0][0]


class TestLegacyState:
    """Feature: tolerate rows written before re-alerting existed"""

    def test_bare_reason_string_is_adopted_without_alerting(self, db_session, sent):
        """Given a latched row holding a bare reason string
        When the source fails again
        Then it is adopted quietly rather than re-alerting immediately.
        """
        set_scraper_state(db_session, STATE_KEY, REASON)
        _fail(db_session, T0)
        assert sent == []

    def test_legacy_row_realerts_one_interval_later(self, db_session, sent):
        """Given a legacy row adopted at T0
        When the re-alert interval elapses
        Then it re-alerts like any other failing source.
        """
        set_scraper_state(db_session, STATE_KEY, REASON)
        _fail(db_session, T0)
        _fail(db_session, T0 + timedelta(hours=INTERVAL_H))
        assert len(sent) == 1
        assert "still failing" in sent[0][0]
