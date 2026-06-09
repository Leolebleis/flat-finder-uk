"""E2E tests: feed page renders and nav highlights.

Feature: Feed page
As a logged-in user, I can view the feed page and navigate the app.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect
from tests.e2e.conftest import login


@pytest.mark.e2e
class TestFeedPage:
    """Feature: Feed page renders for any logged-in user."""

    def test_feed_renders_for_new_user(self, page, app_url):
        """Given a new user with no zones
        When I view the feed
        Then the page loads without errors and shows the nav
        """
        login(page, app_url, "e2e-newuser-feed")
        expect(page.locator("nav.nav")).to_be_visible()
        expect(page.locator(".nav__brand")).to_contain_text("Flat Finder")

    def test_feed_page_title(self, page, app_url):
        """Given I am on the feed page
        Then the browser title contains 'Flat Finder'
        """
        login(page, app_url, "e2e-feedtitle")
        expect(page).to_have_title(re.compile(r"Flat Finder", re.IGNORECASE))

    def test_nav_highlights_feed(self, page, app_url):
        """Given I am on the feed page
        Then the Feed nav link has the active class
        """
        login(page, app_url, "e2e-nav-feed")
        expect(page.locator(".nav__link--active")).to_have_text("Feed")

    def test_nav_links_present(self, page, app_url):
        """Given I am logged in
        Then the nav shows Feed, Map, and Settings links
        """
        login(page, app_url, "e2e-navlinks")
        nav_links = page.locator(".nav__links .nav__link")
        expect(nav_links).to_have_count(3)
        expect(nav_links.nth(0)).to_have_text("Feed")
        expect(nav_links.nth(1)).to_have_text("Map")
        expect(nav_links.nth(2)).to_have_text("Settings")

    def test_nav_shows_username_and_logout(self, page, app_url):
        """Given I am logged in as a specific user
        Then the nav shows my username and a Logout button
        """
        login(page, app_url, "e2e-navuser")
        expect(page.locator(".nav-user")).to_contain_text("e2e-navuser")
        expect(page.locator("button.nav-logout-btn")).to_be_visible()

    def test_settings_nav_link_navigates(self, page, app_url):
        """Given I am on the feed
        When I click the Settings nav link
        Then I land on the settings page
        """
        login(page, app_url, "e2e-settingsnav")
        page.click(".nav__links a:has-text('Settings')")
        page.wait_for_url("**/settings")
        expect(page.locator(".nav__link--active")).to_have_text("Settings")

    def test_nav_highlights_settings(self, page, app_url):
        """Given I am on the settings page
        Then the Settings nav link has the active class
        """
        login(page, app_url, "e2e-nav-settings")
        page.goto(f"{app_url}/settings")
        expect(page.locator(".nav__link--active")).to_have_text("Settings")
