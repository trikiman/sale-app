---
phase: 2
plan: 1
title: "Add getAuthHeaders() helper and update all fetch calls"
wave: 1
depends_on: ["01-01"]
files_modified:
  - miniapp/src/api.js
  - miniapp/src/App.jsx
  - miniapp/src/CartPanel.jsx
requirements:
  - SEC-08
autonomous: true
---

<objective>
Create a centralized `getAuthHeaders(userId)` function that returns Telegram initData auth when available, falling back to X-Telegram-User-Id. Replace all 10 hardcoded header locations in App.jsx and CartPanel.jsx.
</objective>

<tasks>

<task id="2.1.1">
<title>Create miniapp/src/api.js with getAuthHeaders</title>
<action>
Create a new utility that detects Telegram MiniApp environment and returns appropriate auth headers.
</action>
<acceptance_criteria>
- miniapp/src/api.js exports getAuthHeaders function
- Returns `Authorization: tma <initData>` when Telegram.WebApp.initData is available
- Falls back to `X-Telegram-User-Id` header for guest/browser
</acceptance_criteria>
</task>

<task id="2.1.2">
<title>Update App.jsx fetch calls to use getAuthHeaders</title>
<action>
Replace all 6 X-Telegram-User-Id header occurrences in App.jsx with getAuthHeaders(userId).
</action>
<acceptance_criteria>
- App.jsx imports getAuthHeaders from ./api
- All 6 fetch calls use getAuthHeaders(userId) for headers
- No hardcoded X-Telegram-User-Id remains in App.jsx
</acceptance_criteria>
</task>

<task id="2.1.3">
<title>Update CartPanel.jsx fetch calls to use getAuthHeaders</title>
<action>
Replace all 4 X-Telegram-User-Id header occurrences in CartPanel.jsx with getAuthHeaders(userId).
</action>
<acceptance_criteria>
- CartPanel.jsx imports getAuthHeaders from ./api
- All 4 fetch calls use getAuthHeaders(userId) for headers
- No hardcoded X-Telegram-User-Id remains in CartPanel.jsx
</acceptance_criteria>
</task>

</tasks>

<verification>
1. `npm run build` succeeds in miniapp/
2. No hardcoded X-Telegram-User-Id remains in App.jsx or CartPanel.jsx
3. getAuthHeaders returns correct headers for both paths
</verification>

<must_haves>
- Centralized auth header function
- Telegram initData sent when available
- Guest/browser fallback preserved
- No breaking changes
</must_haves>
