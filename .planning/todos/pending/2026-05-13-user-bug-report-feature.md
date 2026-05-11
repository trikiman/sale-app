---
created: 2026-05-13T01:20:00Z
title: User-facing bug report feature in MiniApp
area: ui
priority: P2
files:
  - miniapp/src/App.jsx (entry point — settings / menu)
  - backend/main.py (new /api/bug-report endpoint + persistence)
  - backend/admin.html (already has Bug Reports (N) badge from v1.22 Phase 72)
  - data/bug_reports/ (backend already stores reports here)
---

## Problem

Users hit issues (mismatched counts, slow card open, stale data, UI shifts) but have no in-app way to report them. Currently bugs only surface through the operator/family channel.

User-reported 2026-05-13: "also can u add feature where every user can report bug?"

This also **closes the loop on v1.22 Phase 72 UX-BADGE-01**: backend already stores bug reports in `data/bug_reports/` (hence the admin badge counter). What's missing is the user-side submission surface.

## Solution

### Frontend

Add a "Сообщить об ошибке" entry point. Best placement options:
- Settings menu (gear icon) — least intrusive, matches existing pattern.
- Swipe-up from cart panel footer.
- Long-press on any product card → context menu.

Start with **settings menu entry**. Implementation:

```jsx
<button onClick={() => setBugReportOpen(true)}>
  🐛 Сообщить об ошибке
</button>
```

Modal sheet opens with:
- `<textarea>` for free-form description (required, 10-2000 chars).
- Optional "Что-то не так с товаром?" product picker (pre-fills product_id if user was looking at a specific card).
- Optional checkbox: "Приложить снимок экрана" (future — skip in MVP).
- Submit button → `POST /api/bug-report` → toast "Спасибо, отправлено!"

Metadata auto-captured from the client (no user input):
- `telegram_user_id` (from initData HMAC).
- `miniapp_version` (from Vite build).
- `user_agent`, `viewport_size`, `current_route`, `products_count`.
- `last_cart_attempt` metadata (if recent).
- `sourceFreshness` snapshot (the same stale-banner context).

### Backend

New `/api/bug-report` endpoint:

```python
@app.post("/api/bug-report")
async def submit_bug_report(req: BugReportRequest, request: Request):
    _validate_user_header(request, req.user_id)
    # Persist to data/bug_reports/{timestamp}-{user_hash}.json
    # Auto-enrich with server-side context:
    #   - pool_snapshot (v1.21)
    #   - last_cycle_age_s
    #   - xray_drift (v1.21)
    #   - recent cart_events for this user
```

File shape:
```json
{
  "ts": "2026-05-13T01:20:00Z",
  "user_id": "hashed",
  "reason": "user text",
  "product_id": 12345 | null,
  "client_ctx": { "version": "...", "viewport": "...", "route": "..." },
  "server_ctx": { "pool": {...}, "last_cycle_age_s": ..., "xray_drift": {...} }
}
```

### Wiring

- **v1.22 Phase 72** already added `Bug Reports (N)` admin badge. On submit, the badge counter increments automatically (backend recomputes on next `/admin/status` hit).
- **v1.16** already has `/admin/bug-reports` JSON viewer endpoint. Click on badge opens it.

### Security / rate limiting

- Rate limit: max 5 reports per user per hour. Captured in-memory like `_DEEP_LAST_HIT`.
- Max body size: 2 KB text.
- HTML-escape the reason text when rendering in admin.

### Optional v1.23+: richer admin UI

v1.22 Phase 72 shipped the badge + link. The `/admin/bug-reports` JSON view is adequate but basic. A future phase could add a proper admin UI with filter/sort/mark-read.

## Acceptance

- [ ] MiniApp has a visible, discoverable "Сообщить об ошибке" entry point (settings menu).
- [ ] Submitting a report produces a file in `data/bug_reports/` on EC2.
- [ ] Admin badge (v1.22 Phase 72) increments on next `/admin/status` poll.
- [ ] Rate limit enforced (5/hour/user).
- [ ] Auto-captured server context includes pool snapshot + xray_drift + last_cycle_age_s (gives operator useful diagnosis context without user input).
- [ ] Live MCP test: submit a report, verify admin badge counts up.

## Candidate for

v1.23 — natural extension of v1.22 Phase 72 (closes the submit-side loop). Scope: ~60 LOC backend (endpoint + persistence + validation) + ~100 LOC frontend (modal + form + settings menu entry). Medium-sized phase.
