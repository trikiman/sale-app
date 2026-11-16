---
gsd_state_version: 1.0
milestone: v1.30
milestone_name: Green Tag Uptime
status: Phase 97 complete
stopped_at: milestone planned; next step is `/gsd-plan-phase 94`
last_updated: "2026-11-16T10:58:02.957Z"
progress:
  total_phases: 4
  completed_phases: 3
  total_plans: 6
  completed_plans: 6
  percent: 78
---

*Session checkpoint 2026-10-19 (ops review). Milestone v1.26 remains shipped/archived. Operator milestone "Telegram Favorites Notifications" verified end-to-end on prod and closed as working. Green-уценка confirmed morning-only (VkusVill stock reality, not a bug). RU VLESS pool degraded to 1/5 — scraping survives on the manual trojan seed floor; pool replenishment is the top candidate for the next milestone.*

## Blockers

- **VLESS pool 0/5 healthy** (diagnosed 2026-11-17 00:15, card `t_742784ed`).
  Fetch is healthy: `parsed=1587, geo ru=422, uniq host:port=231`; TCP pre-filter
  `102/152 reachable`. Then **xray probe fails on all 152** (`probe_error=102,
  tcp_unreachable=50`) → pool 0. So the bottleneck is the **tunnel**, not the
  sources: TCP opens but no node proxies. Probe target is already correct
  (`https://vkusvill.ru/favicon.ico`). Next hypotheses: probe timeout too tight
  for reality nodes from Amsterdam; flow/SNI/fingerprint not passed verbatim;
  nodes demand RU egress. Green cycles survive on URnetwork (`urnetwork ok`).
  Replenishing is a vless-hunt problem, not saleapp code — do not "fix" it here.
- **Telegram notifications dead**: bot not polled server-side, `/admin/test-alert`
  → `no_admin_chat_ids`; needs SSH (port 22 blocked by DPI).

## Session

**Last session:** 2026-11-16 (v1.30: phases 94, 95, 97 closed; Phase 96 soak running)
**Stopped at:** soak in progress (168 h, verdict 2026-11-23); instrumentation + daily cron live
**Resume file:** None
