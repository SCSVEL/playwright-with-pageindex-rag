"""Real register test using SmartPage APIs with command-only test body."""

import time

import pytest


@pytest.mark.asyncio
async def test_register_site(smart_page):
    """
    This is to show how to use SmartPage both with explicit SmartLocator commands
    and normal Playwright-style commands for fallback 
    """ 
    username = f"autouser-{int(time.time())}"
    password = "P@ssw0rd123!"

    await smart_page.goto("https://practice.expandtesting.com/register", wait_until="domcontentloaded")

    # Explicit SmartLocator usage as a Playwright-like command.
    await smart_page.smartlocator(texts=["Username"]).fill(username)

    # Normal Playwright-style commands.
    await smart_page.locator("#password").fill(password)
    await smart_page.locator("#confirmPassword").fill(password)

    # This locator is intentionally wrong; internal fallback should click Register.
    await smart_page.locator("#register-submit-does-not-exist").click()

    await smart_page.wait_for_url("**/login", wait_until="domcontentloaded", timeout=10_000)
    body_text = await smart_page.locator("body").inner_text()

    assert smart_page.url.endswith("/login")
    assert "Successfully registered, you can log in now." in body_text


@pytest.mark.asyncio
async def test_another_site(smart_page):
    username = "student"
    password = "Password123"

    await smart_page.goto("https://practicetestautomation.com/practice-test-login/", wait_until="domcontentloaded")

    # Explicit SmartLocator usage as a Playwright-like command.
    await smart_page.smartlocator(texts=["Username"]).fill(username)

    # Normal Playwright-style commands.
    await smart_page.locator("#password").fill(password)    

    # This locator is intentionally wrong; internal fallback should click submit.
    await smart_page.locator("#submit-does-not-exist").click()

    await smart_page.wait_for_url("**/logged-in-successfully/", wait_until="domcontentloaded", timeout=10_000)
    assert smart_page.locator("h1").contains_text("Logged In Successfully")
