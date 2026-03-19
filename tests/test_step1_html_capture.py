"""
Test for Step 1: HTML Capture Module

This test demonstrates basic HTML capture functionality:
- Capture page HTML
- Parse into element tree
- Extract metadata (URL, timestamp, attributes)
- Export snapshot to JSON and HTML files
"""

import pytest
import tempfile
import os
from pathlib import Path
from playwright.async_api import async_playwright
from src.core import HTMLCapture


# Simple HTML for testing
SAMPLE_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Test Page</title>
</head>
<body>
    <h1>Login Form</h1>
    <form id="login-form">
        <input 
            type="text" 
            id="username" 
            name="username" 
            placeholder="Enter username"
            data-testid="username-input"
        />
        <input 
            type="password" 
            id="password" 
            name="password" 
            placeholder="Enter password"
            aria-label="Password field"
        />
        <button type="submit" id="submit-btn" class="btn btn-primary">
            Login
        </button>
        <button type="reset" class="btn btn-secondary">
            Clear
        </button>
    </form>
    <footer>
        <p>© 2024 Test App</p>
    </footer>
</body>
</html>
"""


@pytest.mark.asyncio
async def test_html_capture_basic():
    """Test basic HTML capture functionality."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        # Set content
        await page.set_content(SAMPLE_HTML)
        
        # Capture HTML
        capture = HTMLCapture()
        snapshot = await capture.capture_page(page, metadata={"test_name": "test_html_capture_basic"})
        
        # Verify snapshot
        assert snapshot.url == "about:blank"
        assert snapshot.html_content is not None
        assert len(snapshot.elements) > 0
        assert snapshot.metadata["test_name"] == "test_html_capture_basic"
        
        print(f"\n✓ Captured {len(snapshot.elements)} elements from page")
        print(f"✓ Snapshot timestamp: {snapshot.timestamp}")
        
        await browser.close()


@pytest.mark.asyncio
async def test_element_parsing():
    """Test that elements are parsed with correct attributes."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.set_content(SAMPLE_HTML)
        
        capture = HTMLCapture()
        snapshot = await capture.capture_page(page)
        
        # Find input element with data-testid="username-input"
        input_elements = [el for el in snapshot.elements if el.tag == "input"]
        assert len(input_elements) > 0, "No input elements found"
        
        # Find username input by checking xpath
        username_input = None
        for el in input_elements:
            if "data-testid" in el.attrs and el.attrs.get("data-testid") == "username-input":
                username_input = el
                break
        
        assert username_input is not None, "Username input not found"
        assert username_input.attrs.get("placeholder") == "Enter username"
        assert username_input.accessible_name == "Enter username"
        
        print(f"\n✓ Found username input element")
        print(f"  Tag: {username_input.tag}")
        print(f"  Attrs: {username_input.attrs}")
        print(f"  XPath: {username_input.xpath}")
        print(f"  Accessible Name: {username_input.accessible_name}")
        
        await browser.close()


@pytest.mark.asyncio
async def test_button_accessible_names():
    """Test that button accessible names are extracted."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.set_content(SAMPLE_HTML)
        
        capture = HTMLCapture()
        snapshot = await capture.capture_page(page)
        
        # Find buttons
        button_elements = [el for el in snapshot.elements if el.tag == "button"]
        assert len(button_elements) == 2, "Expected 2 buttons"
        
        # Check submit button
        submit_btn = next((el for el in button_elements if "Login" in el.text), None)
        assert submit_btn is not None
        assert submit_btn.accessible_name == "Login"
        assert "btn" in submit_btn.attrs.get("class", [])
        
        print(f"\n✓ Found {len(button_elements)} buttons in form")
        for btn in button_elements:
            print(f"  - Button: {btn.accessible_name} (classes: {btn.attrs.get('class')})")
        
        await browser.close()


@pytest.mark.asyncio
async def test_snapshot_export():
    """Test snapshot export to JSON and HTML files."""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        await page.set_content(SAMPLE_HTML)
        
        capture = HTMLCapture()
        snapshot = await capture.capture_page(page)
        
        # Create temporary directory
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "snapshot.json")
            html_path = os.path.join(tmpdir, "snapshot.html")
            
            # Export
            capture.export_snapshot_json(snapshot, json_path)
            capture.export_html_content(snapshot, html_path)
            
            # Verify files exist
            assert os.path.exists(json_path), "JSON export failed"
            assert os.path.exists(html_path), "HTML export failed"
            
            # Verify JSON content
            import json
            with open(json_path, "r") as f:
                exported = json.load(f)
                assert exported["elements_count"] == len(snapshot.elements)
                assert exported["url"] == snapshot.url
            
            # Verify HTML content
            with open(html_path, "r", encoding="utf-8") as f:
                html_content = f.read()
                assert html_content == snapshot.html_content

            print(f"\n✓ Exported snapshot to JSON: {json_path}")
            print(f"✓ Exported snapshot to HTML: {html_path}")
            print(f"✓ JSON contains {exported['elements_count']} elements")
        
        await browser.close()


if __name__ == "__main__":
    # Run tests with: pytest tests/test_step1_html_capture.py -v -s
    pytest.main([__file__, "-v", "-s"])
