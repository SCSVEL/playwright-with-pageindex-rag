"""Tests for Step 3: Query and Retrieval."""

import pytest
from playwright.async_api import async_playwright

from src.core import (
    HTMLCapture,
    PageIndex,
    PageIndexConfig,
    QueryRetriever,
    FailedLocatorContext,
)


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Sample Login</title>
</head>
<body>
    <h1>Login Form</h1>
    <form id="login-form">
        <input type="text" id="username" name="username" placeholder="Enter username" />
        <input type="password" id="password" name="password" placeholder="Enter password" />
        <button type="submit" id="submit-btn">Login</button>
    </form>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_query_candidates_are_built_from_failed_context(tmp_path):
    """Ensure query candidates include locator + semantic hints from context."""
    index_dir = tmp_path / "index"
    page_index = PageIndex(config=PageIndexConfig(persist_directory=str(index_dir)))
    retriever = QueryRetriever(page_index)

    context = FailedLocatorContext(
        original_locator="button[name='signin']",
        role="button",
        text="Login",
        label="Login",
        attributes={"id": "submit-btn", "data-testid": "login-cta"},
    )

    candidates = retriever.build_query_candidates(context)

    assert "button[name='signin']" in candidates
    assert "Login" in candidates
    assert "button Login" in candidates
    assert "id:submit-btn" in candidates
    assert "data-testid:login-cta" in candidates


@pytest.mark.asyncio
async def test_retrieve_returns_ranked_results_for_failed_locator_context(tmp_path):
    """Index snapshot, then retrieve likely matches from failed locator context."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(SAMPLE_HTML)

        capture = HTMLCapture()
        snapshot = await capture.capture_page(page, metadata={"test": "step3_retrieve"})

        index_dir = tmp_path / "index"
        page_index = PageIndex(config=PageIndexConfig(persist_directory=str(index_dir)))
        page_index.build_index(snapshot)

        retriever = QueryRetriever(page_index)
        context = FailedLocatorContext(
            original_locator="button[name='signin']",
            action="click",
            role="button",
            text="Login",
        )

        results = retriever.retrieve(context, top_k=5, per_query_top_k=3)

        assert len(results) > 0
        assert any(r.accessible_name == "Login" for r in results)

        # Scores should be descending.
        scores = [r.score for r in results]
        assert scores == sorted(scores, reverse=True)

        await browser.close()
