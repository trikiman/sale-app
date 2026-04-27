# Deployment Checklist — Live Verification Results

- **Run timestamp**: 2026-04-26 23:11 UTC
- **Source commit**: `b165b35` (HEAD of `main` at run start)
- **Environment**: production
  - Vercel: https://vkusvillsale.vercel.app/
  - EC2 backend: `ubuntu@13.60.174.46:8000` (SSH key rejected — see "SSH access" below)
- **Child sessions used**: 11 (out of 11 max)
- **Wall-clock**: ~25 minutes (parallel) — autonomous portion completed in <40 min target

## Summary

| Total | ✅ passed | ❌ failed | 🙋 needs-human | ⏭️ skipped |
|-------|-----------|-----------|----------------|------------|
| **441** | **320** (72.6%) | **11** | **105** | **5** |

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
| C1 | 36 | 27 | 1 | 6 | 2 | 145 |
| C2 | 46 | 43 | 0 | 3 | 0 | 548 |
| C3 | 48 | 33 | 7 | 8 | 0 | 423 |
| C4 | 50 | 47 | 0 | 3 | 0 | 617 |
| C5 | 42 | 35 | 0 | 6 | 1 | 600 |
| C6 | 38 | 31 | 2 | 4 | 1 | 869 |
| C7 | 42 | 17 | 0 | 24 | 1 | 450 |
| C8 | 30 | 7 | 1 | 22 | 0 | 240 |
| C9 | 45 | 36 | 0 | 9 | 0 | 420 |
| C10 | 30 | 12 | 0 | 18 | 0 | 210 |
| C11 | 34 | 32 | 0 | 2 | 0 | 600 |

### Distribution check (balance constraint)

- **mean** items/child: 40.09
- **stdev** items/child: 6.99
- **ratio** (stdev/mean): **0.174** — required `< 0.30` ✅

## Per-section rollup

| Section | Total | ✅ | ❌ | 🙋 | ⏭️ |
|---------|-------|----|----|-----|----|
| QS-* | 5 | 2 | 0 | 3 | 0 |
| §0 | 16 | 10 | 1 | 3 | 2 |
| §1 | 10 | 7 | 0 | 3 | 0 |
| §2 | 94 | 76 | 7 | 11 | 0 |
| §3 | 87 | 75 | 1 | 10 | 1 |
| §4 | 12 | 0 | 0 | 12 | 0 |
| §5 | 13 | 12 | 0 | 0 | 1 |
| §6 | 8 | 7 | 0 | 0 | 1 |
| §7 | 9 | 8 | 0 | 1 | 0 |
| §8 | 14 | 4 | 0 | 10 | 0 |
| §9 | 15 | 14 | 0 | 1 | 0 |
| §10 | 5 | 0 | 0 | 5 | 0 |
| §11 | 1 | 0 | 0 | 1 | 0 |
| §13 | 6 | 4 | 0 | 2 | 0 |
| §14 | 6 | 5 | 1 | 0 | 0 |
| §15 | 8 | 8 | 0 | 0 | 0 |
| §16 | 12 | 12 | 0 | 0 | 0 |
| §17 | 14 | 14 | 0 | 0 | 0 |
| §18 | 10 | 10 | 0 | 0 | 0 |
| §19 | 10 | 5 | 0 | 5 | 0 |
| §20 | 14 | 3 | 1 | 10 | 0 |
| §21 | 55 | 29 | 0 | 26 | 0 |
| §12 sign-off | 17 | 15 | 0 | 2 | 0 |

## ❌ Failures (11)

| Child | Item | Evidence | Root cause hypothesis |
|-------|------|----------|------------------------|
| C1 | **0.2.2** | EC2_SSH_KEY_PEM rejected by 13.60.174.46 — Permission denied (publickey). Key fingerprint SHA256:mtpiVyppCdM9ZzE5OY3HOEkQ7M56VSJDEKroRLjbHaI does not match server. | Org-secret EC2_SSH_KEY_PEM doesn't match the key on EC2 — re-upload correct PEM |
| C3 | **2.7.3** | ADMIN_TOKEN rejected: /admin/status with token -> 403 Invalid admin token on both Vercel and EC2 direct | ADMIN_TOKEN org-secret value mismatch with backend ADMIN_TOKEN env |
| C3 | **2.7.4** | ADMIN_TOKEN rejected (403); code confirms response has scrapers,data,techCookies,sourceFreshness,cycleState,cartDiagnostics but cant verify live | Same — ADMIN_TOKEN auth rejected on protected endpoints |
| C3 | **2.7.5** | ADMIN_TOKEN rejected for token-protected scrapers (green,red,yellow,merge,login -> 403); categories/catalog-discovery work without token | Same — ADMIN_TOKEN auth rejected on token-protected scrapers |
| C3 | **2.7.9** | ADMIN_TOKEN rejected for /admin/status (403); code confirms cartDiagnostics with recentAttempts,pendingCount,lastResolvedAt at L3107-3114 | Same — ADMIN_TOKEN rejected on /admin/status detail |
| C3 | **2.7.10** | POST /api/admin/tech-login -> 403 Invalid admin token; _require_token blocks access | Same — ADMIN_TOKEN rejected on /admin/tech-login |
| C3 | **2.7.11** | All three endpoints (proxy-stats, proxy-history, proxy-logs) -> 403 Invalid admin token; all require _require_token | Same — ADMIN_TOKEN rejected on /admin/proxy-stats|history|logs |
| C3 | **2.7.12** | POST /admin/proxy-refresh -> 403 Invalid admin token; _require_token blocks access | Same — ADMIN_TOKEN rejected on /admin/proxy-refresh |
| C6 | **3.14.1–3.14.4** | SSE EventSource readyState=0 (CONNECTING) after 6s via Vercel; never fires onopen. Vercel serverless may not support long-lived SSE. Backend code at main.py:922 is correct | Vercel serverless does not support long-lived SSE — EventSource never opens. Either run SSE direct from EC2 or remove SSE dependency. |
| C6 | **14.5** | No test_history_search_contract in tests/. grep returned no matches. Only test_sale_history_repair.py exists | Pytest test_history_search_contract not present in `tests/` — either was never landed or moved/renamed |
| C8 | **20.13** | GET http://13.60.174.46:8000/api/health/scheduler → 404 Not Found; endpoint not implemented in backend/main.py (nice-to-have per checklist) | /api/health/scheduler endpoint not implemented (deferred per known carry-over list) |

## 🙋 Manual followup required (105)

### SSH access (EC2 key rejected) (56 items)

- C1 **0.2.1**
- C1 **1.5**
- C6 **7.2**
- C7 **10.16**
- C7 **10.17**
- C7 **11.1-11.9**
- C7 **19.9**
- C8 **QS-3**
- C8 **QS-4**
- C8 **8.3**
- C8 **8.3b**
- C8 **8.3c**
- C8 **8.4**
- C8 **8.5**
- C8 **8.6**
- C8 **8.8**
- C8 **8.9**
- C8 **8.10**
- C8 **8.11**
- C8 **20.1**
- C8 **20.2**
- C8 **20.3**
- C8 **20.4**
- C8 **20.7**
- C8 **20.8**
- C8 **20.10**
- C8 **20.11**
- C8 **20.12**
- C8 **20.14**
- C9 **9.15**
- C9 **21.1.1**
- C9 **21.1.2**
- C9 **21.1.3**
- C9 **21.1.4**
- C9 **21.1.5**
- C9 **21.1.6**
- C9 **21.1.7**
- C9 **21.4.5**
- C10 **21.2.1**
- C10 **21.2.2**
- C10 **21.2.3**
- C10 **21.2.4**
- C10 **21.2.5**
- C10 **21.2.6**
- C10 **21.2.7**
- C10 **21.2.8**
- C10 **21.2.9**
- C10 **21.3.1**
- C10 **21.3.2**
- C10 **21.3.3**
- C10 **21.3.4**
- C10 **21.3.6**
- C10 **21.5.1**
- C10 **21.5.2**
- C10 **21.5.6**
- C11 **Production services**

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

### Other (10 items)

- C1 **1.8**
- C1 **1.9**
- C3 **2.4.4**
- C3 **2.4.5**
- C3 **2.6.6**
- C3 **2.6.7**
- C3 **2.6.8**
- C7 **QS-5**
- C7 **4.11**
- C7 **19.4**

### Real SMS delivery required (6 items)

- C2 **2.3.5**
- C2 **2.3.6**
- C2 **2.3.7**
- C5 **3.10.2–3.10.19**
- C6 **3.11.2–3.11.24**
- C7 **10.1-10.13**

### Inventory state required (sold-out/новинки) (2 items)

- C4 **3.4.7**
- C6 **3.16.1–3.16.5**

### Live e2e (valid cookies.json) (1 items)

- C3 **2.4.13**

### Stress-test tools (hey/ab) not available (1 items)

- C10 **21.5.5**

## ⏭️ Skipped (5)

- C1 **0.3.1** — _No Chrome DevTools MCP server configured in this child session_
- C1 **0.4.1** — _hey/ab not installed_
- C5 **3.6.7** — _Checklist notes N/A currently — no uncategorized products exist to trigger Новинки chip on main category row_
- C6 **6.8** — _No modal currently open to verify backdrop coverage; requires user interaction to trigger modal/drawer_
- C7 **5.11** — _.agent/scripts/checklist.py does not exist in repo_

## SSH access (blocking ~80 needs-human items)

All §8/§20 systemctl checks, §21.1/21.2/21.3/21.5 xray config + lifecycle live checks, §9.15 catalog parity report, and parts of §21.7 were blocked by SSH key mismatch:

```
$ ssh -i $EC2_SSH_KEY_PEM ubuntu@13.60.174.46
ubuntu@13.60.174.46: Permission denied (publickey).

Key fingerprint of EC2_SSH_KEY_PEM org-secret: SHA256:mtpiVyppCdM9ZzE5OY3HOEkQ7M56VSJDEKroRLjbHaI
```

**Resolution**: re-upload the correct PEM (matching the public key on `13.60.174.46:~/.ssh/authorized_keys`) to the org secret `EC2_SSH_KEY_PEM`, then re-run C8/C9/C10 scopes.

## ADMIN_TOKEN auth (blocking 7 admin endpoints)

All §2.7.3/4/5/9/10/11/12 admin endpoints returned `403 Invalid admin token` on both Vercel and EC2 with the org-secret `ADMIN_TOKEN` value. Code path is correct (`_require_token`); the secret value either doesn't match production or has been rotated.

**Resolution**: rotate or fix the org-secret `ADMIN_TOKEN` to match the backend's configured value, then re-run C3 §2.7.* and §15.*.

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
- **Wall-clock (parallel)**: ~25 min (longest child = max(C1=145, C2=548, C3=423, C4=617, C5=600, C6=869, C7=450, C8=240, C9=420, C10=210, C11=600) = 869s)
- **Cumulative agent time**: 5122s
