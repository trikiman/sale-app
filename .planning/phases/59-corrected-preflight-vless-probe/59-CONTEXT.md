# Phase 59: Corrected Pre-flight VLESS Probe — Context

**Gathered:** 2026-05-03
**Status:** Ready for planning
**Source:** Direct plan (user explicitly skipped `/gsd-discuss-phase`; intent captured verbatim below)
**Predecessor:** Phase 58 (v1.18) shipped state + PR #25 / PR #26 post-mortem

## User's stated intent (verbatim, 2026-05-03)

> "i wanna robust solution where if vless time out just change it to next one"

That one sentence is the entire phase scope. Everything below is the safe + robust implementation of it, grounded in the PR #25 revert evidence.

<domain>
## Phase Boundary

Add a lightweight pre-flight probe that checks whether the VLESS bridge (`socks5h://127.0.0.1:10808`) can actually reach VkusVill before the scheduler spends 30-45 s launching a Chrome browser. If the probe fails, rotate at most 2 times (one via balancer-preferred path, one via Python-side node removal fallback). If still failing, stop probing and let the cycle continue — Phase 60's circuit breaker will catch the all-failed outcome.

**In scope:**
- New `vless/preflight.py` module with `probe_bridge_alive(timeout=12) -> ProbeResult`
- Narrow edit to `scheduler_service.py::_run_scraper_set` (line 406 area) adding pre-flight call
- Regression tests for the 12 s timeout floor + rotation cap + probe behavior
- `scripts/verify_v1.19.sh` skeleton (OPS-07 cross-cutting)
- 59-VERIFICATION.md per-phase doc (OPS-06 cross-cutting)
- Rehearsed rollback path (OPS-08 cross-cutting)

**Out of scope:**
- Circuit breaker changes — Phase 60 (REL-07..10)
- Observatory probeURL change — Phase 60 (REL-06)
- Deep health endpoint — Phase 61 (OBS-01..03)
- Pool drain/replenish fixes — Phase 61 (REL-11, REL-12)
- Any miniapp / React changes — deferred to v1.20
- Refactoring `_prepare_proxy_connectivity`, `_kill_all_scraper_chrome`, or other scheduler helpers
- Touching `vless/manager.py` internals, `vless/xray.py`, `vless/parser.py`, `vless/pool_state.py`
- Changing the existing `pm.next_proxy()` retry inside the per-scraper loop (keep as fallback layer)

</domain>

<decisions>
## Implementation Decisions

### Probe behavior (addresses REL-01, REL-02, REL-05)
- **D-01:** Probe target is `https://vkusvill.ru/favicon.ico` — same domain as real traffic (not `google.com`), lightweight (~5 KB), stable URL. The choice of VkusVill-favicon vs. VkusVill-root is documented in `v1.19-ARCHITECTURE.md §2`.
- **D-02:** Probe timeout = 12 s. Rationale: measured healthy-node latency through the VLESS bridge on EC2 (2026-05-03) = 7-9 s with p95 ≈ 9.2 s. 12 s = p95 × 1.30 safety margin. PR #25's 5 s was below the measured median and false-negatived every healthy probe. This constant MUST be guarded by a regression test (see D-11).
- **D-03:** Probe uses `httpx.Client` (not `requests`) with `proxies="socks5h://127.0.0.1:10808"` and `verify=True`. `socks5h` (not `socks5`) so DNS resolution happens through the proxy — important when VkusVill geo-blocks our ISP's resolvers.
- **D-04:** Probe expects HTTP status in `{200, 204, 304, 404, 403}` — 4xx from VkusVill's edge is STILL proof the bridge reaches VkusVill (the edge answered). Only timeout / connection reset / DNS failure count as probe failures. 403 in particular is "VkusVill sees us but doesn't like us" which is a downstream problem, not a bridge problem.
- **D-05:** Probe result is cached for 30 s in a module-level `_LAST_SUCCESS_AT: float | None` variable. If the last probe succeeded ≤ 30 s ago, skip the probe and return `ProbeResult(ok=True, cached=True)`. REL-05. Cache is cleared on any failed probe.

### Rotation behavior (addresses REL-03, REL-04)
- **D-06:** Maximum 2 rotations per scraper launch. Attempt sequence: probe → (fail) → `mark_current_node_blocked(reason="preflight_timeout")` → probe → (fail) → `pm.next_proxy()` → probe → (fail) → give up, return `ProbeResult(ok=False)`, let caller decide (currently: continue with cycle anyway and accept per-scraper retry; Phase 60 circuit breaker will count the failed cycle).
- **D-07:** First rotation uses `mark_current_node_blocked` (marks current head into VkusVill 4h cooldown, triggers one xray restart via `_remove_host_and_restart`). Second rotation uses `next_proxy` (pops the new head, triggers another xray restart). Yes, both restart xray. No, there is no restart-free rotation (see `v1.19-PITFALLS.md §2`; PR #26's assumption otherwise was wrong). The fix is capping count, not pretending one path doesn't restart.
- **D-08:** Do NOT call `next_proxy` in a tight loop (PR #25 failure mode). Each rotation is followed by a probe; the probe gates the next rotation. Max 2 rotations = max 2 xray restarts per scraper launch, not 5.

### Scheduler integration (addresses REL-01)
- **D-09:** Pre-flight probe call placement: immediately after `_prepare_proxy_connectivity(proxy_state)` at `scheduler_service.py:407`, BEFORE the per-scraper `for script, tag, data_file in scrapers:` loop. One probe per scraper-set invocation, not per scraper.
- **D-10:** If all 2 rotations fail (probe still dead after exhausting cap), log a WARNING and proceed to run the scrapers anyway. Do NOT early-abort the cycle. Reasoning: the probe is a heuristic, not truth. A 12 s probe timeout that fails doesn't guarantee the scraper's slower 30-45 s Chrome load will also fail. We lose less by running the scrapers through a possibly-dead bridge than by skipping the whole cycle. Phase 60's circuit breaker handles "consistently failing" with the proper state machine.

### Testing (addresses REL-02 regression guard + OPS-06/07)
- **D-11:** `tests/test_preflight_timeout_regression.py` asserts `probe_bridge_alive.__defaults__[0] >= 12` (or equivalent) AND has a docstring citing the measurement evidence. The test MUST fail if anyone lowers the constant. This is the primary guard against a PR #25-style regression.
- **D-12:** `tests/test_preflight_rotation_cap.py` uses a mock `VlessProxyManager` to simulate failing probes and asserts that `_run_scraper_set` invokes at most 2 rotations before giving up.
- **D-13:** Tests mock `httpx.Client.get` (no real network). A separate EC2-only smoke test (`scripts/verify_v1.19.sh`) does the live probe.

### Verification (addresses OPS-06, OPS-07, OPS-08)
- **D-14:** Per-phase `59-VERIFICATION.md` documents: EC2 deploy steps, expected systemd journal output, Vercel miniapp cart-add check, rollback command. First concrete instance of OPS-06.
- **D-15:** `scripts/verify_v1.19.sh` ships as a skeleton in this phase: runs SSH smoke test, captures output, exits 0 on pass / 1 on fail. Future phases append their own smoke criteria. First concrete instance of OPS-07.
- **D-16:** Rollback rehearsal: create a throwaway branch, deploy to EC2, run `git revert HEAD`, redeploy, confirm `systemctl status saleapp-scheduler` is back to pre-phase behavior. Document evidence in `59-VERIFICATION.md`. First concrete instance of OPS-08.

### Scope guardrails
- **D-17:** Do NOT modify `vless/manager.py`. This phase is additive-only on the vless/ side.
- **D-18:** Do NOT change `PROBE_TIMEOUT = 8` in `vless/manager.py` — that's the admission probe for new VLESS candidates, different concern from bridge pre-flight. Confusion between the two is explicitly documented in `v1.19-PITFALLS.md`.
- **D-19:** Do NOT add new dependencies. `httpx` is already in `requirements.txt` (used by cart/vkusvill_api.py); preflight uses the same lib.
- **D-20:** Do NOT change auto-deploy behavior. The user relies on `git push origin main` → Vercel-rebuild; scheduler deploys via `ssh scraper-ec2 "cd /home/ubuntu/saleapp && git pull && sudo systemctl restart saleapp-scheduler"`.

### The agent's Discretion
- Exact module structure of `vless/preflight.py` (dataclass vs NamedTuple for `ProbeResult`, whether to expose internal helpers)
- Whether to accept additional probe-target URLs via an env var (default stays hard-coded to VkusVill favicon)
- Naming of test functions (follow `test_preflight_*` convention; match existing `test_vless_*` style)
- Exact shape of log messages (keep consistent with existing `scheduler_service.py::log()` format)
- Whether rotation logging goes through `pm._log()` or scheduler's `log()` (either is fine; pick one and stay consistent)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### This phase's driver
- `../../research/v1.19-SUMMARY.md` — 3 findings driving the whole milestone; start here for "why"
- `../../research/v1.19-PITFALLS.md` — 15 grounded mistake modes; §1 (timeout under empirical latency), §2 (restart cascade), §3 (probe/target mismatch) are the direct lessons from PR #25 / PR #26

### Related milestone artifacts
- `../../REQUIREMENTS.md` — REL-01 through REL-05 are what this phase delivers; OPS-06/07/08 are cross-cutting
- `../../ROADMAP.md` §Phase 59 — 6 success criteria and dependencies

### Post-mortem evidence
- GitHub PR #25 (Devin, 2026-04-29) — the 5 s preflight probe attempt, merged then reverted 8 min later. Diff is the primary case study for what NOT to do.
- GitHub PR #26 (revert) — the revert description that partially mis-diagnosed the issue (said "use `mark_current_node_blocked` because it doesn't restart xray"; both paths restart xray).

### Predecessor phase
- `../58-geo-resolver-and-scraper-recovery/58-SUMMARY.md` — v1.18 shipped state; VLESS bridge is operational, just silently degrading.

### Live production evidence (2026-05-03)
- Pool 25 → 13 over 8 days
- 162 consecutive scraper-cycle failures, circuit breaker re-tripping every 2 min for ~5.4 h
- 30/30 detail-proxy timeouts in the last 10 min
- Vercel `/api/products` returns HTTP 200 with cached data (masking the broken state)

### Code under modification (read-only during context gathering)
- `scheduler_service.py:406-443` — `_run_scraper_set` function; integration site
- `scheduler_service.py:373-403` — `_prepare_proxy_connectivity`; upstream of the integration site
- `vless/manager.py:48` — `MIN_HEALTHY = 7`
- `vless/manager.py:52` — `PROBE_TIMEOUT = 8` (admission probe; DO NOT confuse with pre-flight)
- `vless/manager.py:165-211` — `remove_proxy`, `next_proxy`, `mark_current_node_blocked` (used as rotation primitives)
- `vless/manager.py:885` — `_remove_host_and_restart` (both rotation paths land here; restarts xray)

</canonical_refs>

<specifics>
## Specific Ideas

### ProbeResult shape (informative, not binding)

```python
from dataclasses import dataclass

@dataclass
class ProbeResult:
    ok: bool
    status: int | None          # HTTP status if reached; None on connect/timeout/DNS fail
    reason: str                 # "ok" | "timeout" | "connect_reset" | "dns_fail" | "http_5xx" | "cached"
    elapsed_s: float
    cached: bool = False
```

### Integration shape in `_run_scraper_set`

```python
def _run_scraper_set(scrapers, proxy_state):
    pm, proxy_state = _prepare_proxy_connectivity(proxy_state)

    # Pre-flight probe: ensure the VLESS bridge can reach VkusVill before
    # we burn 30-45 s launching Chrome. Up to 2 rotations on failure, then
    # proceed anyway (the circuit breaker will catch chronic failure).
    from vless.preflight import probe_bridge_alive
    probe = probe_bridge_alive(timeout=12)
    rotations = 0
    while not probe.ok and rotations < 2:
        log(f"Pre-flight probe failed ({probe.reason}, {probe.elapsed_s:.1f}s) — rotating")
        if rotations == 0:
            pm.mark_current_node_blocked("preflight_timeout")
        else:
            pm.next_proxy()
        rotations += 1
        probe = probe_bridge_alive(timeout=12)

    if not probe.ok:
        log(f"Pre-flight probe still failing after {rotations} rotations — proceeding anyway")
    elif probe.cached:
        log(f"Pre-flight probe: cached ok (last success {time.time() - _LAST_SUCCESS_AT:.0f}s ago)")
    else:
        log(f"Pre-flight probe: ok ({probe.status} in {probe.elapsed_s:.1f}s)")

    scraper_results = {}
    for script, tag, data_file in scrapers:
        # ... existing per-scraper loop unchanged
```

### `scripts/verify_v1.19.sh` skeleton shape

```bash
#!/usr/bin/env bash
# v1.19 Reliability Smoke Test
# Runs from local terminal; SSHes to EC2; reports pass/fail per criterion.
# Grows with each phase.
set -euo pipefail

PHASE="${1:-all}"
EC2_HOST="scraper-ec2"

echo "=== v1.19 smoke test (phase: $PHASE) ==="

if [[ "$PHASE" == "59" || "$PHASE" == "all" ]]; then
    echo "--- Phase 59: Pre-flight probe ---"
    # 59-A: vless/preflight.py exists on EC2
    ssh "$EC2_HOST" "test -f /home/ubuntu/saleapp/vless/preflight.py" \
        && echo "✓ 59-A: vless/preflight.py deployed" \
        || { echo "✗ 59-A: vless/preflight.py missing"; exit 1; }
    # 59-B: scheduler log shows pre-flight probe running each cycle
    ssh "$EC2_HOST" "sudo journalctl -u saleapp-scheduler -n 200 | grep -q 'Pre-flight probe'" \
        && echo "✓ 59-B: scheduler invokes pre-flight probe" \
        || { echo "✗ 59-B: no pre-flight probe log in last 200 lines"; exit 1; }
    # 59-C: Vercel miniapp cart-add still HTTP 200
    # (runs locally, not through SSH)
    # ... (filled in by 59-03-PLAN.md)
fi

# Future phases append their blocks here (60, 61)

echo "=== all checks passed ==="
```

</specifics>

<deferred>
## Deferred Ideas

These came up during context but explicitly don't belong in Phase 59:

- **Probe failure reason classification** (DNS / TLS / HTTP-4xx / timeout / connect-reset with per-node counters) — captured as REL-FUT-01 in `REQUIREMENTS.md`, v1.20.
- **Multi-target probe** (VkusVill + ipinfo.io; admit only if both pass) — REL-FUT-02, v1.20.
- **Probe URL configurable via env var** — useful but adds a new failure mode (misconfigured env in prod). Keep hard-coded for now; revisit if a legitimate use case surfaces.
- **Async probe** (non-blocking, fire before Chrome launch starts; join before launch fires) — would save ~12 s per cycle but adds concurrency complexity; the 4% overhead is acceptable for now.
- **Telegram alert on probe failure** — noise risk (probe failures are noisy on purpose). Defer to REL-FUT-05 (breaker-state Telegram alert), which fires on state transitions only.

</deferred>

---

*Phase: 59-corrected-preflight-vless-probe*
*Context gathered: 2026-05-03 via direct plan path (user skipped discuss-phase with explicit intent)*
