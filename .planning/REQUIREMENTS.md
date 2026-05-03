# Requirements — v1.19 Production Reliability & 24/7 Uptime

## Milestone Goal

Keep the VkusVill sale app continuously healthy from the user's perspective (Vercel frontend + Telegram MiniApp) 24/7 by hardening the EC2 data pipeline against the failure modes that regressed post-v1.18 — with regression tests and per-phase EC2 smoke verification that would have caught PR #25's revert in pre-merge.

Driving evidence (2026-05-03):
- Pool admitted-node count drifted 25 → 13 over 8 days post-v1.18.
- 162 consecutive scraper-cycle failures observed; circuit breaker re-tripped every 2 min for ~5.4 h with no self-recovery.
- 30/30 detail-proxy timeouts in last 10 min while Vercel `/api/products` returned HTTP 200 with cached data.
- PR #25 (Devin, 2026-04-29) attempted a 5 s pre-flight VLESS probe; reverted 8 min later by PR #26 because empirical healthy-node latency through the bridge is 7-9 s.

Full grounded analysis: `.planning/research/v1.19-SUMMARY.md`.

## Requirements

### Reliability — Pre-flight Bridge Probe

- [ ] **REL-01**: Before each scraper launch (`scrape_red`, `scrape_yellow`, `scrape_green`), the scheduler probes the VLESS bridge via HTTPS GET to a stable VkusVill endpoint and aborts/rotates the launch if the probe fails — eliminating the 30-45 s wasted-Chrome-startup pattern when the current exit node is silently degraded.
- [ ] **REL-02**: The pre-flight probe timeout is set to 12 seconds (empirical healthy-node p95 = 9.2 s × ~1.3 safety margin) and is guarded by a regression test that fails if anyone lowers it without re-measuring against the actual EC2 bridge.
- [ ] **REL-03**: Pre-flight probe rotation is capped at 2 attempts per scraper launch — after the second failed rotation the cycle aborts and the circuit breaker takes over, instead of cascading into 3+ xray restarts (the PR #25 failure mode).
- [ ] **REL-04**: When rotation is needed, the system prefers xray's own `leastPing` balancer decision (no xray restart) and only falls back to Python-side `mark_current_node_blocked` / `next_proxy` when the balancer has no other healthy member — minimizing xray config rebuilds during failure cascades.
- [ ] **REL-05**: A successful pre-flight probe result is cached for 30 seconds so consecutive scraper launches within the same window skip the redundant probe.

### Reliability — Probe/Target Alignment

- [ ] **REL-06**: The xray observatory `probeURL` is set to a stable VkusVill endpoint (e.g. `https://vkusvill.ru/favicon.ico`) instead of `https://www.google.com/generate_204`, so the `leastPing` balancer ranks outbounds based on real-target reachability rather than third-party reachability — and a regression test asserts the configured probeURL hostname remains a VkusVill domain.

### Reliability — Graduated Circuit Breaker

- [ ] **REL-07**: After 3 consecutive fully-failed cycles the scheduler enters an `open` state (no scraping for cooldown duration), then transitions to `half_open` where it runs one ~30 s green-only probe cycle before committing to full cycles — replacing the current pure-time-based recovery that re-trips repeatedly without ever testing if upstream improved.
- [ ] **REL-08**: Circuit breaker cooldown follows exponential backoff: `min(120 s × 2^level, 30 min)` where `level` is the count of consecutive `open → half_open → open` transitions without a full recovery — replacing the current fixed 120 s cooldown that produced 162 useless re-trips in 5.4 h.
- [ ] **REL-09**: The consecutive-failed-cycles counter resets to 0 on **any** successful scraper run (current behavior only resets on a fully-clean cycle, so partial failures keep the counter stuck and the breaker never trips on degraded-but-not-broken state).
- [ ] **REL-10**: Circuit breaker state is persisted to `data/scheduler_state.json` across scheduler restarts, with corruption-safe fallback to `{"phase": "closed", "backoff_level": 0}` if the file is missing or unreadable.

### Reliability — Pool Drain/Replenish Visibility

- [ ] **REL-11**: The pool refresh path (`ensure_pool` in `vless/manager.py`) is verified to actually fire before `pool_count()` drops below `MIN_HEALTHY = 7`, and any drift detected during 24 h observation is fixed (current production evidence: pool 25 → 13 over 8 days indicates refresh cadence may be lagging quarantine drain).
- [ ] **REL-12**: Each refresh and quarantine event logs `pool_size`, `quarantined_count`, and `active_outbounds_count` to `data/proxy_events.jsonl` so multi-day drift is visible to the operator without ad-hoc log scraping.

### Observability — Deep Health Endpoint

- [ ] **OBS-01**: An unauthenticated `GET /api/health/deep` endpoint returns HTTP 200 + JSON when the stack is healthy and HTTP 503 + JSON when degraded/unhealthy — accessible from external uptime ping services (Uptime Robot, Cronitor, or any `curl`) without admin tokens, with no node IPs or user-identifiable data in the response body.
- [ ] **OBS-02**: Healthy criteria are all-of: `pool_size ≥ MIN_HEALTHY`, circuit breaker phase ∈ {`closed`, `half_open`}, last successful full cycle ≤ 15 min ago, xray process running, merged `products.json` mtime ≤ 15 min ago — and any criterion failure produces a status of `degraded` (1-2 criteria failed) or `unhealthy` (3+ failed, or any of: xray dead / scheduler heartbeat stale).
- [ ] **OBS-03**: The `/api/health/deep` response always includes a `reasons: []` array enumerating which criteria failed (e.g. `["pool_size 6 below MIN_HEALTHY 7", "circuit_breaker half_open (next_attempt in 42 s)"]`) so post-incident debugging is possible without server-side log access — and the response is rate-limited to 1 request/sec/IP.

### Operations — Per-Phase Verification Rigor

- [ ] **OPS-06**: Every phase in v1.19 ships with a `VERIFICATION.md` describing EC2 deploy steps, smoke test commands, Vercel-side check (e.g. `/api/products` HTTP 200 + `/api/cart/add` HTTP 200), and rollback evidence (what to do if the phase regresses production).
- [ ] **OPS-07**: Each phase contributes to `scripts/verify_v1.19.sh` — a shell-executable, idempotent smoke test that runs on EC2 over SSH and reports pass/fail per criterion; the script grows with each phase so by v1.19 close it covers every reliability behavior introduced in this milestone.
- [ ] **OPS-08**: Before merging any v1.19 phase to `main`, the rollback procedure is dry-run rehearsed against a staging branch (or staging-equivalent: separate EC2 user, paused systemd target) to prove the revert works — eliminating the PR #25 scenario where an 8-minute-revertable PR landed on `main` and broke production.

## v2 Requirements

### Future Follow-Ups (deferred to v1.20)

#### Pre-flight & probing
- **REL-FUT-01** (was A6 in `v1.19-FEATURES.md`): Probe failure-reason classification (DNS / TLS / HTTP-4xx / timeout) with per-node failure counter for explicit quarantine.
- **REL-FUT-02** (was B3): Multi-target probe (VkusVill + ipinfo.io); admit only if both targets pass.
- **REL-FUT-03** (was B4): Per-node VkusVill failure counter in `proxy_events.jsonl` + auto-quarantine after K failures in sliding window.

#### Breaker enhancements
- **REL-FUT-04** (was C5): Auto-trigger pool refresh on entering `half_open` (not just on initial trip).
- **REL-FUT-05** (was C6): Telegram bot alert on breaker state change (`closed → open`, `open → half_open`, `half_open → closed`) with deduplication.

#### Pool tuning
- **REL-FUT-06** (was D3): Replenish to `MAX_CACHED` instead of stopping at `MIN_HEALTHY + 1`.
- **REL-FUT-07** (was D4): Shorter cooldown for non-block failures (TLS handshake fail = 15 min instead of 4 h).
- **REL-FUT-08** (was D5): Predictive refresh when quarantine rate exceeds replenish rate.

#### Health observability
- **OBS-FUT-01** (was E5): Light `/api/health` endpoint (200 if process alive, for systemd watchdog).
- **OBS-FUT-02** (was E6): Reliability tab in `/admin` panel surfacing breaker state + pool trend.
- **OBS-FUT-03** (was E7): Telegram heartbeat (6 h "still healthy" pings to prove alerting loop is alive).

#### Verification rigor
- **OPS-FUT-01** (was F4): Pre-merge live deploy of PR branch on EC2 with smoke script execution gating merge.
- **OPS-FUT-02** (was F5): Post-deploy 24 h hourly observation window with regression alert.

#### User-facing degraded mode (entire Category G)
- **UI-FUT-01** (was G1): Stale banner reflects `/api/health/deep` status (not just data age).
- **UI-FUT-02** (was G2): Detail drawer indicates "live detail unavailable, showing cached info" when proxy fails.
- **UI-FUT-03** (was G3): Cart add button disabled with tooltip when deep health says unhealthy.
- **UI-FUT-04** (was G4): Reliability tab in admin panel surfaces circuit state + pool trend (overlaps OBS-FUT-02).

## Out of Scope

| Feature | Reason |
|---------|--------|
| Replace xray-core with WireGuard or a different bridge | xray + VLESS+Reality is the right fit (chosen in v1.15 for verified RU exit + Reality TLS); v1.19 is reliability of the existing stack, not substitution |
| Migrate to Kubernetes / containerization | EC2 + systemd is appropriate for family-scale; 1 host, 3 services |
| Add a paid APM (Datadog / New Relic / Sentry) | Family scale; deep-health endpoint + Telegram bot is sufficient signal |
| Frontend framework change | React + Vite is correct; v1.19 is backend reliability |
| New database (PostgreSQL etc.) | SQLite + JSON files are sufficient; pool/health/circuit state fits in existing `data/` artifacts |
| Auto-restart of services from external watchdog | Auto-recovery belongs inside the application's state machine (breaker), not external; auto-restart masks root causes |
| Manual-intervention-only recovery patterns | Anti-feature; v1.19's whole point is self-healing without operator intervention |
| User-visible degraded mode (Category G) | Backend-first milestone; clean foundation now, deferred to v1.20 — current UI provides enough info per user direction 2026-05-03 |
| Prometheus / Grafana / metrics scraping | Over-engineering for family scale; revisit only if v1.19 closes with unexplained behavior |
| Rolling out v1.19 phases concurrently in parallel | Each phase's smoke test must pass before the next phase starts; serial execution is the cultural commitment to no-hotfix discipline |

## Traceability

(Provisional phase mapping; finalized by `/gsd-roadmapper` in step 10 of the new-milestone workflow.)

| Requirement | Provisional Phase | Status |
|---|---|---|
| REL-01 | Phase 59 (Corrected pre-flight probe) | Defined |
| REL-02 | Phase 59 | Defined |
| REL-03 | Phase 59 | Defined |
| REL-04 | Phase 59 | Defined |
| REL-05 | Phase 59 | Defined |
| REL-06 | Phase 60 (Probe/target alignment + graduated breaker) | Defined |
| REL-07 | Phase 60 | Defined |
| REL-08 | Phase 60 | Defined |
| REL-09 | Phase 60 | Defined |
| REL-10 | Phase 60 | Defined |
| REL-11 | Phase 61 (Deep health endpoint + pool snapshot) | Defined |
| REL-12 | Phase 61 | Defined |
| OBS-01 | Phase 61 | Defined |
| OBS-02 | Phase 61 | Defined |
| OBS-03 | Phase 61 | Defined |
| OPS-06 | All phases (cross-cutting) | Defined |
| OPS-07 | All phases (cross-cutting) | Defined |
| OPS-08 | All phases (cross-cutting) | Defined |

**Coverage:**
- v1.19 requirements: 18 total (12 REL, 3 OBS, 3 OPS)
- Mapped to phases: 18 (provisional)
- Unmapped: 0 ✓

## Prior Milestone (v1.15) — Archived

The v1.15 Proxy Infrastructure Migration requirements have been moved to `.planning/milestones/v1.15-REQUIREMENTS.md`. v1.15 (Phase 56) shipped 2026-04-23 and replaced the dead free-SOCKS5 pool with a VLESS+Reality + local xray-core bridge — the foundation v1.19 is now hardening for 24/7 reliability.

The intermediate milestones v1.17 (Phase 57 — VLESS Timeout Hardening, shipped 2026-04-24) and v1.18 (Phase 58 — Geo Resolver & Scraper Recovery, shipped 2026-04-25) were executed as direct phase work without separate REQUIREMENTS.md cycles; their goals and outcomes are recorded in `.planning/MILESTONES.md` and `.planning/ROADMAP.md`.

The post-v1.18 production drift is the direct driver of this v1.19 milestone — see `.planning/research/v1.19-SUMMARY.md` for the grounded failure analysis.

---
*Requirements defined: 2026-05-03*
*Prior milestone v1.15 archived to `.planning/milestones/v1.15-REQUIREMENTS.md`: 2026-05-03*
