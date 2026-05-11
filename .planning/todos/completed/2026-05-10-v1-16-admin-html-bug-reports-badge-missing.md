---
created: 2026-05-10T16:26:37Z
title: v1.16 admin.html missing Bug Reports (N) badge
area: ui
priority: P2
files:
  - backend/admin.html (zero references to bugReports/bug_reports)
  - backend/main.py:4450 (backend exposes bugReports.count + bugReports.unread)
  - .planning/ROADMAP.md Phase 61 Success Criterion 3
---

## Problem

v1.16 Phase 61 Success Criterion 3 says "Existing admin dashboard surfaces a Bug Reports (N) badge driven by bug_reports_unread_count". The backend side was shipped correctly: /admin/status payload exposes bugReports.count and bugReports.unread. But the UI side was never written.

grep on backend/admin.html shows zero occurrences of "bugReports" or "bug_reports". The admin dashboard renders proxy-badge, cart-pending-count, etc., but there is no Bug Reports badge. A v1.16 gap that exists in the code at HEAD, not just an EC2 deploy gap.

Verified 2026-05-10: committed HEAD 68623c3 has the backend counters but no admin.html changes. Even after EC2 is redeployed to v1.16, the badge will not appear.

Mirrors the pattern already present for other counts:
- proxy-badge (line 426)
- proxy-count (line 427)
- cart-pending-count (line 407)
- log-count (line 500)

## Solution

Add about 20 lines to backend/admin.html:
1. Add a span "bug-reports-badge" (class badge, hidden by default) near the proxy-badge in the status row.
2. In applyStatus(data) (line 559) read data.bugReports and .unread, show badge only if greater than 0, set text "Bug Reports (N)".
3. Optionally click-to-open the existing /admin endpoint (we have GET /api/admin/bug-reports already).

Small cosmetic change, no new backend work required. Map to v1.16 gap-closure phase or treat as follow-up issue.
