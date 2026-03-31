---
phase: 1
plan: 1
subsystem: backend-auth
tags: [security, idor, telegram, hmac]
requires: [config.TELEGRAM_TOKEN]
provides: [validate_telegram_init_data, dual-path-auth]
affects: [favorites-api, cart-api]
tech-stack:
  added: []
  patterns: [hmac-sha256-validation, dual-auth-path]
key-files:
  created: []
  modified:
    - backend/main.py
key-decisions:
  - "Dual-path auth: Telegram initData HMAC as primary, X-Telegram-User-Id header as fallback for guest/browser"
  - "auth_date freshness check: 300 seconds (5 minutes) to block replay attacks"
  - "tma prefix convention for Authorization header (matches Telegram standard)"
requirements-completed: [SEC-06, SEC-07]
duration: "3 min"
completed: "2026-03-30"
---

# Phase 1 Plan 01: Telegram initData HMAC Validation Summary

Added cryptographic IDOR protection using Telegram's official initData HMAC-SHA256 validation, replacing the header-only check with a dual-path authentication middleware.

**Duration:** ~3 min | **Tasks:** 2/2 | **Files:** 1 modified

## What Was Built

1. **`validate_telegram_init_data()`** — Standalone HMAC-SHA256 validation function that:
   - Parses URL-encoded initData from Telegram MiniApp SDK
   - Validates hash using `WebAppData` → `bot_token` → `data_check_string` chain
   - Checks `auth_date` freshness (5-minute window)
   - Returns parsed user dict on success, None on failure
   - Uses `hmac.compare_digest` for constant-time comparison

2. **Dual-path `_validate_user_header()`** — Drop-in replacement that:
   - **Path 1 (Telegram):** If `Authorization: tma <initData>` present → validate HMAC → extract user.id → compare with expected_user_id
   - **Path 2 (Guest/Browser):** If no `Authorization` header → fallback to `X-Telegram-User-Id` header match (existing behavior preserved)
   - All 7 callers (3 favorites + 4 cart endpoints) unchanged

3. **TELEGRAM_TOKEN import** — Loaded from `config.py` with `os.environ` fallback, mirrors ADMIN_TOKEN pattern

## Verification

- ✅ `python -c "from backend.main import validate_telegram_init_data"` — imports successfully
- ✅ Valid initData + correct token → returns user dict with correct id
- ✅ Wrong token → returns None
- ✅ Tampered data → returns None
- ✅ Missing hash → returns None
- ✅ 7 callers unchanged (no regressions to existing endpoints)

## Deviations from Plan

None — plan executed exactly as written. Tasks 1.1.1 and 1.1.2 were combined into a single edit since they modified the same file contiguously.

## Task Commits

| Task | Hash | Description |
|------|------|-------------|
| 1.1.1 + 1.1.2 | c38c004 | feat(01-01): add Telegram initData HMAC validation and dual-path auth |

## Issues Encountered

None.

## Next

Phase complete. Frontend (Phase 2) needs to send `Authorization: tma <initData>` from MiniApp.
