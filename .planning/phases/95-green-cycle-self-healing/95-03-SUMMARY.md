---
phase: 95
plan: 95-03
title: Fault-injection harness for the four abort stages
status: complete
requirements: [GREEN-UP-02]
---

# 95-03 — Fault-injection harness (CLOSED)

## What exists

All four abort stages already had harness tests in `tests/test_green_recovery.py`
(10 tests, no Chrome, no network, 10.2 s in the plain venv):

| stage | tests |
|---|---|
| `_safe_js` survives a dead CDP WS | 3 (`survives_dead_ws_and_returns_fresh_page`, `gives_up_after_three_attempts`, `does_not_swallow_real_errors`) |
| `_reacquire_page` retries and never hangs | 2 (`retries_until_a_handle_appears`, `returns_instead_of_hanging_when_all_fail`) |
| `_ensure_delivery_slot` clicks only when needed | 3 (`clicks_nothing_without_a_delivery_modal`, `respects_an_existing_choice`, `never_raises_on_a_broken_page`) |
| delivery-modal filter vs filter panels | 1 (`delivery_modal_filter_rejects_filter_panels`) |
| helpers still wired into the cycle | 1 (`recovery_helpers_are_still_wired_into_the_cycle`) |

The plan stayed `pending` only because the SUMMARY was never written — the work
was in place since phase 95 execution.

## Mutation check (the "fails if recovery is removed" criterion)

Rather than assume, each claim was tested by breaking the recovery on purpose:

| mutation | result |
|---|---|
| `_safe_js`: `for attempt in range(3)` → `range(1)` | **2 failed**, 8 passed |
| `_reacquire_page`: `for attempt in range(3)` → `range(1)` | **1 failed**, 9 passed |
| both reverted | **10 passed** |

So the harness is not a smoke test: it genuinely fails when the retry/recovery
loop is removed. The two delivery-stage assertions are structural (they assert
zero clicks and a `no_slot_found` return), which the mutation table does not
cover — stated plainly rather than claimed as verified.

## Acceptance

- [x] each stage has a test that fails if its recovery is removed (verified for
      `_safe_js` and `_reacquire_page` by mutation; delivery stages asserted
      structurally)
- [x] no test needs a real Chrome or network — 10.2 s, plain venv
- [x] suite runs without `python-telegram-bot`
