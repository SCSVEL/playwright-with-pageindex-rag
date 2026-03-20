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


def _build_modal_extra(encoded_image: str, modal_id: str) -> str:
        image_src = f"data:image/png;base64,{encoded_image}"
        return f"""
<style>
    .sp-thumb {{
        width: 220px;
        max-width: 100%;
        border: 1px solid #d0d7de;
        border-radius: 6px;
        cursor: zoom-in;
    }}
    .sp-modal {{
        display: none;
        position: fixed;
        z-index: 9999;
        inset: 0;
        background: rgba(0, 0, 0, 0.82);
        padding: 24px;
        box-sizing: border-box;
        text-align: center;
    }}
    .sp-modal:target {{
        display: block;
    }}
    .sp-modal img {{
        max-width: min(96vw, 1800px);
        max-height: 90vh;
        margin-top: 24px;
        border-radius: 8px;
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
    }}
    .sp-modal-close {{
        color: #fff;
        text-decoration: none;
        font-size: 26px;
        font-weight: 700;
        position: absolute;
        right: 28px;
        top: 14px;
        line-height: 1;
    }}
</style>
<div>
    <a href="#{modal_id}" title="Click to expand">
        <img class="sp-thumb" src="{image_src}" alt="Failure screenshot" />
    </a>
</div>
<div id="{modal_id}" class="sp-modal">
    <a href="#" class="sp-modal-close" aria-label="Close">×</a>
    <img src="{image_src}" alt="Failure screenshot" />
</div>
"""


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
    modal_id = f"modal_{_safe_nodeid(item.nodeid)}"
    extras.append(pytest_html.extras.html(_build_modal_extra(encoded_image, modal_id)))
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
