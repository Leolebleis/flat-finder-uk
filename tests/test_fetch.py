"""Tests for the resilient HTTP fetch behaviour (retry config + partial pagination)."""

import json
from unittest.mock import Mock

import pytest
import requests
from flat_finder.scraper.rightmove import fetch_rightmove
from flat_finder.scraping import RETRYABLE_STATUSES, make_retry_session


def _rightmove_page_html(result_count: int, prop_id: int) -> str:
    """Minimal Rightmove search page with one property and a __NEXT_DATA__ blob."""
    next_data = {
        "props": {
            "pageProps": {
                "searchResults": {
                    "resultCount": str(result_count),
                    "properties": [
                        {
                            "id": prop_id,
                            "propertyUrl": f"/properties/{prop_id}",
                            "propertyTypeFullDescription": "1 bedroom flat",
                            "summary": "A nice flat",
                            "displayAddress": "1 Test Street, NW6",
                            "price": {"amount": 1500, "frequency": "monthly"},
                            "bedrooms": 1,
                            "location": {"latitude": 51.5, "longitude": -0.1},
                            "propertyImages": {"images": []},
                        }
                    ],
                }
            }
        }
    }
    return f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(next_data)}</script>'


def _ok_response(html: str) -> Mock:
    resp = Mock(status_code=200, text=html)
    resp.raise_for_status = Mock()
    return resp


def _error_response(status: int) -> Mock:
    resp = Mock(status_code=status, text="")
    resp.raise_for_status.side_effect = requests.HTTPError(f"{status} Server Error")
    return resp


class TestRetrySession:
    """Feature: shared requests session with retry/backoff for transient failures"""

    def test_retries_configured_for_transient_statuses(self):
        """Given the shared retry session
        When I inspect its adapter's Retry config
        Then transient statuses (429/5xx) are retried with backoff.
        """
        session = make_retry_session()
        retry = session.get_adapter("https://www.rightmove.co.uk").max_retries

        assert retry.total >= 3
        for status in RETRYABLE_STATUSES:
            assert status in retry.status_forcelist
        assert retry.backoff_factor > 0
        assert retry.respect_retry_after_header is True

    def test_default_headers_applied(self):
        """Given the shared retry session
        When I inspect its default headers
        Then the coherent browser headers are set session-wide.
        """
        session = make_retry_session()
        assert "Mozilla" in session.headers["User-Agent"]
        assert "Accept-Language" in session.headers


class TestFetchRightmovePartialResults:
    """Feature: keep already-fetched pages when a later page fails mid-pagination"""

    def test_returns_earlier_pages_when_later_page_503s(self):
        """Given page 1 succeeds and page 2 returns a 503
        When I fetch a zone
        Then the page-1 listings are returned instead of losing the whole zone.
        """
        session = Mock()
        session.get.side_effect = [_ok_response(_rightmove_page_html(48, 1)), _error_response(503)]

        listings = fetch_rightmove("REGION^1", 1.0, 1, 2, 2000, session=session)

        assert [item["id"] for item in listings] == ["rightmove_1"]

    def test_returns_earlier_pages_when_later_page_has_no_next_data(self):
        """Given page 1 succeeds and page 2 serves HTML without __NEXT_DATA__ (challenge page)
        When I fetch a zone
        Then the page-1 listings are returned.
        """
        session = Mock()
        session.get.side_effect = [
            _ok_response(_rightmove_page_html(48, 1)),
            _ok_response("<html>please verify you are human</html>"),
        ]

        listings = fetch_rightmove("REGION^1", 1.0, 1, 2, 2000, session=session)

        assert [item["id"] for item in listings] == ["rightmove_1"]

    def test_first_page_failure_still_raises(self):
        """Given the first page fails
        When I fetch a zone
        Then the error propagates so the runner records the source failure.
        """
        session = Mock()
        session.get.return_value = _error_response(503)

        with pytest.raises(requests.HTTPError):
            fetch_rightmove("REGION^1", 1.0, 1, 2, 2000, session=session)
