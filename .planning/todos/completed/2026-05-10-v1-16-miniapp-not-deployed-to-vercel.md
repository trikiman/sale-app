---
created: 2026-05-10T16:26:37Z
title: v1.16 MiniApp bug-report UI not deployed to Vercel
area: ui
files:
  - miniapp/src/BugReportPanel.jsx
  - miniapp/src/consoleBuffer.js
  - miniapp/src/App.jsx:40 (import BugReportPanel)
  - miniapp/src/App.jsx:1710 (header-pill entry point)
  - miniapp/src/App.jsx:2102 (BugReportPanel render)
---

## Problem

Discovered 2026-05-10 during v1.16 UAT (commit b1d3b04). The deployed Vercel bundle https://vkusvillsale.vercel.app/assets/index-DFayy0r0.js contains NO references to BugReportPanel, setShowBugReport, consoleBuffer, or the bug emoji. Bundle is 259876 bytes.

Local HEAD builds fine (npm run build ran, produced dist/assets/index-DsukKGON.js, different hash). Local MiniApp unit tests pass 7/7. So the v1.16 feature code exists and builds — it just never shipped to Vercel.

Simulated auth state via fetch-hijack in Chrome DevTools MCP to verify: authenticated header shows Logout + Cart + History + Theme + Admin, but no bug-report pill. Confirms absence, not browser issue.

Likely cause: Vercel auto-deploy hook was pointed at a branch that did not include the v1.16 commits (f4f4ae5 phase 60), or the deploy failed silently. Same pattern as v1.16 backend not on EC2 (see v1-16-backend-not-deployed-to-ec2 todo).

## Solution

TBD. Two paths aligned with the backend decision:

1. Deploy current HEAD miniapp to Vercel. vite build is green, so just push to the branch Vercel watches. Verify post-deploy by repeating the Chrome DevTools auth-hijack test and confirming 🐞 button appears.
2. Close v1.16 frontend as not-deployed alongside backend.

If going with path 1, also verify end-to-end from the DevTools MCP session once deploy completes:
- Bug-report button visible when authenticated
- Clicking opens BugReportPanel form
- Submitting without photo saves .json on EC2 (requires backend also deployed)
- Submitting with small photo saves .json + .jpg
- consoleBuffer captures console.error during session, attached to submission

Related: v1-16-backend-not-deployed-to-ec2, v1-16-admin-html-bug-reports-badge-missing.
