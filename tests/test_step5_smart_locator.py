"""Tests for Step 5: SmartLocator wrapper (failure-only retry)."""

import pytest
from playwright.async_api import async_playwright

from src.core import (
    HTMLCapture,
    LocatorGenerator,
    PageIndex,
    PageIndexConfig,
    QueryRetriever,
    SmartLocator,
    SmartLocatorConfig,
)


HTML_CLICK = """
<!DOCTYPE html>
<html>
<body>
    <button id=\"login-btn\" onclick=\"window.clicked = true\">Login</button>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_smart_locator_uses_primary_when_it_works(tmp_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML_CLICK)

        # Index content for retriever, but primary locator should succeed directly.
        capture = HTMLCapture()
        snapshot = await capture.capture_page(page)
        page_index = PageIndex(config=PageIndexConfig(persist_directory=str(tmp_path / "index1")))
        page_index.build_index(snapshot)

        retriever = QueryRetriever(page_index)
        smart = SmartLocator(
            page=page,
            original_locator="#login-btn",
            query_retriever=retriever,
            locator_generator=LocatorGenerator(),
            config=SmartLocatorConfig(max_alternative_attempts=2, action_timeout_ms=1000),
        )

        await smart.click()
        clicked = await page.evaluate("() => window.clicked === true")
        assert clicked is True

        await browser.close()


@pytest.mark.asyncio
async def test_smart_locator_falls_back_only_after_primary_failure(tmp_path):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML_CLICK)

        # Build PageIndex from actual page so fallback can find semantic alternatives.
        capture = HTMLCapture()
        snapshot = await capture.capture_page(page)
        page_index = PageIndex(config=PageIndexConfig(persist_directory=str(tmp_path / "index2")))
        page_index.build_index(snapshot)

        retriever = QueryRetriever(page_index)
        smart = SmartLocator(
            page=page,
            original_locator="#does-not-exist",
            query_retriever=retriever,
            locator_generator=LocatorGenerator(),
            config=SmartLocatorConfig(max_alternative_attempts=3, action_timeout_ms=750),
        )

        # Primary fails, fallback should click the Login button via semantic candidates.
        await smart.click()
        clicked = await page.evaluate("() => window.clicked === true")
        assert clicked is True

        await browser.close()
