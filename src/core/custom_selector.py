"""Step 6: Custom selector registration for SmartLabels.

Provides a Playwright custom selector engine so tests can directly use:
    page.locator("smartlabels=First Name|FirstName")
"""

from __future__ import annotations

from typing import Iterable, List

from playwright.async_api import Playwright


_SMARTLABELS_ENGINE = r"""
{
  query(root, selector) {
    const labels = (selector || "")
      .split("|")
      .map(s => s.trim())
      .filter(Boolean);

    if (!labels.length) return null;

    const normalize = (txt) => (txt || "").replace(/\s+/g, " ").trim().toLowerCase();

    const candidates = root.querySelectorAll("input,textarea,select,button,a,[role],[aria-label],[placeholder]");

    for (const label of labels) {
      const q = normalize(label);

      for (const el of candidates) {
        const aria = normalize(el.getAttribute("aria-label"));
        const placeholder = normalize(el.getAttribute("placeholder"));
        const text = normalize(el.textContent);
        const id = el.getAttribute("id");

        let associatedLabel = "";
        if (id) {
          const found = root.querySelector(`label[for="${CSS.escape(id)}"]`);
          associatedLabel = normalize(found ? found.textContent : "");
        }

        if (aria === q || placeholder === q || text === q || associatedLabel === q) {
          return el;
        }
      }
    }

    return null;
  },

  queryAll(root, selector) {
    const labels = (selector || "")
      .split("|")
      .map(s => s.trim())
      .filter(Boolean);

    if (!labels.length) return [];

    const normalize = (txt) => (txt || "").replace(/\s+/g, " ").trim().toLowerCase();

    const candidates = Array.from(root.querySelectorAll("input,textarea,select,button,a,[role],[aria-label],[placeholder]"));
    const out = [];

    for (const el of candidates) {
      const aria = normalize(el.getAttribute("aria-label"));
      const placeholder = normalize(el.getAttribute("placeholder"));
      const text = normalize(el.textContent);
      const id = el.getAttribute("id");

      let associatedLabel = "";
      if (id) {
        const found = root.querySelector(`label[for="${CSS.escape(id)}"]`);
        associatedLabel = normalize(found ? found.textContent : "");
      }

      const matches = labels.some(label => {
        const q = normalize(label);
        return aria === q || placeholder === q || text === q || associatedLabel === q;
      });

      if (matches) out.push(el);
    }

    return out;
  }
}
"""


async def register_smartlabels_selector(playwright: Playwright, *, selector_name: str = "smartlabels") -> None:
    """Register SmartLabels custom selector engine in Playwright.

    After registration, use:
        page.locator("smartlabels=First Name|FirstName")
    """
    await playwright.selectors.register(selector_name, _SMARTLABELS_ENGINE)


def build_smartlabels_locator_value(labels: Iterable[str]) -> str:
    """Build selector payload string from labels list.

    Example:
        ["First Name", "FirstName"] -> "First Name|FirstName"
    """
    normalized: List[str] = [label.strip() for label in labels if label and label.strip()]
    return "|".join(normalized)
