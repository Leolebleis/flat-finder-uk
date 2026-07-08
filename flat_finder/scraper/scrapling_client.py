"""Fetch pages through the scrapling MCP server (Chrome TLS fingerprint + VPN egress).

The scrapling container exposes an MCP-over-HTTP endpoint (JSON-RPC bodies; replies
are plain JSON or a single-message SSE stream). Its `get` tool fetches with an
impersonated Chrome TLS fingerprint and returns a JSON envelope of the upstream
response: {"status": <http status>, "content": ["<html>", ...]}.

ScraplingSession adapts that endpoint to the small requests surface the scrapers
use (`.get()` returning a Response). On any transport-level failure it degrades to
the direct fallback session for the rest of the run, so scraping never depends on
the scrapling container being up.
"""

import json
import logging
import time

import requests

from flat_finder.scraping import TRANSIENT_STATUSES

log = logging.getLogger("flat-finder")

_MCP_PROTOCOL_VERSION = "2025-03-26"
_MCP_HEADERS = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
_POST_OVERHEAD_SECS = 20
_RETRY_BACKOFF_SECS = (2.0, 4.0)


class ScraplingTransportError(Exception):
    """The MCP endpoint misbehaved at the protocol level (not an upstream HTTP error)."""


def _parse_message(resp: requests.Response) -> dict | None:
    """Decode one JSON-RPC message from a plain-JSON or SSE-framed MCP reply."""
    if "text/event-stream" in resp.headers.get("content-type", ""):
        data = None
        for line in resp.text.splitlines():
            if line.startswith("data:"):
                data = line[len("data:") :]
        return json.loads(data) if data else None
    return resp.json() if resp.content else None


def _as_response(status: int, text: str, url: str) -> requests.Response:
    """Build a real requests.Response for a page fetched via scrapling."""
    resp = requests.Response()
    resp.status_code = status
    resp.url = url
    resp.encoding = "utf-8"
    resp._content = text.encode("utf-8")  # noqa: SLF001 -- requests has no public constructor
    return resp


class ScraplingSession:
    """requests-like session that fetches via the scrapling MCP `get` tool."""

    def __init__(self, mcp_url: str, fallback: requests.Session, http: requests.Session | None = None) -> None:
        self._mcp_url = mcp_url
        self._fallback = fallback
        self._http = http or requests.Session()
        self._session_id: str | None = None
        self._initialized = False
        self._degraded = False
        self._request_id = 0

    def get(self, url: str, *, timeout: float = 30) -> requests.Response:
        if not self._degraded:
            try:
                return self._fetch_with_retry(url, timeout)
            except (requests.RequestException, ScraplingTransportError, ValueError, KeyError, TypeError):
                self._degraded = True
                log.warning(
                    "Scrapling MCP transport failed; falling back to direct fetches for this run",
                    exc_info=True,
                )
        return self._fallback.get(url, timeout=timeout)

    def close(self) -> None:
        """Terminate the server-side MCP session (best effort)."""
        if self._session_id:
            try:
                self._http.delete(self._mcp_url, headers={"mcp-session-id": self._session_id}, timeout=5)
            except requests.RequestException:
                log.debug("Scrapling MCP session delete failed", exc_info=True)
        self._http.close()

    def _fetch_with_retry(self, url: str, timeout: float) -> requests.Response:
        """Retry transient upstream statuses; urllib3's Retry does this on the direct path."""
        resp = self._fetch_via_mcp(url, timeout)
        for backoff in _RETRY_BACKOFF_SECS:
            if resp.status_code not in TRANSIENT_STATUSES:
                break
            time.sleep(backoff)
            resp = self._fetch_via_mcp(url, timeout)
        return resp

    def _fetch_via_mcp(self, url: str, timeout: float) -> requests.Response:
        self._ensure_initialized()
        result = self._call(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "tools/call",
                "params": {
                    "name": "get",
                    "arguments": {
                        "url": url,
                        "impersonate": "chrome",
                        "extraction_type": "html",
                        "main_content_only": False,
                        "stealthy_headers": True,
                        "timeout": timeout,
                    },
                },
            },
            timeout=timeout + _POST_OVERHEAD_SECS,
        )
        if result.get("isError"):
            msg = f"scrapling get tool errored: {str(result)[:200]}"
            raise ScraplingTransportError(msg)
        envelope = json.loads("".join(c.get("text", "") for c in result["content"]))
        parts = envelope["content"]
        if not isinstance(parts, list):
            msg = "scrapling envelope content is not a list"
            raise ScraplingTransportError(msg)
        return _as_response(int(envelope["status"]), "".join(parts), url)

    def _ensure_initialized(self) -> None:
        if self._initialized:
            return
        resp = self._post(
            {
                "jsonrpc": "2.0",
                "id": self._next_id(),
                "method": "initialize",
                "params": {
                    "protocolVersion": _MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "flat-finder", "version": "1.0"},
                },
            },
            timeout=_POST_OVERHEAD_SECS,
        )
        self._session_id = resp.headers.get("mcp-session-id")
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"}, timeout=_POST_OVERHEAD_SECS)
        self._initialized = True

    def _call(self, payload: dict, timeout: float) -> dict:
        message = _parse_message(self._post(payload, timeout=timeout))
        if message is None or "result" not in message:
            msg = f"unexpected MCP reply: {str(message)[:200]}"
            raise ScraplingTransportError(msg)
        return message["result"]

    def _post(self, payload: dict, timeout: float) -> requests.Response:
        headers = dict(_MCP_HEADERS)
        if self._session_id:
            headers["mcp-session-id"] = self._session_id
        resp = self._http.post(self._mcp_url, json=payload, headers=headers, timeout=timeout)
        resp.raise_for_status()
        return resp

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id
