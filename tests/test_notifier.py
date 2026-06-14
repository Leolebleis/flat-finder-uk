"""Tests for notification formatting and delivery.

Regression: ntfy notifications were published with the title in an HTTP
``Title`` header, which must be latin-1. A new-listing title always contains
an em-dash (e.g. "2 bed — £2,000/mo"), so every alert crashed with
UnicodeEncodeError and was silently swallowed by the runner's _notify_safe.
send_ntfy now uses ntfy's JSON publishing format (UTF-8 body, no headers).
"""

from unittest.mock import patch

from flat_finder.scraper.notifier import format_ntfy_single, send_ntfy


class TestSendNtfy:
    def test_unicode_title_published_in_json_body(self):
        """Given a title with a non-latin-1 character (em-dash)
        When send_ntfy publishes
        Then it does not raise and the title/message/click sit in the JSON body,
        not in HTTP headers (which would reintroduce the latin-1 crash).
        """
        with patch("flat_finder.scraper.notifier.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            send_ntfy("my-topic", "2 bed — £2,000/mo", "10 Acacia Avenue", click_url="https://example.com/x")

        kwargs = mock_post.call_args.kwargs
        payload = kwargs["json"]
        assert payload == {
            "topic": "my-topic",
            "title": "2 bed — £2,000/mo",
            "message": "10 Acacia Avenue",
            "click": "https://example.com/x",
        }
        # The title must not be sent as a header — that is the latin-1 trap.
        assert "Title" not in (kwargs.get("headers") or {})

    def test_click_url_omitted_when_absent(self):
        """Given no click_url
        When send_ntfy publishes
        Then the payload has no 'click' key.
        """
        with patch("flat_finder.scraper.notifier.requests.post") as mock_post:
            mock_post.return_value.raise_for_status.return_value = None
            send_ntfy("my-topic", "Title", "Body")

        assert "click" not in mock_post.call_args.kwargs["json"]


class TestFormatNtfySingle:
    def test_title_contains_em_dash_for_listing_with_bedrooms(self):
        """Confirms the formatter produces the non-latin-1 title that broke header
        publishing — so the send_ntfy JSON path is exercised end to end."""
        title, _ = format_ntfy_single({"address": "10 Acacia Avenue", "price_pcm": 2000, "bedrooms": 2})
        assert "—" in title
