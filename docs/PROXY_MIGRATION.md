# Proxy Migration Operator's Guide (v1.15)

This document is the day-to-day reference for the VLESS+Reality proxy pool
that replaced the free SOCKS5 pool in milestone v1.15. Read it end-to-end the
first time; return to specific sections as needed.

## Architecture

```
   Python callers (scheduler, backend, bot, scrapers, cart)
            │
            │ socks5://127.0.0.1:10808
            ▼
      xray-core (local SOCKS5 inbound  →  VLESS+Reality outbound)
            │
            │ TLS-camouflaged Reality handshake to one of N admitted nodes
            ▼
   VLESS+Reality exit nodes (Russia-geolocated; ~5–30 healthy)
            │
            ▼
       vkusvill.ru, ipinfo.io, ...
```

The Python layer never speaks VLESS directly. All callers import
`ProxyManager` from `proxy_manager.py`, which is a shim that re-exports
`vless.manager.VlessProxyManager`. The manager owns one long-lived
`xray-core` subprocess and exposes `"127.0.0.1:10808"` as the working proxy
endpoint. xray is installed into `bin/xray/v<version>/` and symlinked at
`bin/xray/current/`.

### Key files

| Path | Purpose |
|------|---------|
| `vless/installer.py` | Downloads + SHA256-verifies + extracts xray-core |
| `vless/xray.py` | Subprocess wrapper (start / stop / restart / health-check) |
| `vless/parser.py` | Pure-Python VLESS URL parser |
| `vless/sources.py` | Fetches the igareck node list, geo-filters to RU |
| `vless/config_gen.py` | Builds the xray-core JSON config from admitted nodes |
| `vless/manager.py` | VlessProxyManager — the drop-in ProxyManager replacement |
| `vless/pool_state.py` | Atomic JSON persistence for `data/vless_pool.json` |
| `proxy_manager.py` | Compatibility shim (`ProxyManager = VlessProxyManager`) |
| `legacy/proxy-socks5/` | Archived SOCKS5 implementation (read-only) |
| `systemd/saleapp-xray.service` | systemd unit for xray |
| `systemd/saleapp-scheduler.service` | scheduler unit; `Requires=saleapp-xray` |
| `scripts/bootstrap_xray.py` | Local xray installer / smoke-tester |
| `scripts/deploy_v1_15.sh` | EC2 deploy orchestrator |
| `scripts/verify_v1_15.sh` | 5-check live verification against EC2 |
| `scripts/xray_healthcheck.sh` | 5-minute cron safeguard against silent hangs |

### Data files (same schemas as v1.0-v1.14)

- `data/vless_pool.json` — active admitted-nodes snapshot (new in v1.15)
- `data/proxy_events.jsonl` — append-only event log (schema preserved;
  new event types: `vless_refresh_start`, `vless_node_admitted`,
  `vless_node_removed`, `xray_start`, `xray_stop`)
- `.cache/vkusvill_cooldowns.json` — 4-hour per-host cooldown after a
  VkusVill block or timeout (schema and path unchanged)

## Daily Operations

### Is xray healthy?

```bash
systemctl status saleapp-xray
tail -n 100 /home/ubuntu/saleapp/bin/xray/logs/xray.stderr.log
```

Quick port check:

```bash
timeout 2 bash -c '</dev/tcp/127.0.0.1/10808' && echo OK
```

### What is in the pool right now?

```bash
python3 -c 'from vless.manager import VlessProxyManager; \
            pm = VlessProxyManager(); \
            print(pm.xray_status()); \
            print("pool_count:", pm.pool_count())'
```

### Force a pool refresh

```bash
python3 -c 'from vless.manager import VlessProxyManager; \
            pm = VlessProxyManager(); \
            print("admitted:", pm.refresh_proxy_list())'
```

The refresh fetches the igareck list, geo-filters to Russia, probes each
candidate in parallel (8 concurrent xray test-processes), applies
subnet-diversity (≤3 per /24, cap 30), writes
`data/vless_pool.json`, rebuilds the xray config, and restarts the
running xray so callers continue to get a fresh bridge.

### Where are the logs?

| Stream | Path |
|--------|------|
| xray stdout | `bin/xray/logs/xray.stdout.log` |
| xray stderr | `bin/xray/logs/xray.stderr.log` |
| healthcheck cron | `logs/xray_healthcheck.log` |
| scheduler | `logs/scheduler.stdout.log`, `logs/scheduler.stderr.log` |
| proxy events | `data/proxy_events.jsonl` |

### Recent block/cooldown events

```bash
tail -n 50 data/proxy_events.jsonl | \
  python3 -c 'import sys,json
for line in sys.stdin:
    e = json.loads(line)
    if e.get("event") in {"vkusvill_cooldown","vless_node_removed"}:
        print(e)'
```

## Troubleshooting

### Scheduler won't start

The scheduler unit has `Requires=saleapp-xray.service`. If xray failed to
start, systemd blocks the scheduler. Always check xray first:

```bash
systemctl status saleapp-xray
journalctl -u saleapp-xray -n 100 --no-pager
```

### Pool is empty after refresh

Most likely the igareck source returned zero RU nodes (rare) or all
candidates failed the probe.

1. Check source reachability:
   `curl -sI https://raw.githubusercontent.com/igareck/vpn-configs-for-russia/main/BLACK_VLESS_RUS.txt`
2. Clear cooldowns and retry:
   `rm .cache/vkusvill_cooldowns.json && python3 -c 'from vless.manager import VlessProxyManager; print(VlessProxyManager().refresh_proxy_list())'`
3. If still empty, check `56-CONTEXT.md` for alternate source URLs and
   patch `vless/sources.py` accordingly.

### Cart-add fails with timeout

The current active node may be VkusVill-blocked:

```bash
python3 -c 'from vless.manager import VlessProxyManager; \
            pm = VlessProxyManager(); \
            print("cooldowns:", pm.cooldown_addrs()); \
            pm.mark_current_node_blocked("manual-timeout"); \
            print("rotated; new status:", pm.xray_status())'
```

### xray active but port unresponsive

The 5-minute cron (`scripts/xray_healthcheck.sh`) detects this and
restarts the unit. If it is happening repeatedly, check for version drift:

```bash
ls bin/xray/v*/xray
python3 -c 'from vless.installer import XRAY_VERSION, is_installed; print(XRAY_VERSION, is_installed())'
```

## Rollback

v1.15 is designed so that a single `git revert` returns the codebase to
the SOCKS5 implementation (though the SOCKS5 pool itself is dead — this is
an emergency escape hatch, not a long-term path).

### Rehearsal procedure (do this locally)

```bash
git fetch origin
git checkout -b rehearse/v1.15-rollback origin/main
git log --oneline | grep "phase 56-04"   # find the shim commit hash
git revert --no-edit <hash>
pytest tests/ backend/ -q                # should still pass
git checkout main
git branch -D rehearse/v1.15-rollback
```

### Real rollback (emergency only)

```bash
ssh -i ./scraper-ec2-new ubuntu@13.60.174.46
cd /home/ubuntu/saleapp
git log --oneline -n 20
git revert --no-edit <56-04-commit-hash>
git push origin main
sudo systemctl stop saleapp-xray
sudo systemctl disable saleapp-xray
sudo systemctl restart saleapp-scheduler
```

After rollback the SOCKS5 code path is restored but the pool is still 0%
alive — you have minutes to hours of normal scheduler startup while you
re-land v1.15 with the fix.

## xray Policy & Observatory (v1.17)

Phase 57 added two xray sub-blocks to `vless/config_gen.py` that the
default xray config does NOT include. They're load-bearing — without
them, every transient TLS hiccup turns into a 5-minute hang.

### Why `policy.levels["0"]`

```json
"policy": {"levels": {"0": {"handshake": 8, "connIdle": 30}}}
```

xray defaults `connIdle` to **300 seconds** (5 minutes). When a VLESS
outbound dies mid-stream the TCP socket isn't reaped for 5 min — every
new request stuck behind that connection's keepalive queues. Setting
`connIdle=30s` reaps dead connections fast enough that the next request
pays at most one 30s penalty, not five minutes. `handshake=8` caps the
TLS handshake budget per outbound (matches phase 57-02 timeout
alignment).

### Why `observatory`

```json
"observatory": {
  "subjectSelector": ["vless-"],
  "probeURL": "http://www.gstatic.com/generate_204",
  "probeInterval": "5m"
}
```

Without observatory the balancer has zero signal about which outbounds
are alive. With it, xray actively probes each outbound every 5 minutes
and feeds latency buckets to the balancer. Critical: the JSON tag is
`probeURL` (capital URL — matches xray-core Go source). Earlier drafts
used `probeUrl` and xray silently ignored the URL, falling back to its
default endpoint. (Caught in PR #13 by Devin Review.)

### Why `leastPing` instead of `random`

```json
"routing": {"balancers": [{"strategy": {"type": "leastPing"}, ...}]}
```

`random` picks an outbound for every connection regardless of health —
50% of requests hit dead nodes when half the pool is bad. `leastPing`
uses observatory data to prefer outbounds with low recent ping. Required
companion to the observatory block; without one the other is dead
weight.

### Troubleshooting

- **"my refresh admits 0 nodes"** — check the rejection log for
  `egress_country=...`. Phase 57-03 rejects non-RU exits and ipinfo.io
  rate-limited probes. Pool floor is `MIN_HEALTHY=7`; falling below
  means upstream sources need broadening.
- **"requests still time out after v1.17"** — read `bin/xray/logs/xray.log`:
  - `connection refused` → upstream is blocking us (rotate via
    `manager.remove_proxy("127.0.0.1:10808")` which now properly
    triggers `mark_current_node_blocked`).
  - `handshake timeout` → upstream is slow; observatory will demote
    them on the next 5-minute probe cycle.
- **"observatory data missing"** — check `active.json` actually has
  the `observatory` key (`jq '.observatory' bin/xray/configs/active.json`).
  If null, the deploy was stale; re-run `scripts/deploy_v1_17.sh` to
  force a refresh.

## Upgrading xray-core

1. Edit `vless/installer.py`:
   - Bump `XRAY_VERSION` to the target release
   - Replace each entry in `XRAY_SHA256` with the verified SHA-256 hash
     from the GitHub release assets
2. Re-run bootstrap: `python3 scripts/bootstrap_xray.py --force`
3. Restart the service: `sudo systemctl restart saleapp-xray`
4. Verify: `./scripts/verify_v1_15.sh`

Never trust a download without SHA-256 verification; the installer fails
fast on checksum mismatch and that is a feature.
