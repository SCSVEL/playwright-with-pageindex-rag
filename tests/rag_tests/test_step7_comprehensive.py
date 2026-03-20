"""Step 7: Comprehensive end-to-end tests.

These tests validate the full chain:
HTML capture -> indexing -> retrieval -> semantic locator generation -> failure-only smart retry.
"""

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
    FailedLocatorContext,
)


HTML_PAGE = """
<!DOCTYPE html>
<html>
<body>
  <main>
    <h1>Registration</h1>
    <form id="reg-form">
      <label for="first-name">First Name</label>
      <input id="first-name" name="firstName" placeholder="FirstName" />

      <label for="email">Email</label>
      <input id="email" name="email" placeholder="Enter Email" />

      <button type="button" id="save-btn">Save</button>
    </form>
  </main>
  <script>
    window.saved = false;
    document.getElementById('save-btn').addEventListener('click', () => {
      window.saved = true;
    });
  </script>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_full_pipeline_retrieval_and_generation_for_failed_locator(tmp_path):
    """Validate retrieval + semantic generation from failed locator context."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML_PAGE)

        capture = HTMLCapture()
        snapshot = await capture.capture_page(page, metadata={"test": "step7_pipeline"})

        index = PageIndex(config=PageIndexConfig(persist_directory=str(tmp_path / "index")))
        index.build_index(snapshot)

        retriever = QueryRetriever(index)
        context = FailedLocatorContext(
            original_locator="#missing-first-name",
            action="fill",
            label="First Name",
            placeholder="FirstName",
        )

        retrieved = retriever.retrieve(context, top_k=5, per_query_top_k=3)
        assert len(retrieved) > 0
        assert any(r.attrs.get("name") == "firstName" for r in retrieved)

        generator = LocatorGenerator()
        candidates = generator.generate(context, retrieved, top_k=8)

        assert len(candidates) > 0
        # semantic-first expectation
        semantic_prefix = [c.strategy for c in candidates[:4]]
        assert any(s in semantic_prefix for s in ["get_by_label", "get_by_placeholder", "get_by_role", "get_by_text"])

        await browser.close()


@pytest.mark.asyncio
async def test_full_pipeline_smartlocator_fill_and_click_with_primary_failures(tmp_path):
    """Validate SmartLocator fallback for both fill and click operations."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(HTML_PAGE)

        capture = HTMLCapture()
        snapshot = await capture.capture_page(page, metadata={"test": "step7_smartlocator"})

        index = PageIndex(config=PageIndexConfig(persist_directory=str(tmp_path / "index2")))
        index.build_index(snapshot)

        retriever = QueryRetriever(index)
        generator = LocatorGenerator()

        # Fill fallback
        smart_fill = SmartLocator(
            page=page,
            original_locator="#missing-input",
            query_retriever=retriever,
            locator_generator=generator,
            config=SmartLocatorConfig(max_alternative_attempts=4, action_timeout_ms=1000),
        )
        await smart_fill.fill(
          "Alice",
          label="First Name",
          placeholder="FirstName",
          role="textbox",
        )

        value = await page.locator("#first-name").input_value()
        assert value == "Alice"

        # Click fallback
        smart_click = SmartLocator(
            page=page,
            original_locator="#missing-button",
            query_retriever=retriever,
            locator_generator=generator,
            config=SmartLocatorConfig(max_alternative_attempts=4, action_timeout_ms=1000),
        )
        await smart_click.click(text="Save", role="button")

        saved = await page.evaluate("() => window.saved")
        assert saved is True

        await browser.close()
