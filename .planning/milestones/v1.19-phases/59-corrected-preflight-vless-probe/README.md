# Phase 59: Corrected Pre-flight VLESS Probe

**Milestone:** v1.19 Production Reliability & 24/7 Uptime
**Requirements addressed:** REL-01, REL-02, REL-03, REL-04, REL-05 + first concrete instance of OPS-06/07/08
**Status:** Planned — ready to execute via `/gsd-execute-phase 59`
**Depends on:** Phase 58 (v1.18) shipped state (VLESS bridge operational)
**Planned:** 2026-05-03

## One-line summary

When the VLESS bridge times out, try the next node — with the timeout set above the empirically-measured healthy latency (12 s, not PR #25's 5 s) and with at most 2 rotations per scraper launch so we never cascade into 5 xray restarts (the PR #25 failure mode that was reverted by PR #26 in 8 minutes).

## User's stated intent (2026-05-03)

> "i wanna robust solution where if vless time out just change it to next one"

This phase delivers exactly that, done the safe way:
- Probe first (don't waste 30-45 s on Chrome startup only to fail at page load)
- Timeout above empirical p95 (healthy VLESS nodes respond in 7-9 s through the bridge)
- Cap rotations at 2 (no cascade of xray restarts)
- Prefer the `leastPing` balancer's decision over Python-side node removal
- Cache successful probe results so back-to-back scraper launches don't re-probe

## Plans

- **`59-01-PLAN.md`** — Implementation: `vless/preflight.py` module + `scheduler_service.py::_run_scraper_set` integration
- **`59-02-PLAN.md`** — Tests: regression guard for the 12 s timeout floor, rotation cap enforcement, probe behavior contract
- **`59-03-PLAN.md`** — Verification + deploy: `scripts/verify_v1.19.sh` skeleton, EC2 smoke test, Vercel miniapp cart-add regression check, rehearsed rollback

## Success Criteria (from ROADMAP.md Phase 59)

1. [ ] `vless/preflight.py::probe_bridge_alive(timeout=12)` exists, returns a typed `ProbeResult`, called from `scheduler_service.py::_run_scraper_set`
2. [ ] 12 s timeout guarded by `tests/test_preflight_timeout_regression.py` — fails if anyone lowers the constant
3. [ ] Rotation cap = 2 verified by integration test (asserts ≤ 2 `_remove_host_and_restart` calls per launch)
4. [ ] Live verification on EC2: bad single proxy → one rotation + recovery ≤ 30 s (not 5 cascading xray restarts)
5. [ ] `scripts/verify_v1.19.sh` exists, runs from local terminal via SSH, idempotent, reports pass/fail
6. [ ] Vercel miniapp `/api/cart/add` still returns HTTP 200 `success=true` (no v1.18 regression)

## Non-goals (out of scope for Phase 59)

- Circuit breaker changes — that's Phase 60
- Observatory probeURL change — that's Phase 60
- Deep health endpoint — that's Phase 61
- Pool drain/replenish fixes — Phase 61 (REL-11, REL-12)
- Telegram alerting on breaker state — deferred to v1.20 (REL-FUT-05)
- Any miniapp / React changes — v1.20

## Risk register

| Risk | Mitigation |
|---|---|
| Probe hits a VkusVill edge that's blocked while other edges work | Accept: probe is a heuristic for "this exit works for our target", not truth. If probe succeeds but real traffic fails, the existing per-scraper retry path in `_run_scraper_set` still handles it. |
| 12 s probe adds 12 s to first scraper launch per cycle | Accept: first launch. REL-05 cache (30 s) means subsequent launches in same cycle skip. Net: +12 s per 5-min cycle = 4% overhead in exchange for catching silent degradation. |
| Cap 2 rotations leaves scraper running through bad bridge if both probes fail | Correct: don't pretend to fix it. Log, let Phase 60's circuit breaker decide to stop the cycle. Better than 5 cascading restarts. |
| Module-level constant for 12 s drifts over time as bridge changes | Regression test guards it + comment in code cites measurement date + evidence. Future tuners must re-measure + update both. |

## Rollback procedure (rehearsed per OPS-08)

The only production-facing change is `scheduler_service.py::_run_scraper_set` calling new code. Rollback is a single git revert:

```bash
ssh scraper-ec2 "cd /home/ubuntu/saleapp && git revert HEAD --no-edit && sudo systemctl restart saleapp-scheduler"
```

`vless/preflight.py` is new, so reverting removes it cleanly. No migrations, no state-file changes, no config rebuilds. Pre-merge rehearsal in `59-03-PLAN.md` step 4 proves it works on a branch.
