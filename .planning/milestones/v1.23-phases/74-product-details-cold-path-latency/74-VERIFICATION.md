# Phase 74 — Product Details Cold-Path Latency — Verification

**Milestone:** v1.23 Detail-Path Performance + UX Polish
**Requirements:** PERF-10, PERF-11
**Date:** 2026-05-13
**Environment:** EC2 `ubuntu@13.60.174.46` + Vercel `https://vkusvillsale.vercel.app/`

## Goal Recap

Drop `GET /api/product/{id}/details` cold-path p95 from ~16 s (v1.22 baseline) to ≤ 2 s by removing the pre-v1.15 SOCKS5-era HEAD-probe loop in `backend/main.py::product_details`, tightening httpx timeouts, and emitting a `data/detail_events.jsonl` ledger.

## Evidence

### PERF-10: cold-path p95 ≤ 2 s

**Before (v1.22 baseline, live MCP 2026-05-13)** — first card tap: ~16 s (cache miss triggered 4s HEAD probe + up to 3×10s fetch retries).

**After (v1.23 Phase 74, measured on EC2 with fresh `data/detail_cache.json`):**

5 never-cached product IDs (109880, 111081, 109621, 110579, 116538). Each cleared from cache then hit `http://127.0.0.1:8000/api/product/{id}/details` directly:

| product_id | curl time_total | duration_ms (ledger) |
|---:|---:|---:|
| 109880 | 0.607s | 603 ms |
| 111081 | 0.678s | 669 ms |
| 109621 | 0.638s | 634 ms |
| 110579 | 0.627s | 623 ms |
| 116538 | 0.637s | 631 ms |

**p50: 0.637s · p95: 0.678s · max: 0.678s** — **~25× faster than baseline**. Well under the 2 s PERF-10 budget.

All 5 ledger entries carry `"cached": false`, `"outcome": "ok"`, `"retry_count": 1` — confirming these are real cold-path fetches (not cache hits or fallbacks).

### PERF-11: `data/detail_events.jsonl` ledger

Ledger entries from the cold-path smoke run:

```json
{"ts":1778542692.524,"product_id":"109880","duration_ms":603,"cached":false,"retry_count":1,"outcome":"ok"}
{"ts":1778542693.207,"product_id":"111081","duration_ms":669,"cached":false,"retry_count":1,"outcome":"ok"}
{"ts":1778542693.863,"product_id":"109621","duration_ms":634,"cached":false,"retry_count":1,"outcome":"ok"}
{"ts":1778542694.5,"product_id":"110579","duration_ms":623,"cached":false,"retry_count":1,"outcome":"ok"}
{"ts":1778542695.145,"product_id":"116538","duration_ms":631,"cached":false,"retry_count":1,"outcome":"ok"}
```

**Schema spot-check:** every line has exactly the 6 keys `{ts, product_id, duration_ms, cached, retry_count, outcome}`. Timestamps in Unix epoch seconds. `duration_ms` as int. `cached` as bool. `outcome` ∈ `{cached, ok, fallback, failed}`.

Cache-hit outcomes also emit correctly — additional ledger entry from the cached-path run showed `{"outcome":"cached", "cached":true, "retry_count":0}`.

### Unit tests

`backend/test_product_details_latency.py` — **6/6 passed on EC2** (runs `python3 -m pytest backend/test_product_details_latency.py`):

- `test_cached_path_emits_cached_outcome` ✓
- `test_happy_fetch_emits_ok_outcome` ✓
- `test_all_retries_fail_emits_failed_outcome` ✓ (3 retries, outcome=failed)
- `test_short_html_emits_fallback_outcome` ✓
- `test_non_200_then_success_tracks_retry_count` ✓ (502 then 200 → retry_count=2)
- `test_ledger_schema_has_all_six_keys` ✓

`backend/test_product_details_fallback.py` — **2/2 passed** (was broken pre-v1.23; fixed as part of Plan 74.02 to mock `httpx.AsyncClient` instead of the dead `requests.get` from pre-v1.15).

### Cross-version regression (OPS-20)

All v1.22 critical checks green on EC2 post-deploy:

```
70-A: _load_current_sale_types importable:        OK
70-B: test_history_search_catalog_wide.py:        5 passed
71-B: legacy 'Данные устарели' removed:           OK
72-A/B: admin.html badges present:                2 (bug-reports + xray-drift)
73: priority frontmatter on pending todos:        4/4
Full backend suite:                               110 passed
```

The full backend suite includes all v1.10-v1.22 regression coverage (cart add, idempotency, catalog discovery, history search, scheduler freshness, cart obs, cart pending contract, etc.). Clean run on EC2.

### Implementation diff summary

**`backend/main.py`**
- Removed: ~60 LOC two-phase probe loop (`Phase 1: HEAD check` + `Phase 2: fetch`, per-proxy dead-proxy removal, `pool = pm._cache.get("proxies", [])` iteration).
- Added: ~35 LOC single-path fetch loop with 3 retries through the xray bridge at `socks5://127.0.0.1:10808`.
- Timeouts: `connect 4s→1s, read 6s→3s, write 3s→1s, pool 3s→1s`.
- Module-level constants: `_DETAIL_BRIDGE_PROXY`, `_DETAIL_MAX_RETRIES` (for monkey-patching in tests).
- Logging tag: `[DETAIL-PROXY]` → `[DETAIL-FETCH]` (accurate post-v1.15).
- Wired ledger writes on all 4 terminal branches (cached, ok, fallback, failed).

**`backend/detail_events.py`** (new)
- `append_event()` with 6-key schema, bounded to `MAX_LINES=5000` / `PRUNE_KEEP=4000`.
- `read_recent(limit)` for admin/tests.
- `LEDGER_PATH` honors `SALEAPP_DETAIL_EVENTS_PATH` env var for test isolation.
- All I/O failures swallowed at DEBUG log level — ledger must never crash the endpoint.

**`backend/test_product_details_latency.py`** (new, force-added — `backend/test_*.py` is gitignored)
- `_FakeAsyncClient` stub for `httpx.AsyncClient` — no external deps like `respx`.
- Per-test `tmp_ledger` fixture via `monkeypatch.setattr(detail_events, "LEDGER_PATH", ...)` so tests don't leak into `data/`.

**`backend/test_product_details_fallback.py`** (rewritten)
- Replaced the dead `requests.get` mock (broken since Phase 56 v1.15) with `_AlwaysTimeoutClient` stub matching the new httpx-async architecture.
- Updated to assert the new 3-retry budget (`_AlwaysTimeoutClient.calls["count"] == 3`).

**`scripts/verify_v1.23.sh`** (new, chmod +x in git index)
- Phase 74 smoke: 7 checks (probe removal + timeouts + module import + unit test green + p95 ≤ 2.5s + ledger exists + schema valid).
- Cross-version regression: chains `verify_v1.22.sh all` at the end.
- Phase 75/76 placeholders grow when their phases ship.

## Success Criteria Checklist

- [x] **1.** `backend/main.py::product_details` no longer executes the per-proxy HEAD probe loop. Single code path: check cache → fetch via xray bridge → retry up to 3 times.
- [x] **2.** httpx.Timeout tightened: connect 4.0 → 1.0, read 6.0 → 3.0. Retry loop preserves at 3.
- [x] **3.** New `data/detail_events.jsonl` ledger: one line per request with all 6 keys present and correct. Bounded file.
- [x] **4.** Unit test `backend/test_product_details_latency.py` covers happy / cached / failed / fallback / non-200-then-success / schema spot-check — 6/6 green.
- [x] **5.** Live cold-path: 5 never-cached product_ids via curl, **p95 = 0.678 s** (budget ≤ 2 s).
- [x] **6.** v1.22 + v1.21 + v1.20 + v1.19 regression green on EC2 (backend suite 110/110, v1.22 critical checks all green).

## NEEDS_OPERATOR

- **Live MCP screenshot of filled drawer** — not captured this session (tests + direct curl provide equivalent evidence: HTTP 200, real HTML parsed into all fields, `outcome=ok` in ledger). If the user wants a visual trace via Chrome DevTools MCP, I can open the MiniApp in the shared port-9222 Chrome and record a Performance trace around a card tap. Flagged but not blocking — PERF-10 is proven at the backend layer with measurable before-after delta.
- **Lighthouse cold-path synthetic** — skipping in favor of actual-usage curl timings. Lighthouse on `/api/product/…` is not meaningful (it's an API, not a page).

## Commits

| Commit | Scope | Description |
|---|---|---|
| `14fb185` | 74.01 | perf(backend): remove legacy HEAD probe from product_details cold path |
| `6331cc4` | 74.02 | feat(backend): add detail_events.jsonl ledger for product_details timing |
| (next) | 74.03 | test(v1.23): verify_v1.23.sh + 74-VERIFICATION.md |

## Rollback

Revert commits in reverse order:
```
git revert 6331cc4  # remove ledger (restores product_details shape minus ledger calls)
git revert 14fb185  # restore pre-74 two-phase probe (if needed)
git push origin main
```

Each commit is atomic; reverting only 6331cc4 keeps the probe removal + faster timeouts without the ledger.

## Outcome

**PERF-10 green · PERF-11 green · 25× latency improvement measured · no cross-version regression.** Phase 74 ships.
