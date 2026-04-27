# Deployment Checklist — Live Verification Results

- **Run timestamp**: 2026-04-27 01:47 UTC
- **Source commit**: `b165b35` (initial run) + `62314a3` (merged to main) + 2026-04-27 rerun
- **Environment**: production
  - Vercel: https://vkusvillsale.vercel.app/
  - EC2 backend: `ubuntu@13.60.174.46:8000` (SSH restored 2026-04-27; new key `SHA256:3AoGUmtK1Zf9UaJ56TfYxLXKVWsH/VVThSo3PqDduXs scraper-ec2`)
- **Child sessions used**: 11 (out of 11 max)
- **Wall-clock**: ~25 minutes initial parallel run + ~15 minutes re-verification sweep (inline from parent)
- **Re-run note**: this report was regenerated on 2026-04-27 after SSH key + ADMIN_TOKEN + correct header (`X-Admin-Token`) were reconciled. 66 items that were previously blocked by infra gaps were re-verified inline from the parent session; evidence strings marked `[RE-RUN 2026-04-27]`.

## Summary

| Total | ✅ passed | ❌ failed | 🙋 needs-human | ⏭️ skipped |
|-------|-----------|-----------|----------------|------------|
| **441** | **374** (84.8%) | **4** | **57** | **6** |

### Delta vs 2026-04-26 initial run

| | Initial | Re-run | Δ |
|-|---------|--------|---|
| ✅ passed | 320 | 374 | **+54** |
| ❌ failed | 11 | 4 | **-7** |
| 🙋 needs-human | 105 | 57 | **-48** |
| ⏭️ skipped | 5 | 6 | **+1** |

## Scope per child

| Child | Items | Title | Tooling |
|-------|-------|-------|---------|
| C1 | 36 | CLI/build/infra + Vercel sanity | shell + npm + python + curl |
| C2 | 46 | Backend curl: public + favorites + auth | curl + jq |
| C3 | 48 | Backend curl: cart + linking + history + admin (+§15 catalog) | curl + jq + ADMIN_TOKEN |
| C4 | 50 | Frontend Chrome: load + cards + cart UI + pending contract (+§17) | Chrome via CDP |
| C5 | 42 | Frontend Chrome: filters + drawer + categories (+§13) | Chrome via CDP |
| C6 | 38 | Frontend Chrome: login + edge + responsive + perf + history search (+§14) | Chrome + curl |
| C7 | 42 | Telegram bot + security + e2e + stress + cart truth (+§19) | curl + Telegram |
| C8 | 30 | EC2 SSH: systemd + standalone deployment | ssh + systemctl |
| C9 | 45 | EC2 SSH: scrapers + freshness + xray lifecycle/rotation/recovery (+§16) | ssh + admin API |
| C10 | 30 | EC2 SSH: xray config + geo + egress + timeouts | ssh + jq + verify_v1_18.sh |
| C11 | 34 | Cross-refs + pytest + cart errors + final §12 sign-off (+§18, §21.8, §21.9) | pytest + cross-ref aggregation (run by parent) |

## Items-per-child distribution

| Child | Items | ✅ | ❌ | 🙋 | ⏭️ | Elapsed (s) |
|-------|-------|----|----|-----|----|-------------|
| C1 | 36 | 31 | 0 | 3 | 2 | 145 |
| C2 | 46 | 43 | 0 | 3 | 0 | 548 |
| C3 | 48 | 39 | 0 | 9 | 0 | 423 |
| C4 | 50 | 47 | 0 | 3 | 0 | 617 |
| C5 | 42 | 35 | 0 | 6 | 1 | 600 |
| C6 | 38 | 32 | 2 | 3 | 1 | 869 |
| C7 | 42 | 17 | 0 | 23 | 2 | 450 |
| C8 | 30 | 25 | 2 | 3 | 0 | 240 |
| C9 | 45 | 43 | 0 | 2 | 0 | 420 |
| C10 | 30 | 29 | 0 | 1 | 0 | 210 |
| C11 | 34 | 33 | 0 | 1 | 0 | 600 |

### Distribution check (balance constraint)

- **mean** items/child: 40.09
- **stdev** items/child: 6.99
- **ratio** (stdev/mean): **0.174** — required `< 0.30` ✅

## Per-section rollup

| Section | Total | ✅ | ❌ | 🙋 | ⏭️ |
|---------|-------|----|----|-----|----|
| QS-* | 5 | 3 | 0 | 2 | 0 |
| §0 | 16 | 12 | 0 | 2 | 2 |
| §1 | 10 | 9 | 0 | 1 | 0 |
| §2 | 94 | 82 | 0 | 12 | 0 |
| §3 | 87 | 75 | 1 | 10 | 1 |
| §4 | 12 | 0 | 0 | 12 | 0 |
| §5 | 13 | 12 | 0 | 0 | 1 |
| §6 | 8 | 7 | 0 | 0 | 1 |
| §7 | 9 | 9 | 0 | 0 | 0 |
| §8 | 14 | 14 | 0 | 0 | 0 |
| §9 | 15 | 14 | 0 | 1 | 0 |
| §10 | 5 | 0 | 0 | 5 | 0 |
| §11 | 1 | 0 | 0 | 0 | 1 |
| §13 | 6 | 4 | 0 | 2 | 0 |
| §14 | 6 | 5 | 1 | 0 | 0 |
| §15 | 8 | 8 | 0 | 0 | 0 |
| §16 | 12 | 12 | 0 | 0 | 0 |
| §17 | 14 | 14 | 0 | 0 | 0 |
| §18 | 10 | 10 | 0 | 0 | 0 |
| §19 | 10 | 5 | 0 | 5 | 0 |
| §20 | 14 | 10 | 2 | 2 | 0 |
| §21 | 55 | 53 | 0 | 2 | 0 |
| §12 sign-off | 17 | 16 | 0 | 1 | 0 |

## ❌ Failures (4)

| Child | Item | Evidence | Root cause hypothesis |
|-------|------|----------|------------------------|
| C6 | **3.14.1–3.14.4** | SSE EventSource readyState=0 (CONNECTING) after 6s via Vercel; never fires onopen. Vercel serverless may not support long-lived SSE. Backend code at main.py:922 is correct | — |
| C6 | **14.5** | No test_history_search_contract in tests/. grep returned no matches. Only test_sale_history_repair.py exists | Pytest test_history_search_contract not present in `tests/` — either was never landed or moved/renamed |
| C8 | **20.13** | [RE-RUN 2026-04-27] GET /api/health/scheduler → 404 {'detail':'Not Found'} on EC2 backend (openapi.json has no /api/health* routes). Nice-to-have per §12 footer — carry-over. | /api/health/scheduler endpoint not implemented (deferred per known carry-over list) |
| C8 | **20.14** | [RE-RUN 2026-04-27] No cron for jpg cleanup — only /home/ubuntu/saleapp/scripts/xray_healthcheck.sh is scheduled. Stale *.jpg files from March still present in data/ (e.g. login_clean2_05ab0de1_captch | No jpg cleanup cron configured; stale *.jpg files from March remain in data/. Only cron is xray_healthcheck. Nice-to-have. |

## 🙋 Manual followup required (57)

### Telegram bot interaction (no MCP) (16 items)

- C1 **0.2.4**
- C5 **3.13.1–3.13.5**
- C5 **13.5**
- C5 **13.6**
- C7 **4.1**
- C7 **4.2**
- C7 **4.3**
- C7 **4.4**
- C7 **4.5**
- C7 **4.6**
- C7 **4.7**
- C7 **4.8**
- C7 **4.9**
- C7 **4.10**
- C7 **4.12**
- C11 **Telegram bot fully working**

### Authenticated session required (13 items)

- C1 **0.2.3**
- C3 **2.4.1**
- C3 **2.4.3**
- C4 **3.4.5**
- C4 **3.4.6**
- C5 **3.9.7**
- C5 **3.10.1**
- C6 **3.12.1–3.12.4**
- C7 **10.14**
- C7 **10.15**
- C7 **19.1**
- C7 **19.2**
- C7 **19.3**

### Other (13 items)

- C1 **1.9**
- C3 **2.4.4**
- C3 **2.4.5**
- C3 **2.4.13**
- C3 **2.6.6**
- C3 **2.6.7**
- C3 **2.6.8**
- C7 **QS-5**
- C7 **4.11**
- C7 **19.4**
- C8 **20.12**
- C9 **9.15**
- C10 **21.5.5**

### Real SMS delivery required (7 items)

- C2 **2.3.5**
- C2 **2.3.6**
- C2 **2.3.7**
- C3 **2.7.10**
- C5 **3.10.2–3.10.19**
- C6 **3.11.2–3.11.24**
- C7 **10.1-10.13**

### Database CLI not available on EC2 (3 items)

- C7 **10.16**
- C7 **10.17**
- C7 **19.9**

### Inventory state required (2 items)

- C4 **3.4.7**
- C6 **3.16.1–3.16.5**

### Disruptive / operator-only checks (2 items)

- C8 **QS-4**
- C9 **21.1.7**

### Cross-platform (Windows) — can't verify from EC2 (1 items)

- C8 **20.11**

## ⏭️ Skipped (6)

- C1 **0.3.1** — _No Chrome DevTools MCP server configured in this child session_
- C1 **0.4.1** — _hey/ab not installed_
- C5 **3.6.7** — _Checklist notes N/A currently — no uncategorized products exist to trigger Новинки chip on main category row_
- C6 **6.8** — _No modal currently open to verify backdrop coverage; requires user interaction to trigger modal/drawer_
- C7 **5.11** — _.agent/scripts/checklist.py does not exist in repo_
- C7 **11.1-11.9** — _[RE-RUN 2026-04-27] Stress / edge-case scenarios — manual by design per checklist footer_

## 2026-04-27 re-run coverage

After the initial run surfaced infrastructure blockers, the following fixes were applied and 66 items re-verified inline:

1. **SSH key rotated** — new key (`SHA256:3AoGUmtK1Zf9UaJ56TfYxLXKVWsH/VVThSo3PqDduXs scraper-ec2`) uploaded to `EC2_SSH_KEY_PEM`; parent session reformatted the one-line PEM into proper multi-line format and connected successfully to `ubuntu@13.60.174.46`.
2. **ADMIN_TOKEN reconciled** — the correct production value is 9 chars (`122662Rus`); org secret was 21 chars. More importantly, the backend expects `X-Admin-Token: <token>` request header, not `Authorization: Bearer <token>`. C3's original run used Bearer, which is why the 7 admin endpoints returned 403.

Re-run outcome (66 items):

- **54 now passed** (SSH service health, xray config, admin endpoints, cookies, logs, routing, probes)
- **9 still needs-human** (tech-login OTP, DB queries needing sqlite3, disruptive kill -9 tests, Windows cross-platform, catalog parity v1.9 report)
- **2 now failed** (`20.13` /api/health/scheduler 404; `20.14` jpg cleanup cron absent — both nice-to-have per §12 footer)
- **1 moved to skipped** (`11.1-11.9` stress cases — manual by design)

## Time elapsed

- C1: 145s
- C2: 548s
- C3: 423s
- C4: 617s
- C5: 600s
- C6: 869s
- C7: 450s
- C8: 240s
- C9: 420s
- C10: 210s
- C11: 600s
- **Wall-clock (parallel, initial run)**: ~25 min (longest child = 869s)
- **Cumulative agent time (initial)**: 5122s
- **Re-run (inline from parent)**: ~15 min
