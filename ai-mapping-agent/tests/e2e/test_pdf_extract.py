"""E2E: PDF extract-and-bridge flow — Page 5."""

import pytest
from playwright.sync_api import Page, expect


def test_pdf_pipeline_page_loads(home_page: Page):
    """Navigate to PDF Pipeline page."""
    home_page.get_by_text("PDF Pipeline").first.click()
    home_page.wait_for_url("**/PDF_Pipeline**", timeout=10_000)
    expect(home_page.locator("text=PDF")).to_be_visible()


def test_pdf_page_shows_upload_widget(home_page: Page):
    """Page 5 contains a file-upload input for PDFs."""
    home_page.get_by_text("PDF Pipeline").first.click()
    home_page.wait_for_url("**/PDF_Pipeline**", timeout=10_000)

    file_input = home_page.locator('input[type="file"]')
    expect(file_input).to_be_attached(timeout=5_000)
