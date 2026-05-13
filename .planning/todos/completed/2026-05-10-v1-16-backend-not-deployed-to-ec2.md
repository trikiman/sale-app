---
created: 2026-05-10T16:26:37Z
title: v1.16 backend endpoints not deployed to EC2
area: api
files:
  - backend/main.py:4166 (Bug Reports v1.16 section)
  - backend/main.py:4235 (POST /api/bug-reports)
  - backend/main.py:4344 (GET /api/admin/bug-reports)
---

## Problem

Discovered 2026-05-10 during v1.16 UAT (commit b1d3b04). Production EC2 at 13.60.174.46 returns HTTP 404 for both POST /api/bug-reports and GET /api/admin/bug-reports. The /api/products response does not include the bugReports keys (count, unread) that main.py:4450 adds at HEAD.

Meaning: EC2 is on a revision older than 7f59f1a (phase 59 commit, 2026-04-28) even though STATE.md says v1.16 shipped that day. Auto-deploy webhook was supposed to fire but did not, or it fired against a branch EC2 does not pull.

Update 2026-05-10 19:00: EC2 is actually on v1.20 branch a7ab226 (independently developed on EC2). So EC2 is NOT behind on v1.16 in time, it is on a DIFFERENT branch where the bug-reports commits never landed.

## Solution

TBD. Two paths:

1. Merge v1.16 backend commits (7f59f1a phase 59 + 68623c3 phase 61 status wiring) into the EC2 branch/main, then deploy. This is the "we want bug reports feature live" path.
2. Close v1.16 as "local work not deployed, superseded by v1.17-v1.20 which took priority". Document the gap and move on.

Also affects GET /api/admin/bug-reports (phase 61) — same root cause, same fix. Related todos:
- v1-16-admin-html-bug-reports-badge-missing (UI piece of phase 61 that was never written, needed regardless of deploy path)
- v1-16-miniapp-not-deployed-to-vercel (frontend side of same issue)
