# Requirements — v1.16 Bug Reports

## Milestone Goal

Authenticated MiniApp users can submit a bug report with free-form text, a category, and an optional photo. The report is automatically enriched with the recent client console-log buffer plus runtime metadata (route, viewport, user agent, app version, telegram_id, timestamp). Reports are stored as files in `data/bug_reports/<timestamp>_<id>.json` (with optional `.jpg` photo alongside) so backups and inspection are simple `tar`/`grep`/`scp` operations. The admin can see report count and a preview list through admin-token-gated endpoints — no separate database migration, no new admin UI surface beyond what already exists.

## Requirements

### Frontend (MiniApp Form)

- [x] **BUG-01**: Authenticated user can open a bug report form from the MiniApp (header 🐞 button, only visible when authenticated)
- [x] **BUG-02**: User can enter free-form text (10-2000 chars), select category (`cart`, `login`, `scrape`, `ui`, `other`), and optionally attach one photo (≤5MB, image/* mime types only) before submitting
- [x] **BUG-03**: Form auto-attaches runtime metadata at submit time: current route/URL, viewport dimensions, user agent, app version (`VITE_APP_VERSION` env or 'dev'), telegram_id, ISO-8601 timestamp

### Console Log Buffer

- [x] **BUG-04**: Client buffers the last 30 seconds (capped at 100 records) of `console.error`, `console.warn`, `window.error`, and `unhandledrejection` events via `consoleBuffer.js` installed at app startup in `main.jsx`; the buffer is attached to every bug report submission

### Backend (Storage)

- [x] **BUG-05**: `POST /api/bug-reports` accepts a multipart form (text + meta JSON + optional photo) and writes `data/bug_reports/<ISO-timestamp>_<random8>.json` containing report fields plus client meta and console buffer; if a photo is present it is written alongside as `<same-prefix>.jpg`
- [x] **BUG-06**: The endpoint requires an authenticated session via existing `_validate_user_header` (X-Telegram-User-Id + initData); unauthenticated submissions return 403
- [x] **BUG-07**: Photo uploads enforce ≤5MB size, `image/*` mime type, and PIL `Image.verify()` decode validation — corrupt or oversized files return 400 with no partial state

### Admin Visibility

- [x] **BUG-08**: `GET /api/admin/bug-reports` (gated by `X-Admin-Token`) returns a JSON list of recent reports with: timestamp, telegram_id, category, text preview (first 200 chars), `has_photo`, filename. Plus bonus endpoints: `GET /api/admin/bug-reports/{id}` for full payload + `GET /api/admin/bug-reports/{id}/photo` for the JPG
- [x] **BUG-09**: Admin status payload (`/admin/status`) exposes `bugReports.{count, unread}` for dashboard badge; unread count drops to 0 after admin lists reports (last-read marker in `data/bug_reports_last_read.json`)

## v2 Requirements

### Future Follow-Ups

- **BUG-10**: Telegram bot notification to the operator (`OWNER_TELEGRAM_ID`) when a new report arrives, including category + text preview
- **BUG-11**: Admin "mark as read / triaged / fixed" workflow with status persisted into the report file itself
- **BUG-12**: Auto-screenshot via `html2canvas` or `Element.toDataURL` for non-CORS surfaces (deferred — heavy lib, CORS issues with VkusVill CDN images)
- **BUG-13**: Repository link (e.g. GitHub issue auto-creation) from a triaged report

## Out of Scope

| Feature | Reason |
|---------|--------|
| Auto screenshot of MiniApp on submit | `html2canvas` is ~50KB and breaks on cross-origin VkusVill product images; manual photo upload covers the same need |
| Redux/state snapshot | The MiniApp uses local React state, not a centralized store — there is no single state tree to dump |
| Telegram bot `/bug` command | v1.16 is MiniApp-only; bot entry deferred to BUG-10 |
| Custom admin UI page | Existing admin panel + JSON endpoint is enough for a family-only app; new dedicated admin page deferred |
| DB-backed report storage | File-based storage matches scale (≤5 users, low-volume reports), preserves atomic backup semantics, and avoids a SQLite migration |
| Public/anonymous reports | Auth-gated only — prevents spam without rate-limit/captcha complexity |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| BUG-01 | Phase 60 | Complete |
| BUG-02 | Phase 60 | Complete |
| BUG-03 | Phase 60 | Complete |
| BUG-04 | Phase 60 | Complete |
| BUG-05 | Phase 59 | Complete |
| BUG-06 | Phase 59 | Complete |
| BUG-07 | Phase 59 | Complete |
| BUG-08 | Phase 61 | Complete |
| BUG-09 | Phase 61 | Complete |

**Coverage:**
- v1.16 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0 ✓
- Implemented: 9/9 ✓ (28 unit tests pass: 21 backend + 7 frontend)

## Prior Milestone (v1.15) — Archived

v1.15 Proxy Infrastructure Migration shipped 2026-04-22 and was retroactively closed 2026-04-28. See `.planning/milestones/v1.15-REQUIREMENTS.md` for the archived requirements.

The proxy migration is foundational for `POST /api/bug-reports` reliability — bug-report uploads with photo attachments need the same VLESS-routed proxy guarantees as cart-add already does.

---
*Requirements defined: 2026-04-28*
*Prior milestone v1.15 archived: 2026-04-28*
