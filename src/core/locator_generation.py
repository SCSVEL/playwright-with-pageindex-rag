"""Step 4: Locator Generation (semantic priority).

Generates alternative Playwright locator candidates from failed locator context
and retrieval results. Semantic locators are always prioritized over XPath/CSS.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from .query_retrieval import FailedLocatorContext, RetrievalResult


@dataclass
class LocatorCandidate:
    """Represents a generated locator candidate in ranked order."""

    strategy: str
    value: Dict[str, Any]
    confidence: float
    source_xpath: Optional[str] = None

    def playwright_expression(self) -> str:
        """Render candidate as a Python Playwright expression snippet."""
        if self.strategy == "get_by_role":
            role = self.value.get("role")
            name = self.value.get("name")
            return f'page.get_by_role("{role}", name="{name}")'
        if self.strategy == "get_by_text":
            return f'page.get_by_text("{self.value.get("text")}")'
        if self.strategy == "get_by_label":
            return f'page.get_by_label("{self.value.get("label")}")'
        if self.strategy == "get_by_placeholder":
            return f'page.get_by_placeholder("{self.value.get("placeholder")}")'
        if self.strategy == "css":
            return f'page.locator("{self.value.get("selector")}")'
        if self.strategy == "xpath":
            return f'page.locator("xpath={self.value.get("selector")}")'
        return 'page.locator("UNKNOWN")'


class LocatorGenerator:
    """Generate semantic-first locator alternatives from retrieved elements."""

    _TAG_TO_ROLE = {
        "button": "button",
        "a": "link",
        "input": "textbox",
        "textarea": "textbox",
        "select": "combobox",
        "option": "option",
        "img": "img",
        "checkbox": "checkbox",
    }

    def generate(
        self,
        context: FailedLocatorContext,
        retrieved: List[RetrievalResult],
        top_k: int = 8,
    ) -> List[LocatorCandidate]:
        """Generate candidates in strict priority order.

        Priority:
        1. get_by_role
        2. get_by_text
        3. get_by_label
        4. get_by_placeholder
        5. css
        6. xpath
        """
        ranked: List[LocatorCandidate] = []
        seen: set[Tuple[str, str]] = set()

        def add(candidate: LocatorCandidate, key_repr: str) -> None:
            key = (candidate.strategy, key_repr)
            if key in seen:
                return
            seen.add(key)
            ranked.append(candidate)

        # Context-level semantic candidates first.
        if context.role and (context.text or context.label):
            name = context.text or context.label
            add(
                LocatorCandidate(
                    strategy="get_by_role",
                    value={"role": context.role, "name": name},
                    confidence=0.99,
                ),
                f"{context.role}:{name}",
            )

        if context.text:
            add(
                LocatorCandidate(
                    strategy="get_by_text",
                    value={"text": context.text},
                    confidence=0.96,
                ),
                context.text,
            )

        if context.label:
            add(
                LocatorCandidate(
                    strategy="get_by_label",
                    value={"label": context.label},
                    confidence=0.95,
                ),
                context.label,
            )

        if context.placeholder:
            add(
                LocatorCandidate(
                    strategy="get_by_placeholder",
                    value={"placeholder": context.placeholder},
                    confidence=0.94,
                ),
                context.placeholder,
            )

        # Retrieval-driven candidates.
        for item in retrieved:
            inferred_role = self._infer_role(item)
            name = item.accessible_name or self._attr(item, "aria-label") or self._attr(item, "name")
            placeholder = self._attr(item, "placeholder")

            if inferred_role and name:
                add(
                    LocatorCandidate(
                        strategy="get_by_role",
                        value={"role": inferred_role, "name": name},
                        confidence=max(0.6, min(0.98, item.score)),
                        source_xpath=item.xpath,
                    ),
                    f"{inferred_role}:{name}",
                )

            if item.accessible_name:
                add(
                    LocatorCandidate(
                        strategy="get_by_text",
                        value={"text": item.accessible_name},
                        confidence=max(0.55, min(0.95, item.score - 0.02)),
                        source_xpath=item.xpath,
                    ),
                    item.accessible_name,
                )

            if name:
                add(
                    LocatorCandidate(
                        strategy="get_by_label",
                        value={"label": name},
                        confidence=max(0.5, min(0.93, item.score - 0.04)),
                        source_xpath=item.xpath,
                    ),
                    name,
                )

            if placeholder:
                add(
                    LocatorCandidate(
                        strategy="get_by_placeholder",
                        value={"placeholder": placeholder},
                        confidence=max(0.5, min(0.92, item.score - 0.06)),
                        source_xpath=item.xpath,
                    ),
                    placeholder,
                )

            css_selector = self._build_css_selector(item)
            if css_selector:
                add(
                    LocatorCandidate(
                        strategy="css",
                        value={"selector": css_selector},
                        confidence=max(0.35, min(0.85, item.score - 0.2)),
                        source_xpath=item.xpath,
                    ),
                    css_selector,
                )

            add(
                LocatorCandidate(
                    strategy="xpath",
                    value={"selector": item.xpath},
                    confidence=max(0.3, min(0.8, item.score - 0.22)),
                    source_xpath=item.xpath,
                ),
                item.xpath,
            )

        # Force strategy-priority ordering regardless of insertion interleaving.
        priority = {
            "get_by_role": 0,
            "get_by_text": 1,
            "get_by_label": 2,
            "get_by_placeholder": 3,
            "css": 4,
            "xpath": 5,
        }
        ranked.sort(key=lambda c: (priority.get(c.strategy, 99), -c.confidence))

        return ranked[:top_k]

    def _infer_role(self, item: RetrievalResult) -> Optional[str]:
        explicit = self._attr(item, "role")
        if explicit:
            return str(explicit)
        if item.tag:
            return self._TAG_TO_ROLE.get(item.tag)
        return None

    @staticmethod
    def _attr(item: RetrievalResult, key: str) -> Optional[str]:
        value = item.attrs.get(key)
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _build_css_selector(item: RetrievalResult) -> Optional[str]:
        # Prefer stable attributes when available.
        data_testid = item.attrs.get("data-testid")
        if data_testid:
            return f'[data-testid="{data_testid}"]'

        elem_id = item.attrs.get("id")
        if elem_id:
            return f'#{elem_id}'

        tag = item.tag or "*"
        name = item.attrs.get("name")
        if name:
            return f'{tag}[name="{name}"]'

        return None
