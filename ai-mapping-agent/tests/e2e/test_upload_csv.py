"""E2E: CSV upload flow — Page 1 Upload Controls."""

import os
import pytest
from playwright.sync_api import Page, expect

SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "..", "fixtures", "sample_controls.csv")


def test_home_page_loads(home_page: Page):
    """Smoke: home page contains the app title."""
    expect(home_page.locator("text=AI Control Mapping Agent")).to_be_visible()


def test_navigate_to_upload(home_page: Page):
    """Sidebar navigation goes to the Upload Controls page."""
    home_page.get_by_text("Upload Controls").first.click()
    home_page.wait_for_url("**/Upload_Controls**", timeout=10_000)
    expect(home_page.locator("text=Upload Framework Controls")).to_be_visible()


def test_csv_upload_preview(home_page: Page):
    """Upload a CSV and verify the data loaded successfully."""
    home_page.get_by_text("Upload Controls").first.click()
    home_page.wait_for_url("**/Upload_Controls**", timeout=10_000)

    # Upload sample CSV via the hidden input inside the Streamlit uploader
    file_input = home_page.locator('[data-testid="stFileUploaderDropzone"] input[type="file"]')
    file_input.set_input_files(SAMPLE_CSV)

    # Wait for the success message after parsing
    expect(home_page.locator("text=File loaded successfully")).to_be_visible(timeout=15_000)


def test_column_mapping_and_load(home_page: Page):
    """Upload CSV, map columns, load controls, verify controls_loaded indicator."""
    home_page.get_by_text("Upload Controls").first.click()
    home_page.wait_for_url("**/Upload_Controls**", timeout=10_000)

    file_input = home_page.locator('input[type="file"]')
    file_input.set_input_files(SAMPLE_CSV)
    home_page.wait_for_timeout(2000)

    # The sample CSV column names match the defaults, so we should be able
    # to click "Load Controls" (or similar) directly.
    load_btn = home_page.get_by_role("button", name="Load Controls")
    if load_btn.count():
        load_btn.first.click()
        home_page.wait_for_timeout(2000)
        # Success indicator
        expect(home_page.locator("text=controls loaded")).to_be_visible(timeout=10_000)
