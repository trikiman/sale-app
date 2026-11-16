---
phase: 94
plan: 94-03
title: Alerts for the two deadly green states
status: complete
---

# 94-03 — Summary

`/admin/status.data.greenAlerts` reports the two states that produced the false
zeros:

- `green_snapshot_stale:<Nm>` — snapshot older than 2× the green interval
  (90 min at the current 45-minute threshold);
- `green_zero_with_live_count` — `green == 0` while `greenLiveCount > 0`;
- `null` when healthy — observed live (`greenAlerts=None`).

**Open sub-item:** Telegram delivery of these alerts is not wired. The bot
`@green_price_monitor_bot` is not polled server-side (`getUpdates` returns
`ok:true` with no webhook), `/admin/test-alert` answers `no_admin_chat_ids`, and
adding the chat id needs SSH, which DPI blocks. The status endpoint is the
working delivery path until then; recorded honestly rather than claimed.
