"""Tests for the scrapling MCP transport used for Rightmove fetches."""

import json
from unittest.mock import Mock

import pytest
import requests
from flat_finder.scraper.scrapling_client import ScraplingSession

MCP_URL = "http://scrapling.test:8765/mcp"
SESSION_ID = "sess-123"

INIT_RESULT = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {"serverInfo": {"name": "Scrapling"}, "capabilities": {}},
}


def _mcp_response(payload: dict | None, *, sse: bool = False, session_id: str | None = None) -> Mock:
    """A mocked requests.Response carrying one JSON-RPC message, JSON or SSE framed."""
    headers = {"content-type": "text/event-stream" if sse else "application/json"}
    if session_id:
        headers["mcp-session-id"] = session_id
    resp = Mock(status_code=200, headers=headers)
    if payload is None:
        resp.text = ""
    elif sse:
        resp.text = f"event: message\ndata: {json.dumps(payload)}\n\n"
    else:
        resp.text = json.dumps(payload)
        resp.json = Mock(return_value=payload)
    resp.content = resp.text.encode()
    return resp


def _tool_result(envelope: dict, *, sse: bool = False) -> Mock:
    """A tools/call response whose content text is the scrapling JSON envelope."""
    payload = {
        "jsonrpc": "2.0",
        "id": 2,
        "result": {
            "content": [{"type": "text", "text": json.dumps(envelope)}],
            "isError": False,
        },
    }
    return _mcp_response(payload, sse=sse)


def _handshake_responses() -> list[Mock]:
    """initialize response (with session id) + initialized-notification ack."""
    return [
        _mcp_response(INIT_RESULT, session_id=SESSION_ID),
        _mcp_response(None),
    ]


class TestScraplingSessionFetch:
    """Feature: fetch pages through the scrapling MCP server"""

    def test_returns_upstream_html_from_envelope(self):
        """Given the MCP server returns a 200 envelope with HTML content
        When I get a URL
        Then the response exposes the upstream HTML and status like requests would.
        """
        http = Mock()
        http.post.side_effect = [
            *_handshake_responses(),
            _tool_result({"status": 200, "content": ["<html>", "__NEXT_DATA__ page</html>"]}),
        ]
        session = ScraplingSession(MCP_URL, fallback=Mock(), http=http)

        resp = session.get("https://www.rightmove.co.uk/find.html")

        assert resp.status_code == 200
        assert resp.text == "<html>__NEXT_DATA__ page</html>"
        resp.raise_for_status()  # must not raise

    def test_parses_sse_framed_responses(self):
        """Given the MCP server frames its reply as text/event-stream
        When I get a URL
        Then the envelope is still decoded from the data: line.
        """
        http = Mock()
        http.post.side_effect = [
            *_handshake_responses(),
            _tool_result({"status": 200, "content": ["<html>ok</html>"]}, sse=True),
        ]
        session = ScraplingSession(MCP_URL, fallback=Mock(), http=http)

        resp = session.get("https://www.rightmove.co.uk/find.html")

        assert resp.text == "<html>ok</html>"

    def test_upstream_error_status_raises_on_raise_for_status(self, monkeypatch: pytest.MonkeyPatch):
        """Given the upstream site answers 503 through scrapling on every retry
        When I get a URL and call raise_for_status
        Then requests.HTTPError is raised so callers keep their error handling.
        """
        monkeypatch.setattr("flat_finder.scraper.scrapling_client.time.sleep", lambda _: None)
        http = Mock()
        http.post.side_effect = [
            *_handshake_responses(),
            _tool_result({"status": 503, "content": ["unavailable"]}),
            _tool_result({"status": 503, "content": ["unavailable"]}),
            _tool_result({"status": 503, "content": ["unavailable"]}),
        ]
        session = ScraplingSession(MCP_URL, fallback=Mock(), http=http)

        resp = session.get("https://www.rightmove.co.uk/find.html")

        assert resp.status_code == 503
        with pytest.raises(requests.HTTPError):
            resp.raise_for_status()


class TestScraplingSessionHandshake:
    """Feature: one MCP handshake per session, session id reused on every call"""

    def test_initializes_once_and_reuses_session_id(self):
        """Given two fetches on one session
        When I inspect the MCP posts
        Then initialize ran once and later calls carry the negotiated session id.
        """
        http = Mock()
        http.post.side_effect = [
            *_handshake_responses(),
            _tool_result({"status": 200, "content": ["a"]}),
            _tool_result({"status": 200, "content": ["b"]}),
        ]
        session = ScraplingSession(MCP_URL, fallback=Mock(), http=http)

        session.get("https://example.com/1")
        session.get("https://example.com/2")

        assert http.post.call_count == 4  # initialize, initialized, 2 tool calls
        tool_call_headers = http.post.call_args_list[3].kwargs["headers"]
        assert tool_call_headers["mcp-session-id"] == SESSION_ID


class TestScraplingSessionFallback:
    """Feature: degrade to the direct session when the scrapling endpoint fails"""

    def test_falls_back_to_direct_session_when_endpoint_unreachable(self):
        """Given the MCP endpoint refuses connections
        When I get a URL
        Then the direct fallback session serves the request.
        """
        http = Mock()
        http.post.side_effect = requests.ConnectionError("refused")
        fallback = Mock()
        fallback.get.return_value = Mock(status_code=200, text="<html>direct</html>")
        session = ScraplingSession(MCP_URL, fallback=fallback, http=http)

        resp = session.get("https://www.rightmove.co.uk/find.html")

        assert resp.text == "<html>direct</html>"
        fallback.get.assert_called_once()

    def test_stays_degraded_after_transport_failure(self):
        """Given a transport failure already degraded the session
        When I get another URL
        Then the MCP endpoint is not retried within this run.
        """
        http = Mock()
        http.post.side_effect = requests.ConnectionError("refused")
        fallback = Mock()
        fallback.get.return_value = Mock(status_code=200, text="direct")
        session = ScraplingSession(MCP_URL, fallback=fallback, http=http)

        session.get("https://example.com/1")
        posts_after_first = http.post.call_count
        session.get("https://example.com/2")

        assert http.post.call_count == posts_after_first
        assert fallback.get.call_count == 2

    @pytest.mark.parametrize(
        "result",
        [
            pytest.param(
                {"content": [{"type": "text", "text": "not-json"}], "isError": False}, id="malformed-envelope"
            ),
            pytest.param({"content": [{"type": "text", "text": "boom"}], "isError": True}, id="tool-error"),
        ],
    )
    def test_bad_tool_reply_falls_back(self, result: dict):
        """Given the tool reply is unusable (malformed envelope or execution error)
        When I get a URL
        Then the direct fallback session serves the request.
        """
        http = Mock()
        payload = {"jsonrpc": "2.0", "id": 2, "result": result}
        http.post.side_effect = [*_handshake_responses(), _mcp_response(payload)]
        fallback = Mock()
        fallback.get.return_value = Mock(status_code=200, text="direct")
        session = ScraplingSession(MCP_URL, fallback=fallback, http=http)

        resp = session.get("https://www.rightmove.co.uk/find.html")

        assert resp.text == "direct"


class TestScraplingSessionRetry:
    """Feature: transient upstream statuses retry on the MCP path like the direct path"""

    def test_retries_transient_status_then_succeeds(self, monkeypatch: pytest.MonkeyPatch):
        """Given the upstream answers 503 then 200 through scrapling
        When I get a URL
        Then the 200 response is returned without degrading the session.
        """
        monkeypatch.setattr("flat_finder.scraper.scrapling_client.time.sleep", lambda _: None)
        http = Mock()
        http.post.side_effect = [
            *_handshake_responses(),
            _tool_result({"status": 503, "content": ["unavailable"]}),
            _tool_result({"status": 200, "content": ["<html>ok</html>"]}),
        ]
        fallback = Mock()
        session = ScraplingSession(MCP_URL, fallback=fallback, http=http)

        resp = session.get("https://www.rightmove.co.uk/find.html")

        assert resp.status_code == 200
        assert resp.text == "<html>ok</html>"
        fallback.get.assert_not_called()


class TestScraplingSessionClose:
    """Feature: terminate the server-side MCP session at end of run"""

    def test_close_deletes_negotiated_session(self):
        """Given a session that completed the handshake
        When I close it
        Then an HTTP DELETE with the session id terminates the server-side session.
        """
        http = Mock()
        http.post.side_effect = [
            *_handshake_responses(),
            _tool_result({"status": 200, "content": ["ok"]}),
        ]
        session = ScraplingSession(MCP_URL, fallback=Mock(), http=http)
        session.get("https://example.com/")

        session.close()

        http.delete.assert_called_once()
        assert http.delete.call_args.kwargs["headers"]["mcp-session-id"] == SESSION_ID

    def test_close_without_handshake_sends_no_delete(self):
        """Given a session that never fetched anything
        When I close it
        Then no DELETE is sent (there is no server-side session to terminate).
        """
        http = Mock()
        session = ScraplingSession(MCP_URL, fallback=Mock(), http=http)

        session.close()

        http.delete.assert_not_called()
