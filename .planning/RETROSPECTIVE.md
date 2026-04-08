# Retrospective

## Milestone: v1.12 — Add-to-Cart 5s Hard Cap

**Shipped:** 2026-04-08
**Phases:** 1 | **Plans:** 1

### What Was Built

- AbortController 5s hard cap on add-to-cart fetch with D3 budget gate at 4s
- Time-budget polling loop replacing fixed 20-iteration design, with per-poll AbortController
- Immediate 404/non-recoverable stop in poll loop

### What Worked

- Live diagnosis session (timing the actual 41s tap-to-error flow) produced exact requirements — no guesswork needed
- Single-phase, single-plan milestone kept overhead minimal for a focused bug fix
- Code review and verification artifacts were written same-day as implementation

### What Was Inefficient

- Nothing notable — this was the cleanest milestone-to-archive cycle so far due to tight scope

### Patterns Established

- Time-budget loops are strictly better than fixed-iteration loops for user-facing timeout scenarios
- D3 budget gates (skip downstream work when budget is nearly exhausted) prevent wasted effort on the hot path

### Key Lessons

- A 41s stuck state was caused by just two missing AbortControllers and one unbounded loop — small fixes, huge UX impact
- Diagnosing timing problems with actual measurements before coding prevents scope creep

### Cost Observations

- Sessions: 1 implementation session + 1 verification/archive session
- Notable: entire milestone from diagnosis to archive in ~24h with 56 lines changed in 1 file

---

## Milestone: v1.10 — Scraper Freshness & Reliability

**Shipped:** 2026-04-05
**Phases:** 4 | **Plans:** 11

### What Was Built

- Sale-session continuity guardrails with 60-minute healthy-absence closure
- Confirmed session reentry semantics for notifier/API “new item” behavior
- Full-cycle plus green-only scheduler cadence with per-source freshness metadata
- MiniApp stale-warning reuse plus faster first-load/card enrichment paths
- Milestone-level regression and release verification artifacts

### What Worked

- Turning the “daily re-appearance” complaint into a concrete state-contract fix made the backend work much more direct
- Adding focused regression tests before pushing further into scheduler/UI changes kept the later work safer
- Reusing existing MiniApp warning surfaces avoided unnecessary UI churn while still making stale data visible

### What Was Inefficient

- Milestone planning and implementation overlapped heavily, so state/roadmap paperwork had to be caught up late
- The repo had several stale backend tests that were still asserting old route contracts and had to be updated during verification
- Nyquist validation artifacts lagged behind the later phases even though the milestone-level verification evidence was strong

### Patterns Established

- Persist a machine-readable cycle-state artifact before merge/history updates when downstream logic depends on scraper trustworthiness
- Use active-session flags rather than “ever seen” tables for “new again” sale-entry semantics
- Cached last-good payload hydration is a pragmatic performance win for this MiniApp when freshness warnings remain visible

### Key Lessons

- A flaky observation pipeline needs explicit “is this cycle trustworthy?” state, not just retry logs
- “New product” and “product visible in the latest snapshot” are not the same concept
- Updating stale tests is part of milestone verification work; otherwise release confidence is fake

### Cost Observations

- Sessions: one concentrated autonomous closeout pass spanning planning, implementation, verification, audit, and archival
- Notable: the majority of risk reduction came from the targeted regression harness and planning cleanup, not from large architectural rewrites

## Milestone: v1.7 — Categories & Subgroups

**Shipped:** 2026-04-03
**Phases:** 5 | **Formal plans:** 1

### What Was Built

- Group/subgroup hierarchy scraped into the catalog pipeline
- Main-page drill-down filters and group/subgroup favorites
- History-page drill-down filters with scope-aligned chip behavior
- Telegram category alerts with dedupe and match reasons

### What Worked

- Exact favorite key contracts (`group:X`, `subgroup:X/Y`) made the backend/frontend/notifier integration straightforward
- Fast production verification caught the History chip-scope mismatch before the milestone was archived
- The notifier feature was easy to regression-test with a temporary SQLite fixture

### What Was Inefficient

- Most v1.7 phases were executed ad-hoc, so milestone paperwork lagged behind implementation
- Auto-deploy verification was slowed by a stale manual `uvicorn` process on EC2 blocking systemd restarts

### Patterns Established

- History-page chip sources must align with the dataset currently displayed (`history` vs `all`)
- Sale-notification code can safely enrich missing hierarchy from `product_catalog`
- Production deploy checks should include both “new commit present” and “correct process actually serving traffic”

### Key Lessons

- Live verification matters as much as local build/test success for backend-served features
- If a milestone ships ad-hoc, closeout docs need to be written immediately or audits go stale fast
- Small focused regression tests are worth adding even late in a milestone

### Cost Observations

- Sessions: 1 concentrated milestone-closeout pass after feature implementation
- Notable: more time went into verification, deploy cleanup, and archive hygiene than into the final notifier code itself

## Cross-Milestone Trends

- Ad-hoc implementation remains faster in the short term, but it creates stale audits and weak milestone stats later
- Production verification has become the main source of last-mile bugs for this project, especially around EC2 process state
- Reusing existing UI/state surfaces usually beats introducing new abstractions when the problem is reliability rather than product scope
- Milestone closeout is smoother when verification artifacts are written during implementation instead of reconstructed afterward
