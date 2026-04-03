# Retrospective

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
