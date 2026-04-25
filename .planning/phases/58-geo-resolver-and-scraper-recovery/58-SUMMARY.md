# Phase 58 — Summary (CLOSED 2026-04-25)

## Outcome

v1.18 shipped end-to-end, both punted-from-v1.17 issues closed.

## What changed

- `vless/xray.py::XrayProcess` — added `_GEO_PROVIDERS` class tuple + reworked
  `verify_egress` to iterate the chain. Legacy `url=` kwarg path preserved
  for live integration tests.
- `vless/manager.py::_probe_one` — dropped the explicit
  `url="https://ipinfo.io/json"` kwarg so refresh probes use the chain.
- `scrape_green.py` — added 4 helpers (`_is_dead_ws_error`,
  `_refresh_page_handle`, `_safe_js`, `_navigate_and_settle`); replaced
  the 4 `browser.get(url) + asyncio.sleep` pairs that wrapped force-reloads;
  switched the historical crash site (Step 2.9 cart cleanup) to `_safe_js`.
- `tests/test_vless_xray.py` — 5 new tests covering provider success,
  fallback on 429, deep-fallback to provider 3, all-fail returns last
  error, legacy-`url=` single-provider mode.
- `tests/test_scrape_green_ws_recovery.py` (new file) — 10 tests covering
  error classification, tab re-acquisition, retry semantics,
  `_navigate_and_settle` with both healthy and dead post-nav handles.
- `scripts/deploy_v1_18.sh`, `scripts/verify_v1_18.sh` — minimal 5-step
  flows; no new systemd units, no new dependencies.
- `.planning/ROADMAP.md` — added v1.18 entry + section.

## What did NOT change

- No xray binary or installer changes.
- No systemd unit changes.
- No changes to `vless/parser.py`, `vless/sources.py`, `vless/pool_state.py`,
  `vless/config_gen.py`, `cart/vkusvill_api.py`, `backend/main.py`.
- The 5 pre-existing `ruff` f-string warnings in `scrape_green.py`
  (lines 2075-2076) were left alone — out of scope.

## Numbers

| Metric | v1.17 | v1.18 |
|---|---|---|
| Pool admitted after refresh | 15 | **25** |
| Active outbounds in `active.json` | 16 | 27 |
| Geo providers in chain | 1 | 3 |
| Scraper recovery helpers | 0 | 4 |
| Tests in `tests/` | 96 | **111** |
| Tests in `backend/` | 86 | 86 |
| Vercel miniapp `/api/cart/add` | HTTP 200 | HTTP 200 |

## Phase close-out

- All sub-plans complete: 58-01 (PR #17), 58-02 (PR #18), 58-03 (PR #19).
- All success criteria from `README.md` met.
- No items punted to phase 59.
