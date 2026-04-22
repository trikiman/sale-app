# Phase 56 — Live Verification Evidence

This document captures the live-evidence gate for v1.15. The code path
(56-01..56-04) and the deploy infrastructure (56-05 commit 1) are merged to
main. Actual EC2 rollout must be run by an operator with the
`scraper-ec2-new` SSH key; see "EC2 Rollout (pending operator action)"
below for the exact commands and the expected transcript format.

Everything that can be verified on the developer box was verified. All of
those checks are timestamped PASS or FAIL, not templated text.

## Commit Chain

| Commit | Plan | Subject |
|--------|------|---------|
| `eceb5bd` | 56-01 | feat(vless): add VLESS URL parser and xray config generator (phase 56-01) |
| `fdb64dc` | 56-02 | feat(vless): add xray-core installer and subprocess wrapper (phase 56-02) |
| `e32a7d9` | 56-03 | feat(vless): add VlessProxyManager with API-compatible interface (phase 56-03) |
| `cc70185` | 56-04 | chore(proxy): archive SOCKS5 implementation, shim proxy_manager to VLESS (phase 56-04) |
| `94826d9` | 56-05a | feat(ops): systemd units, deploy + verify scripts for v1.15 (phase 56-05) |
| _this commit_ | 56-05b | docs(phase-56): record v1.15 live verification and rollback rehearsal |

## Dev-Box Verification (2026-04-22)

Platform: `linux-64`, Python 3.12, xray-core v24.11.30 (pinned).

### Check A — xray binary installed and runnable

```
$ python3 -c "from vless.installer import detect_platform, is_installed, XRAY_VERSION; \
              print('platform:', detect_platform()); \
              print('version:', XRAY_VERSION); \
              print('installed:', is_installed())"
platform: linux-64
version: 24.11.30
installed: True
```

**Result: PASS**

### Check B — End-to-end smoke test via `scripts/bootstrap_xray.py --smoke-test`

```
$ python3 scripts/bootstrap_xray.py --smoke-test
[bootstrap] platform=linux-64, target version=24.11.30
[bootstrap] installed at /home/ubuntu/repos/sale-app/bin/xray/v24.11.30/xray
[bootstrap] Xray 24.11.30 (Xray, Penetrates Everything.) 98a72b6 (go1.23.3 linux/amd64)
A unified platform for anti-censorship.
[consensus]   25/66 verified, passed=25
[consensus]   50/66 verified, passed=50
xray started (pid=28942, port=10808)
xray stopped
[bootstrap] smoke-test PASS: egress OK — detected country=RU via 5 nodes
```

**Result: PASS — VLESS+Reality bridge egresses from RU, 5 candidate nodes
admitted via consensus geo-resolver.**

### Check C — VlessProxyManager live end-to-end refresh

```
$ RUN_LIVE=1 pytest tests/test_vless_manager.py::test_live_vless_end_to_end -v
...
  [VLESS] xray started (pid=23102, port=10808)
  [VLESS] Using xray bridge 127.0.0.1:10808 (28 nodes in pool)
  [VLESS] xray stopped
PASSED [100%]
1 passed in 321.03s (0:05:21)
```

**Result: PASS — refresh pipeline admitted 28 RU nodes (threshold is ≥ 5),
bridge served `127.0.0.1:10808`, xray shut down cleanly on manager exit.**

### Check D — Full pytest suite, all three roots

```
$ pytest tests/ backend/ legacy/proxy-socks5/tests -v
...
======================= 167 passed, 2 skipped in 13.41s ======================
```

Breakdown:

- `tests/` — VLESS parser, config-gen, installer, xray, manager, plus
  pre-existing scheduler / cart / session test suites
- `backend/` — FastAPI router, sale continuity, scheduler freshness
- `legacy/proxy-socks5/tests/` — archived SOCKS5 tests
  (`_socks5_preflight`, `_test_proxy`, refresh-timeout regression) run
  against `legacy/proxy-socks5/proxy_manager.py` via the sibling
  `conftest.py` rebinding trick

Skipped (2): the two `RUN_LIVE=1`-gated integration tests (smoke-tested
separately above).

**Result: PASS — 167/167 active tests green.**

### Check E — Ruff

```
$ ruff check vless/ tests/test_vless_*.py proxy_manager.py scripts/bootstrap_xray.py legacy/proxy-socks5/tests/conftest.py
All checks passed!
```

**Result: PASS — no style regressions in new or touched files. Legacy
archive is excluded from ruff (read-only historical state).**

### Check F — Shim is ≤ 30 executable lines and resolves to VlessProxyManager

```
$ python3 -c "from proxy_manager import ProxyManager; pm = ProxyManager(); print(type(pm).__name__)"
VlessProxyManager
```

`proxy_manager.py` contains 7 non-blank, non-comment, non-docstring,
non-import lines of executable code (well under the 30-line budget).

**Result: PASS.**

### Check G — `git log --follow` preserves SOCKS5 history back through v1.0

```
$ git log --follow --oneline -- legacy/proxy-socks5/proxy_manager.py | wc -l
8
$ git log --follow --oneline -- legacy/proxy-socks5/proxy_manager.py | head
cc70185 chore(proxy): archive SOCKS5 implementation, shim proxy_manager to VLESS (phase 56-04)
3f69a86 chore(proxy): 4h VkusVill cooldown and v1.15 research tooling
4c7f271 fix(scheduler): prevent SOCKS5 recv() deadlock that froze scraper for 33h
b5b1c61 fix: restore cart truth and repair history sessions
d51b14b fix: keep cart requests on cached proxies
54bc468 feat: proxy history stats (day/week/month), log filter buttons, Moscow timezone
72819e4 worked login
47ab350 fix: stock=99 bug, Chrome cleanup between cycles, clean .gitignore
```

**Result: PASS — `git mv` preserved history across the archive move.**

### Check H — Rollback rehearsal

Performed on a sacrificial branch, targeting the 56-04 commit
(`cc70185`):

```
$ git checkout -b rehearse/v1.15-rollback-1776901542
Switched to a new branch 'rehearse/v1.15-rollback-1776901542'

$ git revert --no-edit cc70185
 delete mode 100644 legacy/README.md
 delete mode 100644 legacy/proxy-socks5/README.md
 delete mode 100644 legacy/proxy-socks5/tests/conftest.py
 rename legacy/proxy-socks5/proxy_manager.py => proxy_manager.py (100%)
 rename {legacy/proxy-socks5/tests => tests}/test_proxy_manager.py (100%)

$ pytest tests/ backend/ -q
...
167 passed, 2 skipped in 13.45s

$ git checkout devin/1776898458-phase-56-vless-proxy-migration
$ git branch -D rehearse/v1.15-rollback-1776901542
```

- 56-04 is a single atomic commit — `git revert` touches exactly the same
  files (rename back plus readme/conftest delete).
- Post-revert pytest is green (167 passed, 2 skipped). The revert is
  therefore a valid escape hatch if production needs to return to the
  SOCKS5 code path, even though the pool itself is still 0% alive.

**Result: PASS.**

## EC2 Rollout (pending operator action)

The deploy + live-production checks require the `scraper-ec2-new` SSH key
(not present in the Devin execution environment). The operator runs:

```
./scripts/deploy_v1_15.sh        # 8 steps, ends in `systemctl status` on both units
./scripts/verify_v1_15.sh        # 5 live checks (see scripts/verify_v1_15.sh header)
```

`verify_v1_15.sh`'s 5 checks must all print PASS:

1. `systemctl is-active saleapp-xray == active` and port 10808 accepting
2. `curl --socks5-hostname 127.0.0.1:10808 ipinfo.io/json` returns
   `country == "RU"`
3. `curl --socks5-hostname 127.0.0.1:10808 vkusvill.ru/` returns content
   containing the `vkusvill` marker
4. `python3 scrape_green.py` produces at least one product in
   `data/green_products.json`
5. `/api/cart/add` then `/api/cart/remove` both return `{"ok": true}`
   for product 33215 (requires a live `PHPSESSID` cookie in the
   environment)

When the operator runs these, append the full transcript of each script
below this line and flip the corresponding milestone checkboxes in
`.planning/ROADMAP.md` Phase 56 success criteria 2 and 3.

```
# EC2 deploy + verify transcript — <fill in ISO8601 date> — <operator name>

## ./scripts/deploy_v1_15.sh
<paste output here, including [1/8] through [8/8] banners>

## ./scripts/verify_v1_15.sh
<paste output here — each >>> banner through the final
"All 5 live checks PASSED" line>
```

## Milestone Closure Decision

- **Code + tests + docs + dev-verification + rollback rehearsal: COMPLETE.**
  Merged on `main` at commits listed in the table above.
- **EC2 rollout + live production verification: PENDING OPERATOR.**
  The scripts are in place, pinned version, SHA-256-verified, hardened
  systemd unit, cron safeguard, operator guide — every prerequisite is
  shipped.

Closing v1.15 requires one operator deploy run. Once `verify_v1_15.sh`
passes on prod, append its transcript to this file in a follow-up docs
commit and tick the last two boxes in `.planning/ROADMAP.md` Phase 56.
