# Requirements — v1.25 Operator Visibility + Test Coverage

## Milestone Goal

Close the "time-to-notice" gap identified in the v1.24 verifier audit. v1.24 reduced time-to-recover-once-detected from ~60 min to ≤10 min, but time-to-notice is unchanged — during the 2026-05-13 outage, the operator learned about the outage only by opening the MiniApp 60 min in. v1.25 fixes that via Telegram admin alerts on pool-dead + breaker transitions + xray restart failures, plus the ops escape hatches the verifier flagged (force-clear quarantine, force-stale testing helper). Pair with the integration tests the v1.24 audit called out as "MUST ADD before promoting to higher-severity enforcement" so the exact collapse pattern (20→0 in one cycle, 231 dead nodes, 20+ min of failed scrapes) is replayable in CI.

Driving evidence:
- **v1.24 verifier audit** (`.planning/milestones/v1.24-MILESTONE-VERIFICATION.md`): "time-to-recover reduced, time-to-notice deferred"
- **2026-05-13 observation** — operator didn't know for 60 min; first signal was user opening MiniApp
- **v1.24 Phase 77 unit test** — exercises 20→17 gradual decline; does NOT exercise the observed 20→0 in-one-cycle pattern
- **v1.24 Phase 79** — stylelint + eslint configured but **no CI runs them**; rules are "documentation until CI is wired"
- **v1.19 REL-FUT-05** — long-standing tech debt: Telegram alerts on `xray_restart_failed` / breaker state transitions

## Requirements

### Operator Visibility

- [ ] **OBS-08**: Telegram admin alert when pool size stays 0 for > 10 min. One-shot per incident with 30-min cooldown (prevent spam during recovery). Fires via existing `bot/notifier.py` infrastructure. Alert message includes pool size, quarantined count, last successful scrape ts. Recoverable — alert doesn't block recovery.

- [ ] **OBS-09**: Telegram admin alert on breaker state transitions (`closed → open`, `open → half_open`, `half_open → closed`). 5-min cooldown between alerts for same transition type to prevent thrash spam. Addresses v1.19 REL-FUT-05 carry-forward.

- [ ] **OBS-10**: Telegram admin alert on `xray_restart_failed` event. No cooldown (rare enough that each occurrence deserves operator attention). Includes xray process state + last successful reload ts.

### Operations — Escape Hatches

- [ ] **OPS-24**: `POST /admin/vless/quarantine/clear` endpoint wipes `data/pool_quarantine.json`. Requires `X-Admin-Token`. Returns `{cleared_count, previous_entries}` for audit. Use case: false-positive quarantine event (e.g., upstream VLESS provider glitch marks all nodes dead for 5 min).

- [ ] **OPS-25**: `POST /admin/force-stale-all` endpoint — sets a time-limited override (~10 min) that forces `/api/products` to return `staleAll=true` + cached products regardless of actual source freshness. Auto-expires. Use case: deterministic regression testing of v1.24 Phase 78 stale UX without waiting 15+ min for real staleness or pausing the scheduler. Requires `X-Admin-Token`.

### Test Coverage

- [ ] **QA-06**: Integration test replays the 2026-05-13 collapse pattern — pool goes 20→0 in one cycle, 231 RU-filtered candidates are all quarantined, scheduler skips scrapes for N cycles, refresh eventually finds working nodes. Asserts (a) recovery completes within N refreshes, (b) `/api/products` returns cached products with `staleAll=true` throughout the collapse window, (c) no cycle re-probes a quarantined node (verified via probe-count telemetry). Goes into `tests/test_collapse_replay.py`.

- [ ] **QA-07**: Concurrency test for scheduler-vs-manager race on `vless_pool.json`. Spawns a writer thread (simulating `manager.refresh_proxy_list` calling `pool_state.save`) and a reader thread (simulating `scheduler._is_pool_dead`); asserts reader never observes transient inconsistent state across N iterations. Relies on `os.replace` atomicity (already in production) — this test pins the invariant.

- [ ] **QA-08**: `staleAll=true + products=[]` edge case test — backend behavior when source files exist with current mtime but are empty. Asserts the API response is still well-formed and the frontend `App.jsx` empty-state handler renders a useful message (not a blank screen).

### Style Guide v2 Enforcement — CI Wiring

- [ ] **TOOL-04**: GitHub Actions workflow runs `npm run lint` + `npm run lint:css` on every PR. Uses `--max-warnings 0` once baseline debt is refactored (TOOL-05). Until then, runs informationally with PR comment summarizing violation counts.

- [ ] **TOOL-05**: Refactor the 46 baselined inline `style=` violations from `docs/style-guide-debt.md` into CSS classes. Extract common patterns (`grid-row-full`, `text-dimmed`, `clickable`). For truly-dynamic styles (chart widths, etc.), add explicit `// eslint-disable-next-line react/forbid-dom-props -- JUSTIFIED(v1.25): reason` markers so the count converges to zero. After refactor, bump `react/forbid-dom-props` from WARN → ERROR in `eslint.config.js`.

- [ ] **TOOL-06**: Spacing-scale stylelint rule via `declaration-property-value-allowed-list` (not the previously-assumed custom plugin — verifier right to push back). Tokens from style guide v2: `4/8/12/16/24/32/48px` or `var(--space-*)`. Add rule, run, baseline any violations as additional `docs/style-guide-debt.md` entries. If count is high (>30), defer strict enforcement to v1.26.

### Operations — Continuity

- [ ] **OPS-26**: `scripts/verify_v1.25.sh` chains `verify_v1.24.sh all` at the end. Phase 80/81/82 smoke checks grow as they ship.

- [ ] **OPS-27**: Each phase includes live verification where applicable. Phase 80 Telegram alert manually fired on EC2 (trigger pool-dead signal, verify admin DM lands). Phase 81 tests run in CI. Phase 82 verified by introducing a deliberate violation on a temp branch and confirming CI fails.

- [ ] **OPS-28**: Cross-version regression gate green — `bash scripts/verify_v1.24.sh all` passes post-deploy. All v1.25 changes additive.

## v2 Requirements

### Carried forward from earlier milestones

- **REL-FUT-01..04, REL-FUT-06..08, OBS-FUT-01..03** — v1.19 unaddressed items (REL-FUT-05 is consumed by v1.25 OBS-09/10)
- **v1.20 deferred**: Phase 64 HAR capture + `FAST_CART_ADD_URL` go/no-go decision
- **v1.20 NEEDS_OPERATOR-1**: Playwright slow-path test for miniapp
- **v1.21 tech debt**: `XRAY_RESTART_THROTTLE_S` in-memory-only, `_DRIFT_FIRST_SEEN` in-process
- **v1.22 tech debt**: Vitest/RTL wiring for miniapp (caught `[hidden]` CSS bug only via live MCP)
- **v1.23 tech debt**: Background pre-warm of top-visible product details (deferred from PERF-10)
- **v1.24 tech debt**: see `.planning/milestones/v1.24-MILESTONE-VERIFICATION.md` carry-forward list

### Explicitly deferred from v1.24 verifier audit

- Recovery-time p95 dashboard (can be built once QA-06 integration test produces measurable data)
- Per-card badge list-view layout test (requires list-view redesign first)
- WARN→ERROR bump for compliant rules (once TOOL-05 clears baseline)

## Out of Scope

| Feature | Reason |
|---|---|
| Vitest/RTL full wiring | Separate milestone — would need its own design phase for choosing between Vitest + RTL vs. Playwright |
| Historical drift trace / rate-of-change panels | Admin UI polish — belongs in dedicated observability milestone |
| Full VLESS provider migration | Out-of-scope since v1.24 |
| Mobile app / PWA hardening | Family uses Telegram MiniApp; no scope for standalone PWA |

## Traceability

(Provisional phase mapping.)

| Requirement | Provisional Phase | Status |
|---|---|---|
| OBS-08, OBS-09, OBS-10 | Phase 80 (Telegram alerts) | Defined |
| OPS-24, OPS-25 | Phase 80 (admin escape hatches — pairs with alerts) | Defined |
| QA-06, QA-07, QA-08 | Phase 81 (integration tests) | Defined |
| TOOL-04, TOOL-05, TOOL-06 | Phase 82 (style guide CI + debt refactor) | Defined |
| OPS-26/27/28 | All phases (cross-cutting) | Defined |

**Coverage:**
- v1.25 requirements: 13 total (3 OBS, 2 OPS-escape, 3 QA, 3 TOOL, 3 OPS-continuity)
- Mapped to phases: 13 (3 phases + 1 cross-cutting)
- Unmapped: 0 ✓

## Prior Milestone — Archived

v1.24 Pool Self-Heal Hardening + Outage UX shipped 2026-05-13 with 9/9 requirements (OBS-08 deferred to v1.25 by design) across 3 phases (77/78/79). Verifier audit produced `v1.24-MILESTONE-VERIFICATION.md` resolving 4 MUST-CONFIRM-IN-CODE items; final verdict PASS. Full archive:
- `.planning/milestones/v1.24-ROADMAP.md`
- `.planning/milestones/v1.24-REQUIREMENTS.md`
- `.planning/milestones/v1.24-MILESTONE-AUDIT.md`
- `.planning/milestones/v1.24-MILESTONE-VERIFICATION.md`
- `.planning/milestones/v1.24-phases/{77,78,79}-*/`
- Git tag `v1.24`, commits `4eb637e..3ae45bd` (11 commits including verification + bootstrap)

Cross-version regression scripts retained through v1.19.

---
*Requirements defined: 2026-05-13*
*Prior milestone v1.24 archived 2026-05-13*
