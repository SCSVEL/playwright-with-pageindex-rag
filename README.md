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

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install
```

## Step 1: HTML Capture Module

The HTML Capture Module extracts and parses the page's HTML tree at runtime.

### Features
- **Capture**: Extracts full HTML from Playwright page using `page.content()`
- **Parse**: Converts HTML to structured element tree using BeautifulSoup
- **Extract**: Pulls element metadata (tag, attributes, text, XPath, accessible name)
- **Snapshot**: Creates versioned snapshots with URL, timestamp, and metadata
- **Export**: Supports JSON and HTML file exports for debugging

### Running Tests

```bash
# Run all Step 1 tests
pytest tests/test_step1_html_capture.py -v -s

# Run specific test
pytest tests/test_step1_html_capture.py::test_html_capture_basic -v -s

# Run with coverage
pytest tests/test_step1_html_capture.py --cov=src/core
```

### Basic Usage

```python
from src.core import HTMLCapture
from playwright.async_api import async_playwright

async with async_playwright() as p:
    browser = await p.chromium.launch()
    page = await browser.new_page()
    await page.goto("https://example.com")
    
    # Capture page HTML
    capture = HTMLCapture()
    snapshot = await capture.capture_page(page)
    
    # Access parsed elements
    for element in snapshot.elements:
        print(f"{element.tag} - {element.accessible_name}")
    
    # Export for debugging
    capture.export_snapshot_json(snapshot, "snapshot.json")
    
    await browser.close()
```

## Next Steps

After validating Step 1, we'll proceed to:
- Step 2: PageIndex (RAG Indexing)
- Step 3: Query and Retrieval
- Step 4: Locator Generation (semantic priority)
- Step 5: SmartLocator Wrapper (failure-only)
- Step 6: Custom Selector Registration
- Step 7: Pytest Tests (comprehensive)
