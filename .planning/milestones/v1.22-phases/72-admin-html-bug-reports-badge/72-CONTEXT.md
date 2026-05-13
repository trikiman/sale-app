# Phase 72 — admin.html Bug Reports Badge — Context

**Milestone:** v1.22 UX Debt Cleanup + Tooling Polish
**Phase number:** 72
**Phase slug:** admin-html-bug-reports-badge
**Date captured:** 2026-05-12
**Requirements covered:** UX-BADGE-01 + continuing OPS-15/16/17

---

## Domain

Original bug report (2026-05-10): v1.16 Phase 61 Success Criterion 3 required a `Bug Reports (N)` badge in the admin dashboard. Backend side shipped correctly — `/admin/status` payload carries `bugReports.count` and `bugReports.unread`. UI side was never written. grep on `backend/admin.html` at HEAD shows zero occurrences of `bugReports` or `bug_reports`. Pure UI gap, ~20 LOC fix.

Evidence from 2026-05-10 todo:
- Backend exposes `data.bugReports.count` and `data.bugReports.unread` via `/admin/status`.
- Admin page already renders `proxy-badge`, `proxy-count`, `cart-pending-count`, `log-count` in the same status row — established pattern to mirror.
- `applyStatus(data)` function in `admin.html` is the only place we need to wire the new badge update.

---

## SPEC Lock (from REQUIREMENTS.md UX-BADGE-01)

LOCKED — planner must NOT re-litigate:

- **Badge placement:** in the header status row next to the existing counts (`📊 Обзор` card). Small, unobtrusive, only visible when count > 0.
- **Element:** new `<span id="bug-reports-badge" class="badge" hidden>` with text `Bug Reports (N)` where N comes from `data.bugReports.unread` (fallback to `data.bugReports.count`).
- **Update path:** inside `applyStatus(data)` — same function that already reads `d.total`, `d.green`, etc. Add a small block right after the existing count updates.
- **Hidden-when-zero:** use the `hidden` attribute, not `display: none`. When `unread > 0`, remove `hidden` and set text. When `unread === 0`, set `hidden` back.
- **Click behavior:** clicking the badge navigates to `/admin/bug-reports` (existing endpoint). Uses `window.location` assignment.
- **Styling:** reuse `badge badge-warn` class (already defined in admin.html) for yellow/orange attention color. No new CSS needed.
- **No new backend work:** `data.bugReports.{count, unread}` is already in `/admin/status`. Phase 72 is pure HTML + inline JS.
- **Test strategy:** no unit test (admin.html has no test infra). Smoke check greps for the badge element in the committed HTML file. Live Chrome DevTools MCP screenshot is the integration proof.
- **Optional fold-in:** if adding a v1.21 `xray_drift` card in the same file is <10 LOC, include as UX-BADGE-02 late-insert. Otherwise defer to a future phase.

---

## Decisions

### D1. Why in the header status row, not a standalone card

A full card would overweight a 20-LOC feature. The header row already has `Всего / Зелёных / Красных / Жёлтых / Live` + the proxy status — one more small badge fits naturally. When `unread > 0` the badge is visible; when `unread = 0` the row looks identical to before.

### D2. Why `hidden` attribute vs `display: none`

`hidden` is a native HTML attribute with consistent cross-browser behavior, matches the zero-state pattern already used elsewhere in admin.html (e.g. `proxy-refresh-status` uses the `hidden` class, which also supports the same logic). Using the attribute means no CSS change.

### D3. Why `badge badge-warn` style not a custom color

`badge-warn` already exists and conveys the right "attention needed, not critical" signal. Using it avoids adding a new CSS class for a 20-LOC feature.

### D4. Click navigates to `/admin/bug-reports` (existing endpoint)

The backend has a `/admin/bug-reports` JSON endpoint already. Direct navigation to that URL in the admin view shows the raw JSON in the browser — adequate for a family-scale app; a richer UI for bug reports is a separate phase if ever needed. This matches the minimal-change spirit of Phase 72.

### D5. Optional UX-BADGE-02 fold-in decision

The v1.21 `xray_drift` block is returned by `_build_reliability_snapshot` under `reliability.xray_drift`. Adding a similar `<span id="xray-drift-badge">` that shows `Drift (N)` when `drift_count > 0` is ~6 LOC of HTML + 8 LOC of JS — total <15 LOC. Cheap enough to fold in as part of Phase 72 while we're already editing admin.html. This closes a v1.21 tech-debt item documented in the audit.

### D6. Single commit for the phase

Phase 72 is tiny (~20-35 LOC total across HTML + JS in a single file). A 3-commit split would add git noise. One commit for implementation, one for smoke + verification. Matches v1.21 Phase 68 pattern where the smoke script block was a separate docs commit.

---

## Locked Defaults

- Badge element: `<span id="bug-reports-badge" class="badge badge-warn" hidden>Bug Reports (0)</span>`
- Data source: `data.bugReports.unread || data.bugReports.count || 0`
- Click target: `window.location.href = '/admin/bug-reports'`
- Placement: inside the status row that hosts `cnt-total`, `cnt-green`, etc. (around line 350-400 in admin.html — exact location derived at implementation time)
- Optional UX-BADGE-02 element: `<span id="xray-drift-badge" class="badge badge-warn" hidden>Drift (0)</span>`
- Optional UX-BADGE-02 data source: `(data.reliability || {}).xray_drift || {}`
- Optional click target: `window.location.href = '/api/health/deep'`

---

## Files Modified

- `backend/admin.html`:
  - New `<span id="bug-reports-badge">` in the header status row (hidden by default).
  - `applyStatus(data)` gains a ~6-line block updating the badge based on `data.bugReports`.
  - Badge click handler: `onclick="window.location.href='/admin/bug-reports'"`.
  - Optional fold-in: `<span id="xray-drift-badge">` in the same row with its own handler for `/api/health/deep`.
- `scripts/verify_v1.22.sh` (APPEND Phase 72 block): 72-A grep for the badge span; 72-B live `/admin/status` has `bugReports` key; optional 72-C for UX-BADGE-02.
- `.planning/phases/72-admin-html-bug-reports-badge/72-VERIFICATION.md` (NEW, NEEDS_OPERATOR for live admin view with auth token).

---

## Verification

- Local: grep finds `bug-reports-badge` in `admin.html`.
- Smoke 72-A: grep on EC2 repo finds the badge span.
- Smoke 72-B: curl `/admin/status` with admin token returns `bugReports.{count,unread}` keys (existing — just confirms no regression).
- Optional 72-C: grep finds `xray-drift-badge` when UX-BADGE-02 folded in.
- NEEDS_OPERATOR (72-VERIFICATION.md):
  - Live admin view: open `https://vkusvillsale.vercel.app/admin` (or `http://13.60.174.46:8000/admin` direct), paste admin token, confirm bug-reports badge either visible (if unread > 0) or hidden (if 0). Screenshot.
  - If a bug report exists in the system, badge shows `Bug Reports (N)` with the correct unread count.
  - Click badge → navigates to `/admin/bug-reports` JSON.
  - Rollback rehearsal.
  - v1.21 + v1.20 + v1.19 regression green.

---

## Phase Boundary

**Ships:** admin.html Bug Reports badge + `applyStatus` wiring + smoke check. Optional UX-BADGE-02 xray_drift badge fold-in if cheap.

**Does NOT ship:**
- Rich admin UI for bug reports (current JSON view is enough for family-scale app)
- Per-bug-report click-through to individual reports
- Mark-as-read button in the admin UI (would need backend update + JS)
- gsd-check-todos skill polish (Phase 73)

**Acceptance gate:** grep finds badge span in admin.html + `/admin/status` still exposes `bugReports` schema + MCP screenshot shows badge rendering (visible or cleanly hidden).
