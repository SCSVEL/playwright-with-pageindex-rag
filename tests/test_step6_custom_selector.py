"""Tests for Step 6: Custom selector registration (smartlabels)."""

import pytest
from playwright.async_api import async_playwright

from src.core import register_smartlabels_selector, build_smartlabels_locator_value


HTML_FORM = """
<!DOCTYPE html>
<html>
<body>
  <form>
    <label for="first-name">First Name</label>
    <input id="first-name" name="firstName" placeholder="FirstName" />

    <button type="button">Save</button>
  </form>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_register_smartlabels_and_locate_input_by_multiple_labels():
    async with async_playwright() as p:
        await register_smartlabels_selector(p)

        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML_FORM)

        selector_value = build_smartlabels_locator_value(["First Name", "FirstName"])
        target = page.locator(f"smartlabels={selector_value}")

        await target.fill("Alice")

        value = await page.locator("#first-name").input_value()
        assert value == "Alice"

        await browser.close()


@pytest.mark.asyncio
async def test_smartlabels_can_click_button_by_text():
    async with async_playwright() as p:
        await register_smartlabels_selector(p)

        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML_FORM)

        await page.evaluate("() => { window.clicked = false; document.querySelector('button').addEventListener('click', () => window.clicked = true); }")

        button = page.locator("smartlabels=Save")
        await button.click()

        clicked = await page.evaluate("() => window.clicked")
        assert clicked is True

        await browser.close()
