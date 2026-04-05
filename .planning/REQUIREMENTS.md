# Requirements: v1.10 Scraper Freshness & Reliability

**Status:** Planned
**Created:** 2026-04-05
**Goal:** Keep sale/newness signals correct and the main screen fast by making scrape cadence, failure handling, and card loading more resilient.

## Sale Continuity & Notification Correctness

- [ ] **HIST-08**: User sees one continuous sale session for a product that stayed on sale, even if one or more scrape cycles partially fail or temporarily miss the product.
- [ ] **BOT-07**: User does not receive repeated "new item" or favorite-available alerts for a product that never actually left sale.
- [ ] **OPS-02**: Partial or failed scrape cycles do not overwrite downstream history/newness calculations as if missing products truly disappeared.

## Scheduler Freshness

- [ ] **SCRP-10**: Green scraper can refresh more frequently than red/yellow within the current sequential Chrome/profile constraints.
- [ ] **SCRP-11**: Backend/admin status exposes per-source freshness so green staleness is distinguishable from red/yellow staleness.
- [ ] **SCRP-12**: Merge/notifier logic can use the freshest valid source snapshots instead of assuming every source was refreshed in the same cadence bucket.

## MiniApp Load & Card Performance

- [ ] **UI-16**: Main sale screen reaches first useful content without a long blocking spinner under normal conditions.
- [ ] **UI-17**: Product cards remain responsive while enrichment data loads, and card interactions do not feel laggy.
- [ ] **UI-18**: Card/detail data path is profiled and optimized; any extra API or reverse-engineered data path must be justified by measured latency improvement.

## Operations & Verification

- [ ] **OPS-03**: Admin or Telegram receives visible failure alerts when scraper/scheduler cycles error, time out, or keep serving stale data.
- [ ] **QA-03**: Automated coverage protects continuous-sale session integrity, non-duplicate notifications after partial failures, scheduler cadence rules, and the main-screen performance contract.

## Future Requirements

- [ ] **SCRP-13**: Replace the browser-driven green path with a reverse-engineered/private API only if freshness targets still cannot be met after cadence and robustness fixes.
- [ ] **UI-19**: Move to larger-scale feed optimization (server-driven pagination or virtualization) if card performance still degrades as product volume grows.

## Out of Scope

- Replacing the established Python + React + nodriver stack in this milestone.
- Running scrapers in parallel Chrome sessions; the existing sequential constraint stays in place.
- Full redesign of the MiniApp card UI unrelated to speed, freshness, or failure handling.

## Traceability

| Requirement | Phase | Final Status | Notes |
|-------------|-------|--------------|-------|
| HIST-08 | 39 | Planned | Sale sessions must stay continuous across transient scrape gaps or explicitly tolerated partial cycles |
| BOT-07 | 39 | Planned | Notification dedupe must track real sale exits/re-entries instead of single-cycle visibility loss |
| OPS-02 | 39 | Planned | Bad cycles need a contract that prevents history/newness from treating them as true product disappearance |
| SCRP-10 | 40 | Planned | Green refresh cadence should be higher than red/yellow without breaking sequential Chrome usage |
| SCRP-11 | 40 | Planned | Surface per-source freshness in backend/admin status and downstream UI state |
| SCRP-12 | 40 | Planned | Merge/notifier should operate on freshest valid snapshots rather than same-cycle assumptions |
| OPS-03 | 40 | Planned | Failure and stale-data alerts should be pushed visibly, not left only in logs |
| UI-16 | 41 | Planned | Reduce long blocking first-load state on the main sale screen |
| UI-17 | 41 | Planned | Remove card lag caused by enrichment/render paths while preserving existing UX |
| UI-18 | 41 | Planned | Profile-driven optimization of card/detail data path, including API investigation only if it wins measurably |
| QA-03 | 42 | Planned | Regression/perf verification for continuity, cadence, alerting, and main-screen responsiveness |
