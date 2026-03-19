# Playwright PageIndex Retry Strategy

## Project Structure

```
playwright-with-pageindex/
├── src/
│   ├── __init__.py
│   └── core/
│       ├── __init__.py
│       └── html_capture.py           # Step 1: HTML Capture Module
├── tests/
│   └── test_step1_html_capture.py   # Tests for Step 1
├── .github/
│   └── skills/
│       └── playwright-pageindex-retry/
│           └── SKILL.md              # Project plan and architecture
├── requirements.txt
└── README.md
```

## Setup

Detailed design and implementation approach live in [`.github/skills/playwright-pageindex-retry/SKILL.md`](.github/skills/playwright-pageindex-retry/SKILL.md).

```bash
pip install -r requirements.txt
playwright install
```

## Real Usage In Playwright Tests

The intended usage is:

- test files contain only Playwright-style commands
- internal SmartLocator fallback is triggered automatically when a normal locator fails
- explicit fallback usage is available through `page.smartlocator(texts=[...])`

### Fixture Setup

Create a fixture that registers the custom selector and wraps the Playwright page with `SmartPage`.

`tmp_path` is a built-in pytest fixture that provides a fresh temporary directory for each test run; it is used here to store the runtime PageIndex files safely per test.

```python
import pytest_asyncio
from playwright.async_api import async_playwright

from src.core import (
    SmartEngine,
    SmartLocatorConfig,
    SmartPage,
    register_smartlabels_selector,
)


@pytest_asyncio.fixture
async def smart_page(tmp_path):
    async with async_playwright() as p:
        await register_smartlabels_selector(p)

        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        engine = SmartEngine(
            persist_directory=str(tmp_path / "smart_runtime_index"),
            smart_config=SmartLocatorConfig(max_alternative_attempts=4, action_timeout_ms=1500),
        )

        yield SmartPage(page, engine)

        await browser.close()
```

### Example Test

```python
import time
import pytest


@pytest.mark.asyncio
async def test_register_with_internal_fallback_and_explicit_smartlocator(smart_page):
    username = f"autouser-{int(time.time())}"
    password = "P@ssw0rd123!"

    await smart_page.goto("https://practice.expandtesting.com/register", wait_until="domcontentloaded")

    # Explicit SmartLocator usage
    await smart_page.smartlocator(texts=["Username"]).fill(username)

    # Normal Playwright-style commands
    await smart_page.locator("#password").fill(password)
    await smart_page.locator("#confirmPassword").fill(password)

    # Intentionally bad locator; fallback happens internally
    await smart_page.locator("#register-submit-does-not-exist").click()

    await smart_page.wait_for_url("**/login", wait_until="domcontentloaded", timeout=10000)
    body_text = await smart_page.locator("body").inner_text()

    assert smart_page.url.endswith("/login")
    assert "Successfully registered, you can log in now." in body_text
```

## Run MyApp Tests

```bash
pip install -r requirements.txt
playwright install
pytest -q tests/myapp -v
```
