# Phase 81 — Integration Test Coverage — Verification

**Milestone:** v1.25 Operator Visibility + Test Coverage
**Requirements:** QA-06, QA-07, QA-08
**Date:** 2026-05-13

## Goal Recap

Pin the 3 integration scenarios the v1.24 verifier flagged as HIGH priority — especially the 2026-05-13 collapse pattern that caused the 69-min 00:04→01:13 outage. The REL-19 bug fixed tonight (`b65cde7`) proves these tests are non-optional: without them, the bug lived in the code for 6 hours between ship and production failure.

## Evidence

### QA-06 — Collapse replay (`tests/test_collapse_replay.py`)

**5/5 tests green locally + on EC2 Linux.**

Tests pin the full 2026-05-13 pattern:

1. `test_collapse_replay_setup_healthy_pool` — baseline 20 nodes.
2. `test_collapse_replay_event1_catastrophic_drop_to_zero` — pool drops to 0 in one cycle.
3. `test_collapse_replay_event2_dead_cycles_trigger_recovery_attempts` — **THE BUG FIX INVARIANT**: 5 consecutive dead cycles must produce 5 `ensure_pool()` calls. Pre-hotfix (commit before `b65cde7`) would fail with 0 calls. This test is the sanity check against REL-19 regressing.
4. `test_collapse_replay_event3_recovery_resets_state` — pool recovers → counter resets → `scheduler_pool_recovered` event emitted.
5. `test_collapse_replay_full_cycle_end_to_end` — healthy → drop → 5 failed refreshes → recovery → resume. Full tonight's 00:04→01:17 arc.

### QA-07 — File I/O race (`tests/test_pool_state_io_race.py`)

**2/3 tests pass locally (Windows), 3/3 pass on EC2 Linux.**

- `test_concurrent_read_write_never_observes_partial_state` — 200-iteration writer + reader threads pounding `vless_pool.json`. Reader never observes `JSONDecodeError` or transient empty state. Platform-skipped on Windows (known `os.replace` limitation with open handles — same class as baseline `tests/test_vless_xray.py::test_write_config_is_atomic` Windows failure). **Passes on Linux/EC2 where production runs.**
- `test_is_pool_dead_handles_missing_file_gracefully` — pre-first-write scenario returns True (dead).
- `test_is_pool_dead_handles_corrupt_json_gracefully` — truncated write scenario returns True (safer default).

### QA-08 — staleAll + empty products edge (`backend/test_stale_empty_edge.py`)

**2/2 tests green.** Documents current behavior:

1. `test_fresh_deploy_empty_products_returns_dataStale_false` — fresh mtime + empty products → `dataStale=false`, no `staleAll`. Pinned.
2. `test_fresh_deploy_partial_sources_still_no_staleAll` — 1 of 3 stale → v1.22 phantom-strip works, no staleAll. Pinned.

**Known gap documented, not fixed here** — UI shows "В этой категории пока нет товаров" for a fresh-deploy scenario when it should say "scheduler has not yet produced data". Deferred to v1.26 as it requires a new diagnostic field + UI copy change, out of Phase 81's pin-only scope.

### Full regression

`backend/ + tests/` (Windows, 3 baseline failures unchanged):
- **412 passed, 3 skipped, 3 failed (baseline Windows-only)** — no new regressions.
- v1.24 Phase 77 quarantine + v1.24 Phase 78 stale-filter + v1.25 Phase 80 admin-alerts all still green.

On EC2 Linux: Phase 81 suite **10/10 passes** including the race test.

## Key finding — REL-19 regression prevention

Before this phase, the REL-19 bug (scheduler graceful-degrade skipping recovery too) had no test to catch it. The `test_collapse_replay_event2_dead_cycles_trigger_recovery_attempts` + `test_collapse_replay_full_cycle_end_to_end` tests now pin the invariant. If someone reverts my `b65cde7` hotfix or introduces a similar skip-too-aggressive pattern, CI fails immediately.

## Success Criteria Checklist

- [x] **1.** `test_collapse_replay.py` — 5 tests covering setup → probe-fail → dead cycles → recovery. All green.
- [x] **2.** `test_pool_state_io_race.py` — concurrency test with 200 iterations each thread. Passes on Linux (platform-skipped on Windows per known os.replace limitation).
- [x] **3.** `test_stale_empty_edge.py` — 2 tests pinning fresh-deploy + partial-stale edge cases.
- [x] **4.** All new tests pass in isolation + in full backend/tests suite. 412 passed, no new regressions.
- [x] **5.** v1.24 + earlier regression green.

## Commits

| Commit | Scope | Description |
|---|---|---|
| `6391bed` | 81 | test(v1.25): QA-06/07/08 integration tests — 2026-05-13 collapse replay + pool IO race + empty-source edge |

Single commit — Phase 81 is 3 test files in a tightly-coupled scope (v1.24 invariants) and no production code changes.

## Outcome

**Phase 81 ships.** The 2026-05-13 REL-19 regression that caused tonight's 69-min outage can't silently re-ship. Pool-state atomicity is pinned on production platform. Fresh-deploy empty-state edge is documented for v1.26.
