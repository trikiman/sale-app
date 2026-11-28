"""Functional proof that `_add_green_cards_to_cart` walks ALL cards in batches.

`test_green_batched_add.py` only asserts the *shape* of the loop (AST: "range with
batch_size", "i < {end}"). That is not the same as proving the coroutine actually
visits every window — a wrong `end`, an early `break` or a swallowed batch would
still pass it.

This test drives the real coroutine with a fake page and records every evaluate:

* 25 cards -> windows (0,10) (10,20) (20,25), 25 added, no failed batch;
* 100 cards -> ten windows, no holes, no overlap, 100 added;
* one dead batch -> the run continues, the dead window costs exactly its own ten
  cards (added = cards - 10), `failed_batches == 1` and `partial == 1`.

Written 2026-11-22 because the production `Batch N-M` lines are minutes-only in
`/admin/logs`: the multi-batch path had no offline proof at all.
"""
import asyncio
import importlib
import json
import pathlib
import re
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# nodriver is not installed on the workstation; the coroutine under test never
# touches it, so a bare stub is enough to import the module.
#
# The stub is removed again straight after the import: `sys.modules` is shared
# for the whole pytest session, and a fake `nodriver` left behind silently
# changes the outcome of other suites (tests/test_green_recovery.py and
# tests/test_scrape_green_ws_recovery.py install their own richer stub and lost
# nine tests to this leak on 2026-11-22). `scrape_green` is dropped from the
# cache too, so every other module imports it under its own stub.
_added_stub = "nodriver" not in sys.modules
if _added_stub:
    _stub = types.ModuleType("nodriver")
    _stub.cdp = types.SimpleNamespace()  # type: ignore[attr-defined]
    sys.modules["nodriver"] = _stub

sg = importlib.import_module("scrape_green")

if _added_stub:
    sys.modules.pop("nodriver", None)
    sys.modules.pop("scrape_green", None)

WINDOW_RE = re.compile(r"for \(let i = (\d+); i < (\d+); i\+\+\)")


class FakePage:
    """Placeholder — the fake _js below ignores it."""


def _drive(total_cards: int, fail_windows=(), scope_cards=None, restore_modal=None):
    """Drive the coroutine.

    `scope_cards` overrides how many cards the scope reports (a re-navigated page
    reports fewer); `restore_modal` is the value `_reopen_green_modal` yields on each
    call, to simulate a recovery that works or keeps failing.
    """
    calls = []
    seen = {"cards": total_cards if scope_cards is None else scope_cards}
    fired = set()
    restores = list(restore_modal or [])

    async def fake_wait(page, card_source='inline', timeout_s=25.0):
        return seen["cards"] if restore_modal is None else (
            restores.pop(0) if restores else 0)

    async def fake_js(page, script, *args, **kwargs):
        match = WINDOW_RE.search(script)
        if not match:
            # recovery probes issued by _reopen_green_modal / _recover_green_scope
            if "querySelectorAll('.ProductCard, .ProductCards__item').length" in script:
                return seen["cards"] if restore_modal is None else (
                    restores.pop(0) if restores else 0)
            return True
        start, end = int(match.group(1)), int(match.group(2))
        calls.append((start, end))
        if (start, end) in fail_windows and (start, end) not in fired:
            fired.add((start, end))
            raise TimeoutError("batch blew the JS deadline")
        if seen["cards"] == 0:
            return json.dumps({"results": {}, "added": 0, "scope_missing": 1,
                               "in_scope": 0, "scope_hidden": 1})
        added = len([i for i in range(start, min(end, total_cards)) if i < seen["cards"]])
        return json.dumps({
            "results": {"added": added, "no_button": 0, "already_in_cart": 0,
                        "no_card": (end - start) - added, "disabled": 0},
            "added": added,
            "in_scope": seen["cards"],
        })

    async def fake_diagnose(page, limit=4):
        return None

    sg._wait_for_green_cards = fake_wait  # type: ignore[attr-defined]
    sg._js = fake_js  # type: ignore[attr-defined]
    sg._diagnose_no_button_cards = fake_diagnose  # type: ignore[attr-defined]

    totals, added = asyncio.run(
        sg._add_green_cards_to_cart(FakePage(), "inline", total_cards)
    )
    return calls, totals, added


def test_25_cards_are_walked_in_three_windows():
    calls, totals, added = _drive(25)
    assert calls == [(0, 10), (10, 20), (20, 25)], calls
    assert added == 25
    assert totals["failed_batches"] == 0


def test_100_cards_cover_every_card_without_holes_or_overlap():
    calls, totals, added = _drive(100)
    assert len(calls) == 10, calls
    assert calls[0][0] == 0 and calls[-1][1] == 100
    for (a_start, a_end), (b_start, b_end) in zip(calls, calls[1:]):
        assert a_end == b_start, f"hole or overlap between {a_end} and {b_start}"
    assert sum(end - start for start, end in calls) == 100
    assert added == 100


def test_one_dead_batch_is_retried_not_skipped():
    # the timeout re-navigates the page, so the window is retried once the scope is
    # back; the retry succeeds and costs no cards, only a failed-batch counter
    calls, totals, added = _drive(25, fail_windows={(10, 20)})
    assert calls == [(0, 10), (10, 20), (10, 20), (20, 25)], calls
    assert totals["failed_batches"] == 1
    assert totals["partial"] == 1
    assert added == 25, "a successful retry must not lose the window's cards"


def test_zero_cards_makes_no_evaluate_calls():
    calls, totals, added = _drive(0)
    assert calls == []
    assert added == 0