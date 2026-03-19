"""Step 3: Query and Retrieval for PageIndex.

This module builds query candidates from a failed locator context and retrieves
similar indexed elements from PageIndex with scoring and deduplication.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from .page_index import PageIndex


@dataclass
class FailedLocatorContext:
    """Context captured when a primary locator fails."""

    original_locator: str
    action: Optional[str] = None
    role: Optional[str] = None
    text: Optional[str] = None
    label: Optional[str] = None
    placeholder: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RetrievalResult:
    """Normalized retrieval result for downstream locator generation."""

    xpath: str
    tag: Optional[str]
    accessible_name: Optional[str]
    attrs: Dict[str, Any]
    raw_document: str
    distance: float
    score: float


class QueryRetriever:
    """Build query candidates and retrieve ranked matches from PageIndex."""

    def __init__(self, page_index: PageIndex):
        self.page_index = page_index

    def build_query_candidates(self, context: FailedLocatorContext) -> List[str]:
        """Build robust query candidates from failed locator context."""
        candidates: List[str] = []

        def add(val: Optional[str]) -> None:
            if val and val.strip() and val.strip() not in candidates:
                candidates.append(val.strip())

        add(context.original_locator)
        add(context.text)
        add(context.label)
        add(context.placeholder)

        if context.role and context.text:
            add(f"{context.role} {context.text}")
        if context.role and context.label:
            add(f"{context.role} {context.label}")

        # Attribute-driven search hints for dynamic pages.
        for key in ["id", "name", "data-testid", "aria-label", "placeholder", "role"]:
            value = context.attributes.get(key)
            if value:
                add(f"{key}:{value}")

        return candidates

    def retrieve(
        self,
        context: FailedLocatorContext,
        top_k: int = 5,
        per_query_top_k: int = 3,
    ) -> List[RetrievalResult]:
        """Retrieve, score, and deduplicate candidate elements.

        - Runs retrieval for multiple query candidates.
        - Deduplicates by xpath.
        - Sorts by descending score (lower distance => higher score).
        """
        query_candidates = self.build_query_candidates(context)
        if not query_candidates:
            return []

        merged: Dict[str, RetrievalResult] = {}

        for query_text in query_candidates:
            raw_results = self.page_index.query(query_text, top_k=per_query_top_k)
            for item in raw_results:
                metadata = item.get("metadata") or {}
                xpath = metadata.get("xpath")
                if not xpath:
                    continue

                distance = float(item.get("distance") or 0.0)
                score = 1.0 / (1.0 + distance)

                attrs_raw = metadata.get("attrs")
                attrs: Dict[str, Any] = {}
                if isinstance(attrs_raw, str) and attrs_raw:
                    try:
                        attrs = json.loads(attrs_raw)
                    except Exception:
                        attrs = {"raw": attrs_raw}
                elif isinstance(attrs_raw, dict):
                    attrs = attrs_raw

                candidate = RetrievalResult(
                    xpath=xpath,
                    tag=metadata.get("tag"),
                    accessible_name=metadata.get("accessible_name"),
                    attrs=attrs,
                    raw_document=item.get("document") or "",
                    distance=distance,
                    score=score,
                )

                # Keep best-scoring version per xpath.
                existing = merged.get(xpath)
                if existing is None or candidate.score > existing.score:
                    merged[xpath] = candidate

        ranked = sorted(merged.values(), key=lambda x: x.score, reverse=True)
        return ranked[:top_k]
