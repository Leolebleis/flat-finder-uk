"""E2E tests: settings page — ntfy, search params, zones.

Feature: Per-user settings
As a logged-in user, I can configure my ntfy topic, search criteria, and view my zones.
"""

from __future__ import annotations

import pytest
from playwright.sync_api import expect
from tests.e2e.conftest import login


@pytest.mark.e2e
class TestNtfySettings:
    """Feature: Per-user ntfy topic configuration."""

    def test_new_user_has_auto_generated_topic(self, page, app_url):
        """Given a new user
        When I visit settings
        Then an ntfy topic is already set (auto-generated with 'flat-finder-' prefix)
        """
        login(page, app_url, "e2e-ntfy-auto")
        page.goto(f"{app_url}/settings")
        expect(page.locator("#ntfy-value")).to_be_visible()
        expect(page.locator("#ntfy-value")).to_contain_text("flat-finder-")

    def test_edit_button_reveals_form(self, page, app_url):
        """Given I am on the settings page
        When I click Edit on the ntfy topic
        Then the edit form becomes visible
        """
        login(page, app_url, "e2e-ntfy-editbtn")
        page.goto(f"{app_url}/settings")
        page.click("#ntfy-edit-btn")
        expect(page.locator("#ntfy-form")).to_be_visible()
        expect(page.locator("#ntfy_topic")).to_be_visible()

    def test_edit_ntfy_topic(self, page, app_url):
        """Given I have an ntfy topic
        When I click Edit, change it, and save
        Then the new topic is displayed on the settings page
        """
        login(page, app_url, "e2e-ntfy-edit")
        page.goto(f"{app_url}/settings")
        page.click("#ntfy-edit-btn")
        page.fill("#ntfy_topic", "my-custom-topic")
        page.click("#ntfy-form button[type='submit']")
        page.wait_for_url("**/settings")
        expect(page.locator("#ntfy-value")).to_have_text("my-custom-topic")

    def test_ntfy_topic_persists_across_page_reload(self, page, app_url):
        """Given I have saved an ntfy topic
        When I reload the settings page
        Then the saved topic is still shown
        """
        login(page, app_url, "e2e-ntfy-persist")
        page.goto(f"{app_url}/settings")
        page.click("#ntfy-edit-btn")
        page.fill("#ntfy_topic", "persisted-topic")
        page.click("#ntfy-form button[type='submit']")
        page.wait_for_url("**/settings")
        page.reload()
        expect(page.locator("#ntfy-value")).to_have_text("persisted-topic")

    def test_copy_button_is_visible(self, page, app_url):
        """Given I have an ntfy topic
        Then a Copy button is visible next to the topic
        """
        login(page, app_url, "e2e-ntfy-copy")
        page.goto(f"{app_url}/settings")
        expect(page.locator("#ntfy-copy-btn")).to_be_visible()

    def test_cancel_edit_restores_display(self, page, app_url):
        """Given I have clicked Edit on the ntfy topic
        When I click Cancel
        Then the display is restored and the form is hidden
        """
        login(page, app_url, "e2e-ntfy-cancel")
        page.goto(f"{app_url}/settings")
        page.click("#ntfy-edit-btn")
        expect(page.locator("#ntfy-form")).to_be_visible()
        page.click("#ntfy-cancel-btn")
        expect(page.locator("#ntfy-display")).to_be_visible()
        expect(page.locator("#ntfy-form")).to_be_hidden()


@pytest.mark.e2e
class TestSearchParamsSettings:
    """Feature: Per-user search criteria."""

    def test_new_user_has_default_max_rent(self, page, app_url):
        """Given a new user (default max_rent_pcm=2200)
        When I visit settings
        Then the search display shows £2,200
        """
        login(page, app_url, "e2e-search-default")
        page.goto(f"{app_url}/settings")
        expect(page.locator("#search-display")).to_be_visible()
        expect(page.locator("#search-display")).to_contain_text("2,200")

    def test_edit_search_params_saves_max_rent(self, page, app_url):
        """Given I visit settings and click Edit on search params
        When I change max rent to £1,500 and save
        Then the settings page shows £1,500
        """
        login(page, app_url, "e2e-search-edit")
        page.goto(f"{app_url}/settings")
        page.click("#search-edit-btn")
        page.fill("#max_rent_pcm", "1500")
        page.click("#search-form button[type='submit']")
        page.wait_for_url("**/settings")
        expect(page.locator("#search-display")).to_contain_text("1,500")

    def test_edit_search_params_with_bedrooms(self, page, app_url):
        """Given I edit search params with min/max bedrooms
        When I save
        Then the settings page shows the bedroom range
        """
        login(page, app_url, "e2e-search-beds")
        page.goto(f"{app_url}/settings")
        page.click("#search-edit-btn")
        page.fill("#max_rent_pcm", "1800")
        page.fill("#min_bedrooms", "1")
        page.fill("#max_bedrooms", "2")
        page.click("#search-form button[type='submit']")
        page.wait_for_url("**/settings")
        expect(page.locator("#search-display")).to_contain_text("1,800")
        expect(page.locator("#search-display")).to_contain_text("1-2 bed")

    def test_search_params_persist_across_reload(self, page, app_url):
        """Given I have saved search params
        When I reload the settings page
        Then the saved params are still shown
        """
        login(page, app_url, "e2e-search-persist")
        page.goto(f"{app_url}/settings")
        page.click("#search-edit-btn")
        page.fill("#max_rent_pcm", "1600")
        page.click("#search-form button[type='submit']")
        page.wait_for_url("**/settings")
        page.reload()
        expect(page.locator("#search-display")).to_contain_text("1,600")

    def test_cancel_search_edit_restores_display(self, page, app_url):
        """Given I have clicked Edit on search params
        When I click Cancel
        Then the display is restored and the form is hidden
        """
        login(page, app_url, "e2e-search-cancel")
        page.goto(f"{app_url}/settings")
        page.click("#search-edit-btn")
        expect(page.locator("#search-form")).to_be_visible()
        page.click("#search-cancel-btn")
        expect(page.locator("#search-display")).to_be_visible()
        expect(page.locator("#search-form")).to_be_hidden()


@pytest.mark.e2e
class TestZonesSettings:
    """Feature: Zone list display on settings page."""

    def test_new_user_has_no_zones(self, page, app_url):
        """Given a new user
        When I visit settings
        Then no zone entries are shown
        """
        login(page, app_url, "e2e-zones-new")
        page.goto(f"{app_url}/settings")
        expect(page.locator(".settings__zone")).to_have_count(0)

    def test_empty_zone_state_shown(self, page, app_url):
        """Given a new user with no zones
        When I visit settings
        Then the empty state message is displayed
        """
        login(page, app_url, "e2e-zones-empty")
        page.goto(f"{app_url}/settings")
        expect(page.locator("#zone-empty")).to_be_visible()

    def test_add_zone_button_is_visible(self, page, app_url):
        """Given I am on the settings page
        Then the Add Zone button is visible
        """
        login(page, app_url, "e2e-zones-addbtn")
        page.goto(f"{app_url}/settings")
        expect(page.locator("#add-zone-btn")).to_be_visible()

    def test_add_zone_opens_editor(self, page, app_url):
        """Given I am on the settings page
        When I click Add Zone
        Then the zone editor panel is revealed
        """
        login(page, app_url, "e2e-zones-editor")
        page.goto(f"{app_url}/settings")
        page.click("#add-zone-btn")
        expect(page.locator("#zone-editor")).to_be_visible()

    def test_zone_editor_cancel_hides_editor(self, page, app_url):
        """Given the zone editor is open
        When I click Cancel
        Then the editor is hidden
        """
        login(page, app_url, "e2e-zones-canceleditor")
        page.goto(f"{app_url}/settings")
        page.click("#add-zone-btn")
        expect(page.locator("#zone-editor")).to_be_visible()
        page.click("#zone-cancel-btn")
        expect(page.locator("#zone-editor")).to_be_hidden()
