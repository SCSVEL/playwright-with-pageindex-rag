"""Debug script to identify invalid metadata values for Chroma.

Run with:
    python scripts/debug_validate_metadata.py
"""

import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path for local `src` imports
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright
from src.core import HTMLCapture, PageIndex, PageIndexConfig
from chromadb.api.types import validate_metadata

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

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.set_content(SAMPLE_HTML)

        capture = HTMLCapture()
        snapshot = await capture.capture_page(page)

        idx = PageIndex(config=PageIndexConfig(persist_directory="./tmp_index"))

        for i, element in enumerate(snapshot.elements):
            entry = idx._create_index_entry(snapshot, element)
            try:
                validate_metadata(entry.metadata)
            except Exception as e:
                print("Invalid metadata at element", i)
                print("metadata:", entry.metadata)
                print("error:", e)
                break
        else:
            print("All metadata valid")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
