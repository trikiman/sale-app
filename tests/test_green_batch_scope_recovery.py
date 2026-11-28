"""After one batch timeout the remaining windows must NOT collapse to zero.

Live proof of the bug (cron `3dc7ab1ba33a`, 28.11.2026, from `.planning/STATE.md`):

    Modal loaded: 179 cards
    Batch 0-10 … Batch 40-50: added 10 (running total 50)
    Batch 50-60 failed (TimeoutError: ) — continuing with the next batch
    Batch 60-70 … Batch 170-179: added 0 (running total 50)
    Added 50/179 items to cart

`_reacquire_page` navigates to GREEN_URL, so the modal the loop indexes into is gone;
the follow-up evaluates still resolve (modal shell present, zero cards), so every later
window was a silent no-op. `test_green_batched_windows` could not see it: its fake
always reported the full card list.

These tests drive the real coroutine with a fake page that models the scope collapsing
after the timeout, and assert that the scope is restored and the walk continues.
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

# nodriver is absent on the workstation; the coroutine never touches it. The stub and
# the module cache entry are dropped right after import so neighbouring suites are not
# affected (see tests/test_green_batched_windows.py for the whole story).
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
    pass


def _drive(total_cards, timeout_window, reopen_results, card_source="modal", scope_cards=None):
    """Run one batch pass; the scope dies at `timeout_window`.

    `reopen_results` feeds consecutive `_reopen_green_modal` probes — 0 means the
    recovery found no cards, a positive number means the modal came back with that
    many.
    """
    calls = []
    probes = []
    fired = set()
    start_cards = total_cards if scope_cards is None else scope_cards
    state = {"cards": start_cards, "modal_open": start_cards > 0}
    reopens = list(reopen_results)

    async def fake_wait(page, src="inline", timeout_s=25.0):
        return state["cards"]

    async def fake_js(page, script, *args, **kwargs):
        match = WINDOW_RE.search(script)
        if not match:
            if "querySelectorAll('.ProductCard, .ProductCards__item').length" in script:
                probes.append(1)
                nxt = reopens.pop(0) if reopens else 0
                if nxt:
                    state["cards"] = nxt
                    state["modal_open"] = True
                return nxt
            return True
        start, end = int(match.group(1)), int(match.group(2))
        calls.append((start, end))
        if (start, end) == timeout_window and state["cards"] == total_cards \
                and (start, end) not in fired:
            # the timeout re-navigates the page: modal and cards are gone
            fired.add((start, end))
            state["cards"] = 0
            state["modal_open"] = False
            raise TimeoutError("")
        if not state["modal_open"]:
            # the modal shell is in the DOM but holds no green cards: the exact shape
            # that made every later window report `added 0` without raising
            return json.dumps({"results": {}, "added": 0, "scope_missing": 1,
                               "in_scope": 0, "scope_hidden": 1})
        added = len([i for i in range(start, min(end, total_cards)) if i < state["cards"]])
        return json.dumps({
            "results": {"added": added, "no_button": 0, "already_in_cart": 0,
                        "no_card": (end - start) - added, "disabled": 0},
            "added": added,
            "in_scope": state["cards"],
        })

    async def fake_diagnose(page, limit=4):
        return None

    async def fake_reacquire(browser):
        return FakePage()

    sg._wait_for_green_cards = fake_wait  # type: ignore[attr-defined]
    sg._js = fake_js  # type: ignore[attr-defined]
    sg._diagnose_no_button_cards = fake_diagnose  # type: ignore[attr-defined]
    sg._reacquire_page = fake_reacquire  # type: ignore[attr-defined]

    # the production sleeps (1 s + 2 s per modal re-open attempt) dominate the runtime
    _real_sleep = asyncio.sleep

    async def fast_sleep(*args, **kwargs):
        return await _real_sleep(0)

    asyncio.sleep = fast_sleep  # type: ignore[assignment]
    try:
        totals, added = asyncio.run(
            sg._add_green_cards_to_cart(FakePage(), card_source, total_cards, browser=FakePage())
        )
    finally:
        asyncio.sleep = _real_sleep  # type: ignore[assignment]
    return calls, totals, added, probes


def test_the_window_after_a_timeout_still_adds_cards():
    # modal comes back on the first reopen probe; the timed-out window is retried
    calls, totals, added, _ = _drive(30, timeout_window=(10, 20), reopen_results=[30])
    assert (10, 20) in calls, calls
    assert calls.count((10, 20)) == 2, f"the dead window must be retried, got {calls}"
    assert added == 30, f"a successful recovery loses nothing, added={added}"
    assert totals["failed_batches"] == 1
    assert totals["scope_lost"] == 0, "a successful recovery is not a lost scope"
    assert totals["partial"] == 1


def test_recovery_is_logged_and_the_scope_state_is_reported():
    calls, totals, added, probes = _drive(30, timeout_window=(10, 20), reopen_results=[30])
    # 0-10 was fine, 10-20 timed out, the retry of 10-20 must have found the cards
    assert calls[:3] == [(0, 10), (10, 20), (10, 20)], calls
    assert probes, "the recovery must probe the modal instead of guessing"
    assert added == 30


def test_a_scope_that_never_comes_back_ends_the_pass_without_hanging():
    calls, totals, added, _ = _drive(50, timeout_window=(10, 20), reopen_results=[])
    assert added == 10, f"nothing after the timeout can be added, added={added}"
    assert totals["scope_lost"] >= 1, totals
    assert totals["failed_batches"] >= 2
    # the walk must still visit the remaining windows rather than stop at the timeout
    assert calls[-1][1] == 50, calls


def test_recovery_budget_is_bounded():
    calls, totals, added, probes = _drive(100, timeout_window=(10, 20), reopen_results=[])
    # the budget caps recovery ROUNDS (at most 5 modal probes each), not the cheap
    # evaluates: a dead page must not turn nine dead windows into nine full recovery
    # rounds on a 1-vCPU box, but the walk itself still covers every window
    assert len(probes) <= sg.SCOPE_RECOVERY_BUDGET * 5, probes
    assert calls[-1][1] == 100, calls  # no infinite retry loop, the walk still finishes


def test_no_card_inside_a_live_scope_is_not_treated_as_a_lost_scope():
    # declared 30 cards, the scope only renders 12: windows past 12 have no cards but
    # the scope itself is alive, so recovery must not kick in
    calls, totals, added, probes = _drive(30, timeout_window=None, reopen_results=[],
                                          scope_cards=12)
    assert totals["scope_lost"] == 0
    assert totals["failed_batches"] == 0
    assert not probes, "a live scope must not trigger a recovery probe"
    assert added == 12
    assert calls == [(0, 10), (10, 20), (20, 30)]
