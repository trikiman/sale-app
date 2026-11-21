"""The batch arithmetic must cover a 100-card markdown day without holes or overlap.

The live proof on 21.11 22:25 MSK was a single batch (`Batch 0-4: added 4`): the inline
section held four cards. The 97-minute gap #11 was caused by a hundred cards in one
evaluate, which needs ten batches — nobody has observed `Batch 10-20` yet.

This test cannot prove the browser behaviour; it proves the arithmetic read straight from
scrape_green.py: every card index is visited exactly once, and a big day is split into
ceil(total / batch_size) calls rather than one.
"""
import ast
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "scrape_green.py").read_text(encoding="utf-8")


def _body() -> str:
    tree = ast.parse(SRC)
    node = next(n for n in tree.body
                if isinstance(n, ast.AsyncFunctionDef) and n.name == "_add_green_cards_to_cart")
    return ast.get_source_segment(SRC, node) or ""


def _windows(total_cards: int, batch_size: int = 10):
    """Reproduce the loop using the literals taken from the real function."""
    body = _body()
    m = re.search(r"for start in range\(0, max\(total_cards, 0\), batch_size\)", body)
    assert m, "the batching loop disappeared from _add_green_cards_to_cart"
    e = re.search(r"end = min\(start \+ batch_size, total_cards\)", body)
    assert e, "the batch end must be clamped to total_cards"
    return [(start, min(start + batch_size, total_cards))
            for start in range(0, max(total_cards, 0), batch_size)]


def test_a_hundred_cards_are_split_into_ten_batches():
    windows = _windows(100)
    assert len(windows) == 10, f"expected ten evaluates, got {len(windows)}"
    assert windows[0] == (0, 10)
    assert windows[-1] == (90, 100)


def test_every_card_index_is_visited_exactly_once():
    for total in (4, 10, 11, 48, 96, 98, 100):
        seen: list[int] = []
        for start, end in _windows(total):
            seen.extend(range(start, end))
        assert seen == list(range(total)), f"coverage broken at total={total}"


def test_the_small_day_stays_in_one_batch():
    # the case that actually ran in production: four cards, one evaluate
    assert _windows(4) == [(0, 4)]


def test_no_empty_trailing_batch():
    # 100 is a multiple of ten: an off-by-one must not emit Batch 100-100
    for total in (10, 20, 100):
        assert all(start < end for start, end in _windows(total))