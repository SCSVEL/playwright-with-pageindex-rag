"""
HTML Capture Module for Playwright PageIndex Retry Strategy.

This module provides functionality to capture and parse the page's HTML tree,
extract elements, attributes, text content, and hierarchy. Snapshots are created
with metadata (URL, timestamp) for versioning.
"""

import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict
from bs4 import BeautifulSoup, Tag
from playwright.async_api import Page


@dataclass
class ElementNode:
    """Represents a parsed HTML element with metadata."""
    tag: str
    attrs: Dict[str, str]
    text: str
    xpath: str
    css_selector: Optional[str] = None
    children_count: int = 0
    visible: bool = True
    parent_tag: Optional[str] = None
    accessible_name: Optional[str] = None


@dataclass
class HTMLSnapshot:
    """Represents a snapshot of the page's HTML at a point in time."""
    url: str
    timestamp: str
    html_content: str
    elements: List[ElementNode]
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert snapshot to dictionary."""
        return {
            "url": self.url,
            "timestamp": self.timestamp,
            "html_length": len(self.html_content),
            "elements_count": len(self.elements),
            "elements": [asdict(el) for el in self.elements],
            "metadata": self.metadata,
        }


class HTMLCapture:
    """
    Captures and parses the page's HTML tree from a Playwright page.
    
    Usage:
        capture = HTMLCapture()
        snapshot = await capture.capture_page(page)
        print(f"Captured {snapshot.elements_count} elements")
    """

    def __init__(self):
        """Initialize HTML Capture module."""
        self.last_snapshot: Optional[HTMLSnapshot] = None

    async def capture_page(self, page: Page, metadata: Optional[Dict[str, Any]] = None) -> HTMLSnapshot:
        """
        Capture the current page's HTML and parse it into a tree structure.

        Args:
            page: Playwright Page object
            metadata: Optional metadata to store with snapshot (e.g., test name, context)

        Returns:
            HTMLSnapshot: Snapshot containing parsed elements and metadata
        """
        # Get page URL and timestamp
        url = page.url
        timestamp = datetime.now().isoformat()

        # Capture raw HTML content
        html_content = await page.content()

        # Parse HTML into tree structure
        elements = self._parse_html(html_content, page)

        # Create snapshot with metadata
        snapshot_metadata = metadata or {}
        snapshot_metadata["browser"] = page.context.browser.browser_type.name if page.context.browser else "unknown"

        snapshot = HTMLSnapshot(
            url=url,
            timestamp=timestamp,
            html_content=html_content,
            elements=elements,
            metadata=snapshot_metadata,
        )

        # Store as last snapshot for reference
        self.last_snapshot = snapshot

        return snapshot

    def _parse_html(self, html_content: str, page: Page) -> List[ElementNode]:
        """
        Parse HTML content into a list of ElementNode objects.

        Args:
            html_content: Raw HTML string
            page: Playwright Page object (for accessibility queries)

        Returns:
            List[ElementNode]: List of parsed elements with metadata
        """
        soup = BeautifulSoup(html_content, "html.parser")
        elements = []

        # Walk through all elements
        for idx, element in enumerate(soup.find_all()):
            if isinstance(element, Tag):
                node = self._create_element_node(element, page, soup)
                elements.append(node)

        return elements

    def _create_element_node(self, element: Tag, page: Page, soup: BeautifulSoup) -> ElementNode:
        """
        Create an ElementNode from a BeautifulSoup Tag.

        Args:
            element: BeautifulSoup Tag element
            page: Playwright Page object
            soup: BeautifulSoup object (for XPath calculation)

        Returns:
            ElementNode: Parsed element node
        """
        tag = element.name or "unknown"
        attrs = dict(element.attrs) if element.attrs else {}

        # Extract text content (visible text only, stripped)
        text = element.get_text(strip=True)[:200]  # Limit to 200 chars

        # Calculate XPath (simple xpath generation)
        xpath = self._generate_xpath(element)

        # Check if element has visible content
        visible = self._is_visible(element)

        # Get accessible name (aria-label, placeholder, alt, text content)
        accessible_name = self._get_accessible_name(element)

        # Count children
        children_count = len(element.find_all(recursive=False))

        # Get parent tag
        parent_tag = element.parent.name if element.parent and isinstance(element.parent, Tag) else None

        return ElementNode(
            tag=tag,
            attrs=attrs,
            text=text,
            xpath=xpath,
            css_selector=None,  # TODO: Add CSS selector generation
            children_count=children_count,
            visible=visible,
            parent_tag=parent_tag,
            accessible_name=accessible_name,
        )

    def _generate_xpath(self, element: Tag) -> str:
        """
        Generate a simple XPath for the given element.

        Args:
            element: BeautifulSoup Tag element

        Returns:
            str: XPath string
        """
        path = []
        current = element

        while current and isinstance(current, Tag):
            # Get position among siblings of same tag
            siblings = [s for s in current.parent.find_all(current.name, recursive=False)] if current.parent else []
            position = siblings.index(current) + 1 if siblings else 1
            
            # Build XPath component
            xpath_component = f"{current.name}[{position}]" if len(siblings) > 1 else current.name
            path.append(xpath_component)

            current = current.parent

        # Reverse to get root-to-element path
        path.reverse()
        xpath = f"//{'/'.join(path)}"

        return xpath

    def _is_visible(self, element: Tag) -> bool:
        """
        Determine if element is likely visible (heuristic based on tags and classes).

        Args:
            element: BeautifulSoup Tag element

        Returns:
            bool: True if element appears visible
        """
        # Hidden tags or elements with display:none, visibility:hidden
        hidden_tags = ["script", "style", "meta", "link", "noscript"]
        if element.name in hidden_tags:
            return False

        # Check for visibility-related classes (simple heuristic)
        classes = element.get("class", [])
        if any("hidden" in str(c).lower() for c in classes):
            return False

        # Check style attribute
        style = element.get("style", "")
        if any(hidden_attr in style.lower() for hidden_attr in ["display:none", "visibility:hidden"]):
            return False

        return True

    def _get_accessible_name(self, element: Tag) -> Optional[str]:
        """
        Get the accessible name for an element (aria-label, placeholder, alt, text, etc.).

        Args:
            element: BeautifulSoup Tag element

        Returns:
            str or None: Accessible name if found
        """
        # Priority: aria-label > title > placeholder > alt > text content (for buttons/links)
        aria_label = element.get("aria-label")
        if aria_label:
            return aria_label

        title = element.get("title")
        if title:
            return title

        placeholder = element.get("placeholder")
        if placeholder:
            return placeholder

        alt = element.get("alt")
        if alt:
            return alt

        # For buttons and links, use text content
        if element.name in ["button", "a"]:
            text = element.get_text(strip=True)
            if text:
                return text[:100]  # Limit to 100 chars

        return None

    def export_snapshot_json(self, snapshot: HTMLSnapshot, output_path: str) -> None:
        """
        Export snapshot to JSON file for debugging/analysis.

        Args:
            snapshot: HTMLSnapshot object to export
            output_path: Path to write JSON file
        """
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(snapshot.to_dict(), f, indent=2, ensure_ascii=False)

    def export_html_content(self, snapshot: HTMLSnapshot, output_path: str) -> None:
        """
        Export raw HTML content to file.

        Args:
            snapshot: HTMLSnapshot object
            output_path: Path to write HTML file
        """
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(snapshot.html_content)
