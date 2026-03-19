"""Step 5: SmartLocator wrapper (failure-only retry).

SmartLocator tries the original locator first. Alternative locator generation and
retry are only triggered when the original locator action fails.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from playwright.async_api import Locator, Page

from .locator_generation import LocatorCandidate, LocatorGenerator
from .query_retrieval import FailedLocatorContext, QueryRetriever


@dataclass
class SmartLocatorConfig:
    """Configuration for SmartLocator retry behavior."""

    max_alternative_attempts: int = 3
    action_timeout_ms: int = 3000


class SmartLocator:
    """Failure-only smart locator wrapper around Playwright locators."""

    def __init__(
        self,
        page: Page,
        original_locator: str,
        query_retriever: QueryRetriever,
        locator_generator: Optional[LocatorGenerator] = None,
        config: Optional[SmartLocatorConfig] = None,
    ) -> None:
        self.page = page
        self.original_locator = original_locator
        self.query_retriever = query_retriever
        self.locator_generator = locator_generator or LocatorGenerator()
        self.config = config or SmartLocatorConfig()

    async def click(
        self,
        *,
        text: Optional[str] = None,
        label: Optional[str] = None,
        placeholder: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Locator:
        """Click using original locator first, then alternatives only on failure."""
        primary = self.page.locator(self.original_locator)
        try:
            await primary.click(timeout=self.config.action_timeout_ms)
            return primary
        except Exception as original_error:
            return await self._retry_action(
                action="click",
                text=text,
                label=label,
                placeholder=placeholder,
                role=role,
                original_error=original_error,
            )

    async def fill(
        self,
        value: str,
        *,
        text: Optional[str] = None,
        label: Optional[str] = None,
        placeholder: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Locator:
        """Fill using original locator first, then alternatives only on failure."""
        primary = self.page.locator(self.original_locator)
        try:
            await primary.fill(value, timeout=self.config.action_timeout_ms)
            return primary
        except Exception as original_error:
            return await self._retry_action(
                action="fill",
                text=text,
                label=label,
                placeholder=placeholder,
                role=role,
                fill_value=value,
                original_error=original_error,
            )

    async def _retry_action(
        self,
        action: str,
        original_error: Exception,
        fill_value: Optional[str] = None,
        text: Optional[str] = None,
        label: Optional[str] = None,
        placeholder: Optional[str] = None,
        role: Optional[str] = None,
    ) -> Locator:
        context = FailedLocatorContext(
            original_locator=self.original_locator,
            action=action,
            text=text,
            label=label,
            placeholder=placeholder,
            role=role,
        )

        retrieved = self.query_retriever.retrieve(
            context,
            top_k=max(self.config.max_alternative_attempts, 5),
            per_query_top_k=3,
        )
        candidates = self.locator_generator.generate(
            context=context,
            retrieved=retrieved,
            top_k=max(self.config.max_alternative_attempts * 2, 6),
        )

        attempted = 0
        for candidate in candidates:
            if attempted >= self.config.max_alternative_attempts:
                break

            locator = self._candidate_to_locator(candidate)
            attempted += 1

            try:
                if action == "click":
                    await locator.click(timeout=self.config.action_timeout_ms)
                elif action == "fill":
                    await locator.fill(fill_value or "", timeout=self.config.action_timeout_ms)
                else:
                    continue
                return locator
            except Exception:
                continue

        raise original_error

    def _candidate_to_locator(self, candidate: LocatorCandidate) -> Locator:
        """Map LocatorCandidate into a concrete Playwright locator call."""
        if candidate.strategy == "get_by_role":
            return self.page.get_by_role(
                candidate.value["role"],
                name=candidate.value.get("name"),
            )
        if candidate.strategy == "get_by_text":
            return self.page.get_by_text(candidate.value["text"])
        if candidate.strategy == "get_by_label":
            return self.page.get_by_label(candidate.value["label"])
        if candidate.strategy == "get_by_placeholder":
            return self.page.get_by_placeholder(candidate.value["placeholder"])
        if candidate.strategy == "css":
            return self.page.locator(candidate.value["selector"])
        if candidate.strategy == "xpath":
            return self.page.locator(f"xpath={candidate.value['selector']}")

        return self.page.locator(self.original_locator)
