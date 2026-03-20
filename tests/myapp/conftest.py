"""Fixtures for myapp tests with SmartPage support."""

import base64
from datetime import datetime
from pathlib import Path

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright

from src.core import (
    SmartEngine,
    SmartLocatorConfig,
    SmartPage,
    register_smartlabels_selector,
)


RESULTS_DIR = Path("playwright-results") / "screenshots"


def _safe_nodeid(nodeid: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in nodeid)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store phase reports and attach screenshot extras for failed test calls."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)

    if rep.when != "teardown":
        return

    rep_call = getattr(item, "rep_call", None)
    screenshot_path = getattr(item, "_failure_screenshot_path", None)
    if not rep_call or not rep_call.failed or not screenshot_path:
        return

    pytest_html = item.config.pluginmanager.getplugin("html")
    if not pytest_html:
        return

    extras = getattr(rep, "extras", [])
    image_bytes = Path(screenshot_path).read_bytes()
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    extras.append(pytest_html.extras.png(encoded_image))
    extras.append(pytest_html.extras.url(str(screenshot_path), name="Screenshot file"))
    rep.extras = extras


@pytest_asyncio.fixture
async def smart_page(tmp_path, request):
    async with async_playwright() as p:
        await register_smartlabels_selector(p)

        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        engine = SmartEngine(
            persist_directory=str(tmp_path / "smart_runtime_index"),
            smart_config=SmartLocatorConfig(max_alternative_attempts=4, action_timeout_ms=1500),
        )

        request.node._playwright_page = page
        yield SmartPage(page, engine)

        rep_call = getattr(request.node, "rep_call", None)
        if rep_call and rep_call.failed:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            screenshot_name = f"{_safe_nodeid(request.node.nodeid)}_{timestamp}.png"
            screenshot_path = RESULTS_DIR / screenshot_name

            try:
                await page.screenshot(path=str(screenshot_path), full_page=True)
                request.node._failure_screenshot_path = screenshot_path
            except Exception:
                # Best-effort screenshot capture should never fail the test run.
                request.node._failure_screenshot_path = None

        await browser.close()
