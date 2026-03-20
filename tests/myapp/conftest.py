"""Fixtures for myapp tests with SmartPage support."""

import base64
from datetime import datetime
from html import escape
from pathlib import Path

import pytest
import pytest_asyncio
from playwright.async_api import async_playwright

from src.core import (
    SmartEngine,
    SmartLocatorConfig,
    SmartPage,
    register_smartlabels_selector,
)


RESULTS_DIR = Path("playwright-results") / "screenshots"
RAG_SOURCE_HINTS = (
    "src/core/",
    "smart_page_runtime",
    "page_index",
    "query_retrieval",
    "locator_generation",
    "smart_locator",
    "chromadb",
    "langchain",
)
RAG_LOG_ENTRIES = []


def _safe_nodeid(nodeid: str) -> str:
    return "".join(ch if ch.isalnum() or ch in ("-", "_") else "_" for ch in nodeid)


def _build_modal_extra(encoded_image: str, modal_id: str) -> str:
    image_src = f"data:image/png;base64,{encoded_image}"
    return f"""
<style>
    .sp-modal-toggle {{
        display: none;
    }}
    .sp-thumb-trigger img {{
        width: 120px;
        max-height: 80px;
        object-fit: cover;
        max-width: 100%;
        border: 1px solid #d0d7de;
        border-radius: 6px;
        cursor: zoom-in;
    }}
    .sp-modal {{
        display: none;
        position: fixed;
        inset: 0;
        z-index: 9999;
    }}
    .sp-modal-overlay {{
        position: absolute;
        inset: 0;
        background: rgba(0, 0, 0, 0.82);
    }}
    .sp-modal-content {{
        position: relative;
        display: flex;
        align-items: center;
        justify-content: center;
        height: 100%;
        padding: 24px;
        box-sizing: border-box;
        z-index: 1;
    }}
    .sp-modal-content img {{
        max-width: min(96vw, 1800px);
        max-height: 90vh;
        border-radius: 8px;
        box-shadow: 0 12px 36px rgba(0, 0, 0, 0.45);
    }}
    .sp-modal-close {{
        position: absolute;
        top: 14px;
        right: 18px;
        font-size: 26px;
        font-weight: 700;
        color: #fff;
        cursor: pointer;
        line-height: 1;
    }}
    .sp-modal-toggle:checked + .sp-thumb-trigger + .sp-modal {{
        display: block;
    }}
</style>
<div>
    <input id="{modal_id}" class="sp-modal-toggle" type="checkbox" />
    <label for="{modal_id}" class="sp-thumb-trigger" title="Click to expand">
        <img src="{image_src}" alt="Failure screenshot" />
    </label>
    <div class="sp-modal">
        <label for="{modal_id}" class="sp-modal-overlay" aria-label="Close modal"></label>
        <div class="sp-modal-content">
            <label for="{modal_id}" class="sp-modal-close" aria-label="Close">×</label>
            <img src="{image_src}" alt="Failure screenshot full view" />
        </div>
    </div>
</div>
"""


def _is_rag_section(section_title: str, section_text: str) -> bool:
    title = section_title.lower()
    if not ("captured stdout" in title or "captured stderr" in title or "captured log" in title):
        return False

    body = section_text.lower()
    return any(hint in body for hint in RAG_SOURCE_HINTS)


def pytest_configure(config):
    del config
    RAG_LOG_ENTRIES.clear()


def pytest_html_results_table_header(cells):
    cells.insert(-1, "<th>Screenshot</th>")


def pytest_html_results_table_row(report, cells):
    screenshot_html = getattr(report, "screenshot_modal_html", "")
    cells.insert(-1, f"<td>{screenshot_html}</td>")


def pytest_runtest_logreport(report):
    if not getattr(report, "sections", None):
        return

    kept_sections = []
    rag_sections = []

    for section_title, section_text in report.sections:
        if _is_rag_section(section_title, section_text):
            rag_sections.append((section_title, section_text))
        else:
            kept_sections.append((section_title, section_text))

    if rag_sections:
        RAG_LOG_ENTRIES.append((report.nodeid, rag_sections))

    report.sections = kept_sections


def pytest_html_results_summary(prefix, summary, postfix):
    del prefix
    del summary
    if not RAG_LOG_ENTRIES:
        return

    blocks = []
    for nodeid, sections in RAG_LOG_ENTRIES:
        section_html = "".join(
            f"<h5>{escape(title)}</h5><pre style='white-space:pre-wrap'>{escape(text)}</pre>"
            for title, text in sections
        )
        blocks.append(f"<details><summary>{escape(nodeid)}</summary>{section_html}</details>")

    postfix.append(
        "<details><summary><strong>RAG log</strong></summary>"
        "<div style='max-height:420px;overflow:auto'>"
        f"{''.join(blocks)}"
        "</div></details>"
    )


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """Store phase reports and attach screenshot extras to the test call row."""
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)

    if rep.when != "teardown":
        return

    rep_call = getattr(item, "rep_call", None)
    screenshot_path = getattr(item, "_failure_screenshot_path", None)
    if not rep_call or not screenshot_path:
        return

    pytest_html = item.config.pluginmanager.getplugin("html")
    if not pytest_html:
        return

    extras = getattr(rep_call, "extras", [])
    image_bytes = Path(screenshot_path).read_bytes()
    encoded_image = base64.b64encode(image_bytes).decode("ascii")
    modal_id = f"modal_{_safe_nodeid(item.nodeid)}"
    rep_call.screenshot_modal_html = _build_modal_extra(encoded_image, modal_id)
    extras.append(pytest_html.extras.png(encoded_image, name="Screenshot (raw)"))
    rep_call.extras = extras


@pytest_asyncio.fixture
async def smart_page(tmp_path, request):
    async with async_playwright() as p:
        await register_smartlabels_selector(p)

        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        engine = SmartEngine(
            persist_directory=str(tmp_path / "smart_runtime_index"),
            smart_config=SmartLocatorConfig(max_alternative_attempts=4, action_timeout_ms=1500),
        )

        request.node._playwright_page = page
        yield SmartPage(page, engine)

        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
        screenshot_name = f"{_safe_nodeid(request.node.nodeid)}_{timestamp}.png"
        screenshot_path = RESULTS_DIR / screenshot_name

        try:
            await page.screenshot(path=str(screenshot_path), full_page=True)
            request.node._failure_screenshot_path = screenshot_path
        except Exception:
            # Best-effort screenshot capture should never fail the test run.
            request.node._failure_screenshot_path = None

        await browser.close()
