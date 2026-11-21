"""Adding the green cards must not blow the JS deadline on a big markdown day.

21.11.2026: the modal held 100 green cards. One batched evaluate did scrollIntoView +
a five-event pointer sequence + a modal sweep for all 100 in a single call and exceeded
JS_EVAL_TIMEOUT_S = 45 s. The TimeoutError killed five runs in a row (07:17, 07:26, 07:44,
07:55, 08:02) — and because GREEN runs first, RED and YELLOW never executed, so the API
silently dropped red and yellow and the site showed only greens.

Batches of ten keep each evaluate inside the deadline, and a failed batch costs ten cards
instead of the entire cycle.
"""
import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "scrape_green.py").read_text(encoding="utf-8")


def _func(name: str) -> str:
    tree = ast.parse(SRC)
    node = next(n for n in tree.body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == name)
    return ast.get_source_segment(SRC, node) or ""


def test_clicks_are_issued_in_batches():
    body = _func("_add_green_cards_to_cart")
    assert "batch_size: int = 10" in body
    assert "for start in range(0, max(total_cards, 0), batch_size)" in body, (
        "the whole list must not be sent in a single evaluate"
    )


def test_js_loop_uses_the_batch_bounds():
    body = _func("_add_green_cards_to_cart")
    assert "for (let i = {start}; i < {end}; i++)" in body
    assert "i < {total_cards}" not in body, "the JS loop must respect the batch window"


def test_a_failed_batch_does_not_end_the_cycle():
    tree = ast.parse(SRC)
    fn = next(n for n in tree.body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "_add_green_cards_to_cart")
    guarded = False
    for node in ast.walk(fn):
        if isinstance(node, ast.Try):
            seg = ast.get_source_segment(SRC, node) or ""
            if "_js(page, f" in seg and "failed_batches" in seg:
                guarded = True
                assert "_reacquire_page" in seg, "a dead handle must be re-acquired"
    assert guarded, "a batch timeout must be caught, counted and skipped"


def test_caller_passes_the_browser_handle():
    # only the call sites inside scrape_green_prices_async can recover a dead page
    assert "browser=browser" in SRC
    assert SRC.count("_add_green_cards_to_cart(page,") >= 5