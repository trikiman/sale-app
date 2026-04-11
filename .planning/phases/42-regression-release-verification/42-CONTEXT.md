# Phase 42: Regression & Release Verification - Context

**Gathered:** 2026-04-05
**Status:** Ready for planning

<domain>
## Phase Boundary

Prove the milestone’s continuity, freshness, alerting, and main-screen performance behavior is stable before shipping. This phase covers automated regression coverage, verification artifacts, and release-readiness checks. It does not add new product behavior outside what Phases 39-41 already changed.

</domain>

<decisions>
## Implementation Decisions

### Verification Scope
- **D-01:** Verification must explicitly prove the fake daily re-appearance scenario is gone.
- **D-02:** Verification must cover duplicate-notification prevention across partial-failure cycles.
- **D-03:** Verification must exercise the new scheduler cadence and stale-warning behavior.
- **D-04:** Verification must confirm the main-screen/card experience is meaningfully faster or smoother than before.

### Release Evidence
- **D-05:** Keep the verification results inspectable in files/logs, not just as a one-time terminal run.
- **D-06:** Prefer repeatable automated checks first, with targeted manual/browser verification where needed.

### the agent's Discretion
- Exact verification artifact format, as long as it is easy to inspect later.
- Exact test split between backend pytest, frontend tests, and browser/manual verification.

</decisions>

<specifics>
## Specific Ideas

- The user specifically wants confidence that the fake “appears every day” bug is really fixed.
- Verification should also prove stale/failure warnings are visible and green freshness is improved relative to red/yellow.
- The milestone should not be closed on vibes alone; it needs inspectable evidence.

</specifics>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` — Phase 42 goal, requirements mapping, and success criteria
- `.planning/REQUIREMENTS.md` — QA-03 verification contract
- `.planning/PROJECT.md` — milestone framing and current active goals
- `.planning/STATE.md` — milestone status, known bugs, and phase notes

### Prior Phase Contracts
- `.planning/phases/39-sale-continuity-guardrails/39-CONTEXT.md`
- `.planning/phases/40-freshness-aware-scheduler-alerts/40-CONTEXT.md`
- `.planning/phases/41-main-screen-card-performance/41-CONTEXT.md`
- `.planning/codebase/TESTING.md`

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- Existing backend pytest suites can host most milestone regression checks.
- `miniapp/test_ui.py` already provides a starting point for browser-level smoke verification.
- Admin status/log endpoints already expose operator-facing evidence that can be extended into release verification.

### Established Patterns
- The repo already uses phase verification and parity report artifacts for inspectable evidence.
- There is no heavy CI pipeline; release confidence comes from targeted test commands plus explicit verification artifacts.

### Integration Points
- Backend pytest files for continuity/newness/freshness regressions
- MiniApp/browser verification for loading/interaction feel
- Phase verification/report files under `.planning/phases/42-regression-release-verification/`

</code_context>

<deferred>
## Deferred Ideas

- Broader long-term monitoring/observability work beyond this milestone’s regression and release checks

</deferred>

---

*Phase: 42-regression-release-verification*
*Context gathered: 2026-04-05*
