"""The modal loader must degrade, not die, when the page is heavy.

08:26 on 21.11.2026: the modal scroll evaluate timed out after collecting 98 products, and
the TimeoutError ended the run — the same failure mode as the click loop, one step earlier.
A scroll that will not answer is not a reason to lose the modal: the loader now stops with
whatever it collected. The evaluate deadline also moves 45 -> 90 s, because a single call
over a 100-card modal legitimately needed longer than 45 s.
"""
import ast
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "scrape_green.py").read_text(encoding="utf-8")


def test_eval_deadline_raised_for_heavy_modal():
    value = int(SRC.split("JS_EVAL_TIMEOUT_S = ")[1].split("\n")[0])
    assert value == 90
    assert 15 <= value <= 120


def test_modal_scroll_is_guarded():
    tree = ast.parse(SRC)
    fn = next(n for n in tree.body
              if isinstance(n, ast.AsyncFunctionDef) and n.name == "scrape_green_prices_async")
    guarded = False
    for node in ast.walk(fn):
        if isinstance(node, ast.Try):
            seg = ast.get_source_segment(SRC, node) or ""
            if "js-modal-cart-prods-scroll" in seg:
                guarded = True
                assert "break" in seg, (
                    "a stuck scroll must stop the loader, not raise out of the cycle"
                )
    assert guarded, "the modal scroll evaluate must be wrapped in try/except"


def test_loader_keeps_collected_cards_on_timeout():
    # the log line must name the count, otherwise a degraded load is invisible in the log
    assert "stopping the loader at" in SRC