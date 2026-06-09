"""E2E test fixtures: live uvicorn server + shared login helper."""

from __future__ import annotations

import os
import time
from multiprocessing import Process

import httpx
import pytest
import uvicorn


def _run_server(db_path: str, secret_key: str) -> None:
    """Entry point for the server subprocess."""
    os.environ["FLAT_FINDER_DB"] = db_path
    os.environ["SECRET_KEY"] = secret_key
    import importlib  # noqa: PLC0415

    import flat_finder.config  # noqa: PLC0415

    importlib.reload(flat_finder.config)
    uvicorn.run("flat_finder.api.app:app", host="127.0.0.1", port=8765, log_level="warning")


@pytest.fixture(scope="session")
def live_server(tmp_path_factory):
    """Start a real uvicorn server with a fresh DB for the entire E2E session."""
    db_path = tmp_path_factory.mktemp("e2e") / "test.db"

    # Set env vars before spawning so the child process inherits them
    os.environ["FLAT_FINDER_DB"] = str(db_path)
    os.environ["SECRET_KEY"] = "e2e-test-secret"  # noqa: S105

    proc = Process(target=_run_server, args=(str(db_path), "e2e-test-secret"), daemon=True)
    proc.start()

    # Wait for server to be ready (up to 5 s)
    for _ in range(50):
        try:
            httpx.get("http://127.0.0.1:8765/flat/login", timeout=1)
            break
        except (httpx.ConnectError, httpx.TimeoutException):
            time.sleep(0.1)
    else:
        proc.kill()
        msg = "Live server failed to start within 5 seconds"
        raise RuntimeError(msg)

    yield "http://127.0.0.1:8765/flat"
    proc.kill()


@pytest.fixture
def app_url(live_server):
    """Base URL for page.goto() calls — includes the /flat root_path."""
    return live_server


def login(page, app_url: str, username: str) -> None:
    """Log in as *username*. Creates the user automatically on first login."""
    page.goto(f"{app_url}/login")
    page.fill("input[name='username']", username)
    page.click("button[type='submit']")
    # Wait for the redirect to complete (away from /login)
    page.wait_for_url(lambda url: "/login" not in url, timeout=5000)


@pytest.fixture
def logged_in_page(page, app_url):
    """A page already logged in as 'e2e-default'."""
    login(page, app_url, "e2e-default")
    return page
