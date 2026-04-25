# Phase 58 — Geo Resolver & Scraper Recovery

**Status**: SHIPPED 2026-04-25
**Milestone**: v1.18
**Predecessor**: Phase 57 (VLESS Timeout Hardening, v1.17)
**Triggered by**: user request "can u finish all phases" — closes the two
known issues punted from `57-VERIFICATION.md`.

## Goals

1. **Stop ipinfo.io 429s capping pool admission.** v1.17 refresh saw
   ~70% HTTP 429 rate-limits because we relied on a single geo provider.
   Real RU-exit nodes were silently rejected with `rejected_reason=429`.
2. **Stop scraper crashes from Chromium CDP-WebSocket HTTP 500 errors
   mid-cycle.** `scrape_green.py` died deterministically at "Step 2.9:
   Clearing unavailable items..." right after a force-reload — Chromium
   had swapped the underlying CDP target while we still held the old
   `page` handle.

## Non-goals

- No new sources, no new probe URLs for VkusVill itself.
- No restructuring of `_probe_one` or the refresh pipeline beyond
  swapping the geo provider call.
- No nodriver upgrade — the WS-500 recovery is implemented at the call
  sites, not by changing the underlying browser-control library.

## Sub-plans

| ID | Scope | PR | Commit |
|---|---|---|---|
| 58-01 | Multi-provider geo resolver (`vless/xray.py::verify_egress` + `vless/manager.py::_probe_one` call site) + 5 unit tests | [#17](https://github.com/trikiman/sale-app/pull/17) | `acf8929` |
| 58-02 | Scraper CDP-WS recovery helpers in `scrape_green.py` + 10 unit tests | [#18](https://github.com/trikiman/sale-app/pull/18) | `f616af9` |
| 58-03 | `scripts/deploy_v1_18.sh` + `scripts/verify_v1_18.sh` + this docs bundle + ROADMAP update | #19 | TBD |

## Success criteria

1. Pool size after refresh on EC2 ≥ 15 (the v1.17 baseline). **Achieved: 25 nodes (+67%)**.
2. `XrayProcess._GEO_PROVIDERS` exposes all three providers; live `verify_egress` returns `RU` through the chain. **Achieved**.
3. `scrape_green` exposes all four recovery helpers as module-level callables. **Achieved**.
4. Vercel miniapp `/api/cart/add` still returns HTTP 200 with `success=true` (no regression on the v1.17 fix). **Achieved: `cart_items=3, cart_total=971.6`**.
5. All existing tests still pass; new tests cover the helpers. **Achieved: 96 → 111 in `tests/`, 86/86 backend, 2 skipped (live-only) unchanged**.

## Risks & mitigations

- **ipapi.co or ip-api.com unreachable from EC2.** Mitigation: the chain
  is order-preserving and returns the *last* provider's error if every
  provider fails, so operators can diagnose. Fallthrough is safe — we
  never become more permissive than v1.17.
- **`browser.tabs` may surface closed-but-not-removed tabs.** Mitigation:
  `_refresh_page_handle` probes each candidate with `await tab.evaluate("1")`
  before returning it, skipping any tab that raises.
- **`_navigate_and_settle` always sleeps before probing.** Mitigation: the
  4 call sites already had explicit `asyncio.sleep` calls of identical
  duration, so the helper is behavior-preserving on the happy path.

## References

- `.planning/phases/57-vless-timeout-hardening/57-VERIFICATION.md` —
  source of the "Known issues" list this phase closes.
- `.planning/phases/57-vless-timeout-hardening/57-SUMMARY.md` — phase 57
  closure that punted these two items.
