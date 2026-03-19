"""Debug script to reproduce PageIndex.build_index failure and inspect metadata entries."""

import asyncio
import sys
from pathlib import Path

# Ensure project root is on sys.path so `src` package can be imported.
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from playwright.async_api import async_playwright

from src.core import HTMLCapture, PageIndex, PageIndexConfig
from chromadb.utils import embedding_functions
import chromadb

SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <h1>Login Form</h1>
    <form id=\"login-form\">
        <input type=\"text\" id=\"username\" name=\"username\" placeholder=\"Enter username\" />
        <input type=\"password\" id=\"password\" name=\"password\" placeholder=\"Enter password\" />
        <button type=\"submit\" id=\"submit-btn\">Login</button>
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

        idx = PageIndex(config=PageIndexConfig(persist_directory=str(Path('tmp_index'))))

        try:
            idx.build_index(snapshot)
            print('Build index succeeded')
        except Exception as err:
            print('Build index failed:', err)
            print('---')
            print('Attempting to build full metadata list and see which causes failure...')
            for i, element in enumerate(snapshot.elements):
                entry = idx._create_index_entry(snapshot, element)
                # Try to build the list and add incrementally
                try:
                    # Create a fresh client and collection for testing
                    from chromadb.config import Settings
                    test_client = chromadb.Client(Settings(persist_directory=str(Path('tmp_test_index')), is_persistent=True))
                    test_ef = embedding_functions.SentenceTransformerEmbeddingFunction(
                        model_name=idx.config.embedding_model_name
                    )
                    test_col =test_client.get_or_create_collection(
                        name='test_single',
                        embedding_function=test_ef,
                        get_or_create=True
                    )
                    # Try to add this single entry
                    from chromadb.utils import embedding_functions
                    text_embedding = test_ef([entry.text])[0]
                    print(f'Element {i}: {entry.id}')
                    print(f'  Metadata: {entry.metadata}')
                    test_col.add(ids=[entry.id], documents=[entry.text], metadatas=[entry.metadata])
                except Exception as err2:
                    print(f'Failed at element {i}')
                    print(f'  ID: {entry.id}')
                    print(f'  Text: {entry.text}')
                    print(f'  Metadata: {entry.metadata}')
                    print(f'  Error: {err2}')
                    break
            raise

        await browser.close()


if __name__ == '__main__':
    asyncio.run(main())
