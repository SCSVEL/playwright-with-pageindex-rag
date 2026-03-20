"""Tests for Step 4: Locator Generation (semantic priority)."""

from src.core import (
    FailedLocatorContext,
    LocatorGenerator,
    RetrievalResult,
)


def _sample_retrieval() -> list[RetrievalResult]:
    return [
        RetrievalResult(
            xpath="//html/body/form/button",
            tag="button",
            accessible_name="Login",
            attrs={"id": "submit-btn", "name": "submit", "data-testid": "login-cta"},
            raw_document="button | Login",
            distance=0.12,
            score=0.892,
        ),
        RetrievalResult(
            xpath="//html/body/form/input[1]",
            tag="input",
            accessible_name="First Name",
            attrs={"name": "firstName", "placeholder": "First Name"},
            raw_document="input | First Name",
            distance=0.2,
            score=0.833,
        ),
    ]


def test_semantic_strategies_are_prioritized_before_css_xpath():
    generator = LocatorGenerator()
    context = FailedLocatorContext(
        original_locator="button[name='signin']",
        role="button",
        text="Login",
    )

    candidates = generator.generate(context=context, retrieved=_sample_retrieval(), top_k=10)

    strategies = [c.strategy for c in candidates]

    # Ensure semantic-first ordering.
    assert "get_by_role" in strategies
    assert "get_by_text" in strategies
    assert "css" in strategies
    assert "xpath" in strategies

    first_css_index = strategies.index("css")
    first_xpath_index = strategies.index("xpath")

    for semantic in ["get_by_role", "get_by_text", "get_by_label", "get_by_placeholder"]:
        if semantic in strategies:
            assert strategies.index(semantic) < first_css_index
            assert strategies.index(semantic) < first_xpath_index


def test_playwright_expression_rendering_is_valid_for_semantic_methods():
    generator = LocatorGenerator()
    context = FailedLocatorContext(
        original_locator="input[name='first_name']",
        label="First Name",
        placeholder="First Name",
    )

    candidates = generator.generate(context=context, retrieved=_sample_retrieval(), top_k=12)
    expressions = [c.playwright_expression() for c in candidates]

    assert any(expr.startswith('page.get_by_role(') for expr in expressions)
    assert any(expr.startswith('page.get_by_text(') for expr in expressions)
    assert any(expr.startswith('page.get_by_label(') for expr in expressions)
    assert any(expr.startswith('page.get_by_placeholder(') for expr in expressions)
    assert any(expr.startswith('page.locator("xpath=') for expr in expressions)
