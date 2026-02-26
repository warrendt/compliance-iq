"""E2E: Review & Export pages (sanity checks without live mappings)."""

import pytest
from playwright.sync_api import Page, expect


def test_review_page_warns_no_mappings(home_page: Page):
    """Page 3 shows a warning when no mappings exist."""
    home_page.get_by_text("Review").first.click()
    home_page.wait_for_url("**/Review_Edit**", timeout=10_000)
    expect(home_page.locator("text=No mappings")).to_be_visible(timeout=5_000)


def test_export_page_warns_no_mappings(home_page: Page):
    """Page 4 shows a warning when no mappings exist."""
    home_page.get_by_text("Export").first.click()
    home_page.wait_for_url("**/Export_Policy**", timeout=10_000)
    expect(home_page.locator("text=No mappings")).to_be_visible(timeout=5_000)
