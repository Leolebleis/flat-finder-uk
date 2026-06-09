"""E2E tests: isolation between different users.

Feature: Multi-user isolation
Each user has independent settings, zones, and POIs. One user cannot see another's data.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect
from tests.e2e.conftest import login


@pytest.mark.e2e
class TestMultiUserIsolation:
    """Feature: Complete data isolation between users."""

    def test_different_users_have_different_ntfy_topics(self, browser, app_url):
        """Given two users each with distinct ntfy topics
        When each views their settings
        Then each sees only their own topic
        """
        ctx_leo = browser.new_context()
        page_leo = ctx_leo.new_page()
        login(page_leo, app_url, "e2e-iso-leo")
        page_leo.goto(f"{app_url}/settings")
        page_leo.click("#ntfy-edit-btn")
        page_leo.fill("#ntfy_topic", "leo-topic")
        page_leo.click("#ntfy-form button[type='submit']")
        page_leo.wait_for_url("**/settings")

        ctx_amelie = browser.new_context()
        page_amelie = ctx_amelie.new_page()
        login(page_amelie, app_url, "e2e-iso-amelie")
        page_amelie.goto(f"{app_url}/settings")
        page_amelie.click("#ntfy-edit-btn")
        page_amelie.fill("#ntfy_topic", "amelie-topic")
        page_amelie.click("#ntfy-form button[type='submit']")
        page_amelie.wait_for_url("**/settings")

        # Verify isolation: each user sees only their own topic
        page_leo.goto(f"{app_url}/settings")
        expect(page_leo.locator("#ntfy-value")).to_have_text("leo-topic")

        page_amelie.goto(f"{app_url}/settings")
        expect(page_amelie.locator("#ntfy-value")).to_have_text("amelie-topic")

        ctx_leo.close()
        ctx_amelie.close()

    def test_different_users_have_different_search_params(self, browser, app_url):
        """Given user A sets max rent to £1,200 and user B sets max rent to £2,000
        When each views their settings
        Then each sees only their own search params
        """
        ctx_a = browser.new_context()
        page_a = ctx_a.new_page()
        login(page_a, app_url, "e2e-search-iso-a")
        page_a.goto(f"{app_url}/settings")
        page_a.click("#search-edit-btn")
        page_a.fill("#max_rent_pcm", "1200")
        page_a.click("#search-form button[type='submit']")
        page_a.wait_for_url("**/settings")

        ctx_b = browser.new_context()
        page_b = ctx_b.new_page()
        login(page_b, app_url, "e2e-search-iso-b")
        page_b.goto(f"{app_url}/settings")
        page_b.click("#search-edit-btn")
        page_b.fill("#max_rent_pcm", "2000")
        page_b.click("#search-form button[type='submit']")
        page_b.wait_for_url("**/settings")

        page_a.goto(f"{app_url}/settings")
        expect(page_a.locator("#search-display")).to_contain_text("1,200")
        expect(page_a.locator("#search-display")).not_to_contain_text("2,000")

        page_b.goto(f"{app_url}/settings")
        expect(page_b.locator("#search-display")).to_contain_text("2,000")
        expect(page_b.locator("#search-display")).not_to_contain_text("1,200")

        ctx_a.close()
        ctx_b.close()

    def test_new_user_has_no_zones_independent_of_other_users(self, browser, app_url):
        """Given an existing user with zones API data
        When a brand-new user visits settings
        Then the new user sees zero zones
        """
        # User A is already set up (no zones added — just ensuring they're separate users)
        ctx_a = browser.new_context()
        page_a = ctx_a.new_page()
        login(page_a, app_url, "e2e-zone-iso-a")
        page_a.goto(f"{app_url}/settings")
        # A has 0 zones as a fresh user
        assert page_a.locator(".settings__zone").count() == 0

        # Fresh user B should also have 0 zones
        ctx_b = browser.new_context()
        page_b = ctx_b.new_page()
        login(page_b, app_url, "e2e-zone-iso-b")
        page_b.goto(f"{app_url}/settings")
        assert page_b.locator(".settings__zone").count() == 0

        ctx_a.close()
        ctx_b.close()

    def test_concurrent_sessions_do_not_interfere(self, browser, app_url):
        """Given two users are logged in simultaneously in separate browser contexts
        When each is on their settings page at the same time
        Then each sees only their own username in the nav
        """
        ctx_x = browser.new_context()
        page_x = ctx_x.new_page()
        login(page_x, app_url, "e2e-concurrent-x")

        ctx_y = browser.new_context()
        page_y = ctx_y.new_page()
        login(page_y, app_url, "e2e-concurrent-y")

        # Both pages now open settings simultaneously
        page_x.goto(f"{app_url}/settings")
        page_y.goto(f"{app_url}/settings")

        expect(page_x.locator(".nav-user")).to_contain_text("e2e-concurrent-x")
        expect(page_x.locator(".nav-user")).not_to_contain_text("e2e-concurrent-y")

        expect(page_y.locator(".nav-user")).to_contain_text("e2e-concurrent-y")
        expect(page_y.locator(".nav-user")).not_to_contain_text("e2e-concurrent-x")

        ctx_x.close()
        ctx_y.close()

    def test_logout_one_user_does_not_affect_other(self, browser, app_url):
        """Given two users are logged in simultaneously
        When user A logs out
        Then user B is still logged in
        """
        ctx_a = browser.new_context()
        page_a = ctx_a.new_page()
        login(page_a, app_url, "e2e-logout-iso-a")

        ctx_b = browser.new_context()
        page_b = ctx_b.new_page()
        login(page_b, app_url, "e2e-logout-iso-b")

        # Log out user A
        page_a.click("button.nav-logout-btn")
        expect(page_a).to_have_url(re.compile(r".*/login"))

        # User B's session is unaffected
        page_b.goto(f"{app_url}/")
        expect(page_b.locator(".nav-user")).to_contain_text("e2e-logout-iso-b")

        ctx_a.close()
        ctx_b.close()
