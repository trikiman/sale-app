# Phase 81 — Integration Test Coverage
**Milestone:** v1.25 Operator Visibility + Test Coverage
**Requirements:** QA-06, QA-07, QA-08
**Started:** 2026-05-13

## Goal

Add the integration tests the v1.24 verifier flagged as HIGH priority. The tests must pin the behaviors that matter in production — not just unit-level invariants — so the next pool outage pattern can't regress silently like REL-19 did on 2026-05-13.

## Why now

The v1.24 verifier flagged three gaps:

1. **QA-06 — "The exact 2026-05-13 collapse pattern is not replayed in any test."** Pool 20→0 in one cycle, 231 RU-filtered nodes all failing probes, scheduler skipping for 20+ min. The REL-19 hotfix I shipped 40 min ago (commit `b65cde7`) proves this gap was real — the bug lived in the code for ~6 hours because no test exercised the "pool stays dead across many cycles" path.

2. **QA-07 — scheduler/manager race on `vless_pool.json`.** `_is_pool_dead()` reads the file; `refresh_proxy_list()` writes it. `os.replace` atomicity makes the race window vanishingly small, but we should pin the invariant.

3. **QA-08 — `staleAll=true + products=[]` edge case.** Fresh deploy writes empty source files with current mtime → `isStale=false` → `staleAll=false` → user sees empty grid. Not a regression from v1.24, but identified by the verifier as the existing edge case that could surprise a fresh deploy.

## Scope

### QA-06: Collapse replay (`tests/test_collapse_replay.py`)

Simulate the 2026-05-13 pattern with mocks so no network is touched:

- **Setup**: Pool at 20 nodes. `proposals.json` has 174 products (16/35/123). All 3 source files fresh.
- **Event 1 — Catastrophic probe failure**: Trigger a refresh where `_probe_candidates_in_parallel` returns 0 (all 231 candidates fail). Assert:
  - All 231 candidates end up in `quarantine` ledger
  - Pool size drops to 0
  - `scheduler_pool_dead` event fires (after 2nd consecutive dead cycle)
- **Event 2 — Failed recovery loop**: Run 3 more dead cycles. Each must trigger `ensure_pool()` (the exact invariant the REL-19 hotfix introduced). Probe still fails, pool stays at 0.
- **Event 3 — Recovery**: On cycle 5, `_probe_candidates_in_parallel` succeeds for 10 nodes. Assert:
  - Pool recovers to 10
  - `scheduler_pool_recovered` event fires
  - `consecutive_pool_dead_cycles` counter resets
  - Next scrape cycle proceeds normally (no longer skipped)
- **Throughout**: `/api/products` always returns cached products + `staleAll=true` block (verified by direct endpoint call via TestClient).

### QA-07: Scheduler/manager file race (`tests/test_pool_state_io_race.py`)

Concurrent writer + reader threads against `vless_pool.json`:

- Writer thread: 100 iterations of `pool_state.save()` with varying node counts
- Reader thread: 100 iterations of `scheduler_service._is_pool_dead()`
- Assert: reader never observes a partially-written file (no `json.JSONDecodeError`, no transient empty state during a write of 10+ nodes)
- Relies on `os.replace` atomicity — test pins the invariant

### QA-08: staleAll + empty products edge case (`backend/test_stale_empty_edge.py`)

New-deploy scenario: source files exist with current mtime but zero products:

- **Setup**: `proposals.json` has `products: []`, all 3 source files exist with mtime=now
- `_build_source_freshness` returns `isStale=false` for all (because mtime is fresh)
- `staleAll` is absent (because not all stale)
- **Assert current behavior**: `/api/products` returns `products: []` + `dataStale: false`. This is the documented gap the v1.24 verifier called out.
- **Document as known issue**: UI shows empty-state message ("В этой категории пока нет товаров"). Not a regression, existed pre-v1.24.
- **Optional improvement** (if trivial): When `products=[]` AND source files are fresh AND there's a `greenMissing` or `greenLiveCount: 0` signal, the endpoint could add a diagnostic field like `"emptyReason": "scheduler_not_yet_produced_data"`. But that's mission creep — keep this test as a pin only, defer UI message improvement to v1.26.

## Non-Goals

- No live EC2 integration — these are pure unit-style integration tests using mocks + TestClient
- No new production code changes — all behavior tested was shipped in v1.24 + tonight's hotfix
- No performance benchmarks — tests assert correctness only, not speed

## Files Touched

| File | Change |
|---|---|
| `tests/test_collapse_replay.py` (new) | QA-06 — full 2026-05-13 collapse → recovery replay |
| `tests/test_pool_state_io_race.py` (new) | QA-07 — atomic-write race invariant |
| `backend/test_stale_empty_edge.py` (new, force-add) | QA-08 — empty-products fresh-deploy edge |
| `scripts/verify_v1.25.sh` | Phase 81 smoke — run all 3 new test files |

## Plan Order

Single atomic commit — Phase 81 is 3 tests in 3 files, tightly coupled to v1.24 invariants. Split-by-plan would be ceremony.

## Success Criteria

1. [ ] `test_collapse_replay.py` — 5+ tests covering setup → probe-fail → dead cycles → recovery. All green.
2. [ ] `test_pool_state_io_race.py` — concurrency test with ≥100 iterations each thread. Never observes partial-write state.
3. [ ] `test_stale_empty_edge.py` — 2 tests pinning current behavior (dataStale=false when sources fresh, products=[]).
4. [ ] All new tests pass in isolation + in full backend/tests suite (no cross-contamination).
5. [ ] v1.24 + earlier regression green — `backend/ + tests/test_vless_quarantine.py` counts grow; no prior test fails.
