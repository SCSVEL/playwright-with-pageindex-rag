"""SmartPage wrapper for Playwright-style usage with internal SmartLocator fallback.

- Normal `locator(...).click()/fill()` tries Playwright first and falls back internally.
- Explicit `smartlocator(texts=[...])` is exposed as a Playwright-like command.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Optional

from playwright.async_api import Locator, Page

from .custom_selector import build_smartlabels_locator_value
from .html_capture import HTMLCapture
from .locator_generation import LocatorGenerator
from .page_index import PageIndex, PageIndexConfig
from .query_retrieval import QueryRetriever
from .smart_locator import SmartLocator, SmartLocatorConfig


class SmartEngine:
    """Builds runtime retrieval context used by SmartLocator fallback."""

    def __init__(
        self,
        persist_directory: str,
        smart_config: Optional[SmartLocatorConfig] = None,
    ) -> None:
        self.persist_directory = persist_directory
        self.smart_config = smart_config or SmartLocatorConfig()

    async def build_smart_locator(self, page: Page, original_locator: str) -> SmartLocator:
        capture = HTMLCapture()
        snapshot = await capture.capture_page(page, metadata={"source": "smart_page_runtime"})

        Path(self.persist_directory).mkdir(parents=True, exist_ok=True)
        index = PageIndex(
            config=PageIndexConfig(
                persist_directory=self.persist_directory,
                collection_name="runtime_page_index",
            )
        )
        index.build_index(snapshot, overwrite=True)

        retriever = QueryRetriever(index)
        return SmartLocator(
            page=page,
            original_locator=original_locator,
            query_retriever=retriever,
            locator_generator=LocatorGenerator(),
            config=self.smart_config,
        )


class SmartFallbackLocator:
    """Locator proxy that adds SmartLocator fallback for click/fill."""

    def __init__(self, page: Page, base_locator: Locator, selector: str, engine: SmartEngine):
        self._page = page
        self._base = base_locator
        self._selector = selector
        self._engine = engine

    async def click(self, *args: Any, **kwargs: Any) -> None:
        if "timeout" not in kwargs:
            kwargs["timeout"] = self._engine.smart_config.action_timeout_ms

        try:
            await self._base.click(*args, **kwargs)
            return
        except Exception:
            smart = await self._engine.build_smart_locator(self._page, self._selector)
            hint = self._selector_hint()
            await smart.click(text=hint or None, label=hint or None, placeholder=hint or None, role="button")

    async def fill(self, value: str, *args: Any, **kwargs: Any) -> None:
        if "timeout" not in kwargs:
            kwargs["timeout"] = self._engine.smart_config.action_timeout_ms

        try:
            await self._base.fill(value, *args, **kwargs)
            return
        except Exception:
            smart = await self._engine.build_smart_locator(self._page, self._selector)
            hint = self._selector_hint()
            await smart.fill(value, text=hint or None, label=hint or None, placeholder=hint or None)

    def _selector_hint(self) -> str:
        hint = self._selector
        for token in ["#", ".", "[", "]", "=", "\"", "'", ":", "-", "_"]:
            hint = hint.replace(token, " ")

        words = [w.lower() for w in hint.split() if w.strip()]
        if not words:
            return ""

        # Prefer high-signal action words for clickable elements.
        preferred = ["register", "submit", "save", "login", "continue", "next"]
        for p in preferred:
            if p in words:
                return p.capitalize()

        # Remove noisy tokens commonly present in intentionally broken selectors.
        ignore = {"does", "not", "exist", "missing", "invalid", "locator"}
        filtered = [w for w in words if w not in ignore]
        if filtered:
            return " ".join(filtered[:2]).capitalize()

        return " ".join(words[:2]).capitalize()

    def __getattr__(self, name: str) -> Any:
        # Delegate all other methods/properties to underlying Playwright locator.
        return getattr(self._base, name)


class SmartPage:
    """Playwright-like page wrapper exposing internal fallback + explicit smartlocator."""

    def __init__(self, page: Page, engine: SmartEngine):
        self._page = page
        self._engine = engine

    def locator(self, selector: str, *args: Any, **kwargs: Any) -> SmartFallbackLocator:
        base = self._page.locator(selector, *args, **kwargs)
        return SmartFallbackLocator(self._page, base, selector, self._engine)

    def smartlocator(self, texts: Iterable[str], selector_name: str = "smartlabels") -> Locator:
        value = build_smartlabels_locator_value(texts)
        return self._page.locator(f"{selector_name}={value}")

    def __getattr__(self, name: str) -> Any:
        # Delegate regular Page API (goto, wait_for_url, get_by_role, etc.)
        return getattr(self._page, name)
