---
phase: 48-session-warmup-optimization
plan: 01
subsystem: cart
tags: [performance, cart-api, session-warmup, httpx]

requires:
  - phase: 47-diagnose-fix-cart-failures
    provides: cart add diagnostics and pending timeout architecture
provides:
  - sessid_ts timestamp persisted at login for downstream staleness detection
  - warmup GET eliminated from cart-add hot path
  - fast-fail auth_expired when session metadata missing
affects: [48-02, cart-add-latency, session-staleness]

tech-stack:
  added: []
  patterns: [metadata-first session bootstrap, fast-fail auth pattern]

key-files:
  created: []
  modified: [backend/main.py, cart/vkusvill_api.py]

key-decisions:
  - "Remove warmup GET from _ensure_session entirely instead of making it conditional — fail fast with auth_expired is better than 2-5s blocking"
  - "Keep _extract_session_params() method intact for future stale-refresh logic in Plan 02"

patterns-established:
  - "Fast-fail auth: cart operations return auth_expired immediately if session metadata missing rather than attempting slow recovery"

requirements-completed: [PERF-01]

duration: 2min
completed: 2026-04-11
---

# Phase 48 Plan 01: Session Warmup Optimization Summary

**Eliminated 2-5s warmup GET from cart-add hot path by persisting sessid_ts at login and fast-failing on missing session metadata**

## Performance

- **Duration:** 2 min
- **Started:** 2026-04-11T20:23:43Z
- **Completed:** 2026-04-11T20:25:45Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments
- Warmup GET to vkusvill.ru removed from VkusVillCart._ensure_session() hot path — saves 2-5s on first cart add
- sessid_ts Unix timestamp now persisted in cookies.json at login time for downstream staleness detection
- VkusVillCart loads _sessid_ts from cookie metadata on init
- Changes deployed to EC2 production and verified running

## Task Commits

Each task was committed atomically:

1. **Task 1: Add sessid_ts to login cookie payload and remove warmup GET from cart-add path** - `e1dd1df` (perf)
2. **Task 2: Deploy and verify on EC2** - no file changes (deploy/verify only, code in Task 1 commit)

## Files Created/Modified
- `backend/main.py` - Added sessid_ts field to cookie_payload dict at login
- `cart/vkusvill_api.py` - Added _sessid_ts to __init__, loaded from metadata in _ensure_session, removed _extract_session_params() call from hot path

## Decisions Made
- Removed warmup GET entirely from _ensure_session rather than making it conditional — fast-fail with auth_expired is strictly better for 5s budget
- Kept _extract_session_params() method intact for Plan 02 stale-refresh logic

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- sessid_ts available for Plan 02 staleness detection logic
- _extract_session_params() still exists for Plan 02 to wire into stale-refresh path
- Backend restarted on EC2 with new code active

---
*Phase: 48-session-warmup-optimization*
*Completed: 2026-04-11*
