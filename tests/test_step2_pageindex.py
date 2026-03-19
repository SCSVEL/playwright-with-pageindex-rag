"""Tests for Step 2: PageIndex (RAG Indexing)."""

import os
import tempfile

import pytest
from playwright.async_api import async_playwright

from src.core import HTMLCapture, PageIndex, PageIndexConfig


SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
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
async def test_pageindex_basic_query(tmp_path):
    """Index an HTML snapshot and query for a known element."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(SAMPLE_HTML)

        capture = HTMLCapture()
        snapshot = await capture.capture_page(page, metadata={"test": "pageindex_basic_query"})

        # Build index using temporary persist directory
        index_dir = tmp_path / "index"
        page_index = PageIndex(config=PageIndexConfig(persist_directory=str(index_dir)))
        page_index.build_index(snapshot)

        # Query for the login button and expect to get a relevant result
        results = page_index.query("Login")
        assert len(results) > 0

        # Ensure we can find an element whose accessible name is "Login"
        found_login = any(r["metadata"].get("accessible_name") == "Login" for r in results)
        assert found_login, f"Expected to find 'Login' in metadata results, got: {results}"

        # Export index and verify file exists
        export_path = tmp_path / "index_export.json"
        page_index.export_index(str(export_path))
        assert export_path.exists(), "Index export file should exist"

        await browser.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])