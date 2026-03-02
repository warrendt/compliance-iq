"""
Playwright E2E test fixtures.
Starts Streamlit frontend (requires backend at BACKEND_URL or localhost:8000).
"""

import os
import subprocess
import time
import signal
import pytest
from playwright.sync_api import Page


FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")
STREAMLIT_PORT = int(os.getenv("STREAMLIT_TEST_PORT", "8502"))
STREAMLIT_URL = f"http://localhost:{STREAMLIT_PORT}"

# Path to a tiny sample CSV used by upload tests
SAMPLE_CSV = os.path.join(os.path.dirname(__file__), "fixtures", "sample_controls.csv")


@pytest.fixture(scope="session")
def streamlit_server():
    """Launch Streamlit in a subprocess for the test session."""
    proc = subprocess.Popen(
        [
            "streamlit", "run", "app.py",
            "--server.port", str(STREAMLIT_PORT),
            "--server.headless", "true",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=FRONTEND_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env={**os.environ, "BACKEND_URL": os.getenv("BACKEND_URL", "http://localhost:8000")},
    )

    # Wait for Streamlit to be ready (max 30 s)
    import httpx

    for _ in range(60):
        try:
            r = httpx.get(f"{STREAMLIT_URL}/_stcore/health", timeout=2)
            if r.status_code == 200:
                break
        except Exception:
            pass
        time.sleep(0.5)
    else:
        proc.terminate()
        raise RuntimeError("Streamlit did not start in time")

    yield STREAMLIT_URL

    # Teardown
    proc.send_signal(signal.SIGTERM)
    proc.wait(timeout=10)


@pytest.fixture()
def home_page(page: Page, streamlit_server: str) -> Page:
    """Navigate to the Streamlit home page."""
    page.goto(streamlit_server, wait_until="networkidle")
    return page
