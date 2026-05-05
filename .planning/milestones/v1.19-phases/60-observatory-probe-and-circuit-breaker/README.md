# Phase 60 — Observatory probeURL + Graduated Circuit Breaker

**Milestone:** v1.19 Production Reliability & 24/7 Uptime
**Status:** Planned — executing autonomously after Phase 59 ship
**Depends on:** Phase 59 (smoke script foundation)
**Requirements:** REL-06, REL-07, REL-08, REL-09, REL-10 + continued OPS-06/07/08

## User intent (verbatim)

> "if vless time out just change it to next one" (continuing from Phase 59) plus "robust solution" (not the current 162-re-trips counter).

## What Phase 60 does

Two distinct fixes composed in one phase because they're symptoms of the same root cause — the scheduler has no real feedback loop from the bridge health back to its own pacing:

1. **Observatory probeURL alignment (REL-06)** — xray's `leastPing` balancer currently ranks outbounds by ping time to `google.com/generate_204`, which has nothing to do with reachability to VkusVill. A node that's blocked by VkusVill's WAF but otherwise fast still wins the leastPing race. Phase 60 changes `probeURL` in `@/Users/ProsalovP/Desktop/projects/sale-app/vless/config_gen.py:154` to `https://vkusvill.ru/favicon.ico` so the balancer ranks by real-target reachability, matching what Phase 59's preflight probe checks.

2. **Graduated circuit breaker (REL-07..10)** — replace the current naïve counter (`consecutive_fails >= 3 → wait 120s`) in `@/Users/ProsalovP/Desktop/projects/sale-app/scheduler_service.py:663-677` with a proper 3-state machine:
   - `closed` (normal): scrapers run every 5 min
   - `open` (tripped): wait `cooldown_s`, then transition to `half_open`; `cooldown_s` starts at 120 s and doubles on every re-trip up to 30 min cap
   - `half_open` (probing): run GREEN only; success → `closed` (cooldown resets to 120 s); failure → `open` (cooldown doubles)
   
   State persisted in `@/Users/ProsalovP/Desktop/projects/sale-app/data/scheduler_state.json` across restart, with corrupt-file fallback to a fresh closed breaker. Counter resets on **any** scraper success (REL-09), not just all-clean cycles, so intermittent YELLOW failure doesn't mask the RED/GREEN successes that prove the stack works.

## Scope boundary (what Phase 60 does NOT do)

- No deep-health HTTP endpoint (that's Phase 61).
- No pool_snapshot() method (Phase 61).
- No proxy_events.jsonl extension (Phase 61).
- No change to `vless/preflight.py` from Phase 59 (already shipping; circuit breaker consumes its results via `consecutive_fails`, no direct coupling).
- No change to `VlessProxyManager` cooldown internals (4 h stays).

## Files touched

| File | Change |
|---|---|
| `@/Users/ProsalovP/Desktop/projects/sale-app/vless/config_gen.py` | probeURL: google → vkusvill/favicon.ico; probeInterval: 5m → 60s (REL-06) |
| `@/Users/ProsalovP/Desktop/projects/sale-app/scheduler_service.py` | Replace `consecutive_fails` breaker with `BreakerState` class + `_load/_persist_breaker_state()` |
| `@/Users/ProsalovP/Desktop/projects/sale-app/data/scheduler_state.json` | NEW (created on first successful persist; gitignored content not committed) |
| `@/Users/ProsalovP/Desktop/projects/sale-app/tests/test_xray_probe_url_regression.py` | NEW — asserts probeURL references vkusvill.ru not google.com |
| `@/Users/ProsalovP/Desktop/projects/sale-app/tests/test_circuit_breaker_state_machine.py` | NEW — transitions, backoff, persistence, corrupt-file fallback |
| `@/Users/ProsalovP/Desktop/projects/sale-app/scripts/verify_v1.19.sh` | Append Phase 60 checks (60-A..60-G) |
| `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/phases/60-observatory-probe-and-circuit-breaker/60-VERIFICATION.md` | NEW — per-phase verification record |
| `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/STATE.md` | Progress update |

## Risk register

| Risk | Mitigation |
|---|---|
| probeURL change to VkusVill could trigger WAF rate-limit on xray probes | Use `favicon.ico` (cached on CDN); probeInterval stays ≥ 60 s; accept 4xx statuses as healthy in xray (only 5xx / connect-fail demotes node). xray's leastPing ignores HTTP status and ranks by TCP/TLS handshake time, so CDN status doesn't affect the ranking — confirmed in xray-core docs. |
| scheduler_state.json corruption or filesystem-full could crash the scheduler | Corrupt-file fallback resets to fresh `closed` breaker with default cooldown; write is atomic via `os.replace` (tmp file + rename); write failure is logged but non-fatal (state stays in-memory). |
| Breaker stuck in `open` forever if `time.monotonic()` rolls back or system clock adjusts | Breaker uses `time.time()` for persistence (wall clock) and recomputes cooldown remaining on each tick; long-jump clock adjustments auto-resolve within one cycle. |
| Splitting all-failed vs any-failed resets could hide real cycle failures | Emit a structured log line on every reset with the reason (`"breaker reset: GREEN succeeded"`) so degradation is still visible in the journal; Phase 61's `/api/health/deep` will expose breaker state to monitoring. |

## Rollback

```bash
# Revert both commits:
ssh scraper-ec2 "cd /home/ubuntu/saleapp && git revert HEAD --no-edit && sudo systemctl restart saleapp-scheduler && sudo systemctl restart saleapp-xray"
```

Then re-run xray with the old config (restart re-reads the config). Breaker resets cleanly: on revert, the old simple counter is back in memory; the `scheduler_state.json` file lingers but is ignored by the old code. No data loss.

**Full rehearsal** during 60-03 verification.

## Plans

- `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/phases/60-observatory-probe-and-circuit-breaker/60-01-PLAN.md` — Implementation (probeURL + breaker state machine + persistence)
- `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/phases/60-observatory-probe-and-circuit-breaker/60-02-PLAN.md` — Tests (2 new test files, ~15 tests)
- `@/Users/ProsalovP/Desktop/projects/sale-app/.planning/phases/60-observatory-probe-and-circuit-breaker/60-03-PLAN.md` — Verify + deploy + live transition rehearsal + smoke script extension
