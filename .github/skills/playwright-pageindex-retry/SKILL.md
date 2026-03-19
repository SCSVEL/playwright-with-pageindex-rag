---
name: playwright-pageindex-retry
description: '**WORKFLOW SKILL** — Detailed plan for building a Playwright locator retry strategy using PageIndex RAG approach by analyzing dynamic page HTML structure. 
USE FOR: planning and implementing resilient locator strategies for dynamic web pages with AI-powered retry mechanisms. DO NOT USE FOR: general Playwright coding; actual implementation without user approval.'
---

# Playwright PageIndex Retry Strategy Skill

## Overview
This skill encapsulates the detailed plan and approach for building a Playwright locator retry strategy that leverages the page's HTML tree (DOM structure) and integrates a Retrieval-Augmented Generation (RAG) system via a "PageIndex" mechanism. The goal is to make locators more resilient to dynamic web pages by dynamically analyzing the HTML tree and suggesting or retrying alternative locators based on semantic similarity and structural context.

## Basic Instructions to Follow
- Always follow the step-by-step implementation plan outlined in this skill.
- Ensure the tests for each step are run and validated before moving to the next step.

## Key Assumptions and Scope
- **Dynamic Pages**: Focus on pages where elements change (e.g., via JavaScript, user interactions, or AJAX), making static locators brittle.
- **Retry Logic**: Integrate with Playwright's built-in retry mechanisms but extend with AI-powered suggestions.
- **Non-Intrusive**: Strategy should not slow down tests significantly; aim for sub-second analysis per retry.
- **Fallbacks**: Always use SmartLocator fallback only when the original locator fails.
- **Ethical/Practical**: Ensure no sensitive data is logged; focus on structural analysis only.
- **Out of Scope**: Full AI-driven test generation; this is locator-specific.

## High-Level Architecture
1. **HTML Capture Module**: Extract the page's HTML tree (DOM) at runtime using Playwright's Python API.
2. **Indexing Module (PageIndex)**: Process the HTML into chunks, generate embeddings, and store in a vector database for fast retrieval.
3. **Query and Retrieval Module**: When a primary locator fails, query the index with the failed locator's context to retrieve similar elements.
4. **Locator Generation Module**: Use retrieved results to generate alternative locators using Playwright's built-in methods (getByRole, getByText, getByPlaceholder, getByLabel, etc.) before falling back to XPath/CSS.
5. **Retry Integration**: Hook into Playwright's locator API to attempt retries automatically **only when the original locator fails**.
6. **Custom Selector Registration**: Register a `smartlabels` selector engine via Playwright selectors API and expose a Playwright-like helper method `page.smartlocator(texts=[...])` through the SmartPage wrapper.
7. **Feedback Loop**: Optionally, learn from successful retries to improve future indexing.

## Step-by-Step Implementation Plan
1. **Set Up HTML Capture**:
   - Use Playwright's `page.content()` or `page.evaluate()` to get the full HTML string.
   - Parse into a tree structure (e.g., using a DOM parser) to extract elements, attributes, text, and hierarchy.
   - Capture at key points: Before each locator attempt, or on failure.
   - Store as a "snapshot" with metadata (e.g., URL, timestamp) for versioning.

2. **Build the PageIndex (RAG Indexing)**:
   - **Chunking**: Break the HTML into meaningful units (e.g., individual elements, subtrees based on tags like `<div>`, `<button>`). Include context like parent/child relationships, attributes (id, class, data-*), and visible text.
   - **Embedding Generation**: Convert chunks into vector embeddings for semantic search. Use text from elements plus structural hints.
   - **Storage**: Use a vector database (e.g., in-memory for simplicity, or persistent like ChromaDB) to index embeddings with metadata (e.g., XPath, CSS selector for each chunk).
   - **Update Mechanism**: Re-index on page changes (e.g., detect via mutation observers or periodic snapshots).

3. **Implement Query and Retrieval**:
   - On locator failure (e.g., `LocatorError`), extract context from the failed attempt (e.g., intended element description, partial selector).
   - Query the PageIndex: Perform similarity search on embeddings (e.g., "find elements similar to a button with text 'Submit' near a form").
   - Retrieve top-k matches (e.g., 3-5) with scores, including alternative paths/selectors.

4. **Generate Alternative Locators**:
   - From retrieved chunks, prioritize Playwright's semantic locators:
     - **getByRole**: Most resilient; query by accessibility role (e.g., `locator.get_by_role("button", name="Submit")`).
     - **getByText**: For text-based matching (e.g., `locator.get_by_text("Submit")`).
     - **getByPlaceholder**: For input fields (e.g., `locator.get_by_placeholder("Enter name")`).
     - **getByLabel**: For labeled form fields (e.g., `locator.get_by_label("Email")`).
     - **Fallback to XPath/CSS**: Only if semantic methods don't match (e.g., `locator.locator("xpath=//div[@class='form']//button")`). 
   - Validate generated locators quickly using Playwright's `locator.count()` to test if they match elements.
   - Return locator with highest confidence score first.

5. **Integrate Retry Strategy**:
   - Create a custom `SmartLocator` wrapper class that wraps Playwright's `Locator`.
   - **Default behavior**: Attempt locator operation (click, fill, etc.) using the original locator.
   - **On failure only**: Trigger RAG query → generate alternative locators → retry in sequence (e.g., try 2-3 alternatives before giving up).
   - Add timeouts and limits to prevent infinite retries (e.g., max 3 attempts, 5-second total timeout).
   - If all alternatives fail, raise original locator error with context about attempted alternatives.

6. **Testing and Validation**:
   - Unit tests using pytest (e.g., HTML parsing, embedding accuracy, locator generation logic).
   - Integration tests: Run on sample dynamic pages (e.g., React apps with changing DOM) using Playwright's test fixtures.
   - Measure success rate: % of retries that succeed vs. standard Playwright.
   - Performance: Ensure indexing/querying <500ms.
   - Test both success cases (SmartLocator finds element) and failure cases (all alternatives exhausted).

7. **Integration and Edge Cases**:
   - Integrate as a core module within the test framework (do not package as external plugin yet).
   - Handle edge cases: Shadow DOM, iframes, large pages (chunk wisely).
   - Update embeddings/models periodically for better accuracy.

## Recommended Libraries for Effective Analysis (Python Stack)
- **HTML/DOM Parsing and Manipulation**:
  - **BeautifulSoup4** or **lxml**: Lightweight DOM parsers for Python.
  - **Playwright's `page.content()` and `page.evaluate()`**: Built-in for direct DOM access.

- **RAG and Indexing (Core for PageIndex)**:
  - **LangChain** (Python): Frameworks for building RAG pipelines.
  - **LlamaIndex** (Python): Alternative for document/structure indexing.
  - **Vector Databases**: **Chroma** (local/serverless) or **Pinecone** (cloud).

- **Embeddings**:
  - **OpenAI Embeddings API**: High-quality semantic understanding via API.
  - **Sentence Transformers** (Hugging Face): Open-source alternative, runs locally (e.g., `all-MiniLM-L6-v2`).

- **Locator Generation/Synthesis**:
  - Playwright's native methods: `get_by_role()`, `get_by_text()`, `get_by_placeholder()`, `get_by_label()`.
  - Custom XPath/CSS generation using string templating and validation.

- **Integration and Utilities**:
  - **Playwright Python**: Core testing framework with async support.
  - **pytest**: Testing framework and fixtures.
  - **pytest-asyncio**: Async test support.
  - **dataclasses** or **pydantic**: For structured configuration and element metadata.

## Potential Challenges and Mitigations
- **Performance**: Embedding large HTML trees can be slow; mitigate by chunking and caching.
- **Accuracy**: Embeddings might miss structural nuances; combine with rule-based heuristics.
- **Dynamic Content**: Capture HTML post-load or use mutation observers.
- **Security/Privacy**: Sanitize HTML before processing.
- **Scalability**: Use distributed vector stores or pre-compute indexes.

## Benefits
- **Resilience**: Reduces flaky tests by adapting to DOM changes.
- **Efficiency**: Faster debugging; less manual locator tweaking.
- **AI Leverage**: RAG provides semantic understanding beyond regex matching.
- **Extensibility**: Can evolve to full test generation or visual locators.

## Custom Selector Registration
Use the implemented selector registration + SmartPage wrapper so tests remain Playwright-command only.

### Expected Usage Model
- **Normal path**: `page.locator("...").click()` or `fill()` first tries native Playwright.
- **Fallback path (internal)**: If a native locator fails, internal SmartLocator fallback is triggered automatically.
- **Explicit path**: `page.smartlocator(texts=["text1", "text2"])` resolves via the `smartlabels` selector engine.

### Registration and Usage
```python
from playwright.async_api import async_playwright
from src.core import register_smartlabels_selector, SmartPage, SmartEngine

async with async_playwright() as p:
   # Register custom selector engine once per Playwright instance.
   await register_smartlabels_selector(p)

   browser = await p.chromium.launch()
   raw_page = await browser.new_page()

   # Wrap Playwright page to enable internal fallback + explicit smartlocator API.
   page = SmartPage(raw_page, SmartEngine(persist_directory="./.pageindex-runtime"))

   await page.goto("https://practice.expandtesting.com/register")

   # Explicit smart locator usage.
   await page.smartlocator(texts=["Username", "User Name"]).fill("autouser-123")

   # Normal locator usage with automatic internal fallback on failure.
   await page.locator("#register-submit-does-not-exist").click()
```

### Practical Expectations
- Your test body should contain only Playwright-style commands.
- Smart fallback internals (HTML capture, index build, retrieval, retry) should stay outside the test body in framework helpers/fixtures.

## Implementation Steps
Implement one step at a time. After each step, investigate the output, validate it, and provide feedback before proceeding to the next step:
1. HTML Capture Module
2. PageIndex (RAG Indexing)
3. Query and Retrieval
4. Locator Generation (semantic methods priority)
5. SmartLocator Wrapper (failure-only retry)
6. Custom Selector Registration
7. Pytest Tests