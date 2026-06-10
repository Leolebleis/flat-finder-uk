"""E2E tests: login, logout, session persistence.

Feature: User Authentication
As a user, I can log in with my username and my session persists across pages.
"""

from __future__ import annotations

import re

import pytest
from playwright.sync_api import expect
from tests.e2e.conftest import login


@pytest.mark.e2e
class TestLoginFlow:
    """Feature: User Authentication"""

    def test_unauthenticated_redirects_to_login(self, page, app_url):
        """Given I am not logged in
        When I visit the feed
        Then I am redirected to the login page
        """
        page.goto(f"{app_url}/")
        expect(page).to_have_url(re.compile(r".*/login"))

    def test_login_page_has_accessible_form(self, page, app_url):
        """Given I am on the login page
        Then there is a labeled username input and a submit button
        """
        page.goto(f"{app_url}/login")
        expect(page.locator("label[for='username']")).to_be_visible()
        expect(page.locator("input[name='username']")).to_be_visible()
        expect(page.locator("button[type='submit']")).to_be_visible()

    def test_login_creates_user_and_redirects_to_feed(self, page, app_url):
        """Given I enter a new username
        When I submit the login form
        Then I am redirected to the feed and my username appears in the nav
        """
        page.goto(f"{app_url}/login")
        page.fill("input[name='username']", "e2e-alice")
        page.click("button[type='submit']")
        expect(page).to_have_url(re.compile(r".*/(?:$|\?)"))
        expect(page.locator(".nav-user")).to_contain_text("e2e-alice")

    def test_empty_username_stays_on_login(self, page, app_url):
        """Given I submit an empty username
        Then I remain on the login page with an error message
        """
        page.goto(f"{app_url}/login")
        # Clear the field (it may be pre-filled) and submit
        page.fill("input[name='username']", "")
        page.click("button[type='submit']")
        expect(page).to_have_url(re.compile(r".*/login"))

    def test_login_normalizes_username_to_lowercase(self, page, app_url):
        """Given I enter an uppercase username
        When I submit the login form
        Then my username is stored and displayed lowercase
        """
        page.goto(f"{app_url}/login")
        page.fill("input[name='username']", "E2E-CaseUser")
        page.click("button[type='submit']")
        expect(page.locator(".nav-user")).to_contain_text("e2e-caseuser")

    def test_session_persists_across_navigation(self, page, app_url):
        """Given I am logged in
        When I navigate to settings and back to feed
        Then I remain logged in throughout
        """
        login(page, app_url, "e2e-persist")
        page.goto(f"{app_url}/settings")
        expect(page.locator(".nav-user")).to_contain_text("e2e-persist")
        page.goto(f"{app_url}/")
        expect(page.locator(".nav-user")).to_contain_text("e2e-persist")

    def test_returning_user_can_log_in_again(self, page, app_url):
        """Given a user who has logged in before
        When they log in again with the same username
        Then they land on the feed with their username shown
        """
        login(page, app_url, "e2e-returning")
        page.goto(f"{app_url}/login")
        page.fill("input[name='username']", "e2e-returning")
        page.click("button[type='submit']")
        expect(page).to_have_url(re.compile(r".*/(?:$|\?)"))
        expect(page.locator(".nav-user")).to_contain_text("e2e-returning")


@pytest.mark.e2e
class TestLogoutFlow:
    """Feature: User Logout"""

    def test_logout_redirects_to_login(self, page, app_url):
        """Given I am logged in
        When I click Logout
        Then I am redirected to the login page
        """
        login(page, app_url, "e2e-logout")
        page.click("button.nav-logout-btn")
        expect(page).to_have_url(re.compile(r".*/login"))

    def test_after_logout_feed_requires_login(self, page, app_url):
        """Given I have logged out
        When I navigate to the feed
        Then I am redirected to the login page
        """
        login(page, app_url, "e2e-logout2")
        page.click("button.nav-logout-btn")
        page.goto(f"{app_url}/")
        expect(page).to_have_url(re.compile(r".*/login"))

    def test_after_logout_settings_requires_login(self, page, app_url):
        """Given I have logged out
        When I navigate to settings
        Then I am redirected to the login page
        """
        login(page, app_url, "e2e-logout3")
        page.click("button.nav-logout-btn")
        page.goto(f"{app_url}/settings")
        expect(page).to_have_url(re.compile(r".*/login"))
