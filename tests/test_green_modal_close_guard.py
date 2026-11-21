"""Closing the green modal must never end a run that already filled the cart.

21.11.2026 07:17 and 07:26: two cycles failed with `asyncio.exceptions.TimeoutError` raised
from `_close_green_modal` → `_js` → `page.evaluate` (JS_EVAL_TIMEOUT_S = 45 s), right after
69 products had been added. The cart was fine; the modal close was cosmetic, and the next step
reloads the page anyway. The scraper now continues (with a re-acquired page handle) instead of
throwing away a completed run.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "scrape_green.py").read_text(encoding="utf-8")


def _function(name: str) -> str:
    tree = ast.parse(SRC)
    node = next(n for n in tree.body
                if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)) and n.name == name)
    return ast.get_source_segment(SRC, node) or ""


def test_modal_close_is_guarded():
    body = _function("scrape_green_prices_async")
    assert "_close_green_modal" in body
    # the call must sit inside a try block, not at the mercy of a 45 s evaluate timeout
    tree = ast.parse(SRC)
    fn = next(n for n in tree.body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "scrape_green_prices_async")
    guarded = False
    for node in ast.walk(fn):
        if isinstance(node, ast.Try):
            seg = ast.get_source_segment(SRC, node) or ""
            if "_close_green_modal" in seg:
                guarded = True
                assert "except" in seg, "the guard must have an except clause"
    assert guarded, "a modal-close timeout must not abort the cycle"


def test_guard_reacquires_the_page():
    """The try-block that wraps the modal close must re-acquire the dead page handle."""
    tree = ast.parse(SRC)
    fn = next(n for n in tree.body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "scrape_green_prices_async")
    found_guarded = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Try):
            continue
        seg = ast.get_source_segment(SRC, node) or ""
        if "_close_green_modal" not in seg:
            continue
        handler_src = "".join(
            ast.get_source_segment(SRC, h) or "" for h in node.handlers
        )
        found_guarded.append("_reacquire_page" in handler_src)
    assert found_guarded, "no try/except around _close_green_modal"
    assert any(found_guarded), (
        "the modal-close handler must re-acquire the page: after a failed evaluate the old "
        "handle is dead"
    )