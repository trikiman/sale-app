---
phase: 2
plan: 1
subsystem: frontend-auth
tags: [security, idor, telegram, miniapp]
requires: [Telegram.WebApp.initData]
provides: [getAuthHeaders]
affects: [App.jsx, CartPanel.jsx]
key-files:
  created:
    - miniapp/src/api.js
  modified:
    - miniapp/src/App.jsx
    - miniapp/src/CartPanel.jsx
key-decisions:
  - "Centralized getAuthHeaders() helper instead of inline headers"
  - "Keep X-Telegram-User-Id alongside initData during rollout for backward compat"
requirements-completed: [SEC-08]
duration: "2 min"
completed: "2026-03-30"
---

# Phase 2 Plan 01: Frontend initData Auth Headers Summary

Created centralized `getAuthHeaders(userId)` helper and replaced all 10 hardcoded `X-Telegram-User-Id` header locations to send Telegram `initData` when available.

**Duration:** ~2 min | **Tasks:** 3/3 | **Files:** 3 (1 created, 2 modified)

## What Was Built

1. **`miniapp/src/api.js`** — New auth helper module:
   - `getAuthHeaders(userId)` — returns `Authorization: tma <initData>` when `Telegram.WebApp.initData` is available
   - Falls back to `X-Telegram-User-Id` header for guest/browser users
   - Keeps both headers during rollout for backward compatibility

2. **App.jsx** — 6 fetch calls updated (favorites GET/POST/DELETE, cart items GET, cart add POST)

3. **CartPanel.jsx** — 4 fetch calls updated (cart items GET, cart remove POST, cart quantity POST, cart clear POST)

## Verification

- ✅ Zero hardcoded `X-Telegram-User-Id` remaining in App.jsx and CartPanel.jsx
- ✅ `npm run build` passes cleanly (364.59 kB JS, 26.78 kB CSS)
- ✅ getAuthHeaders detects Telegram SDK and returns appropriate headers

## Deviations from Plan

None — plan executed exactly as written.

## Task Commits

| Task | Hash | Description |
|------|------|-------------|
| 2.1.1 + 2.1.2 + 2.1.3 | c8d866d | feat(02-01): add getAuthHeaders() and send initData from MiniApp |

## Issues Encountered

None.

## Next

Phase complete. IDOR security is now end-to-end: backend validates initData, frontend sends it.
