# Requirements — v1.15 Proxy Infrastructure Migration

## Milestone Goal

Replace the dead free-SOCKS5 proxy pool (0% alive across 269 tested nodes as of 2026-04-22) with a VLESS+Reality proxy pool tunneled through a local `xray-core` SOCKS5 bridge, so scraper and cart-add traffic reliably exits from a Russian IP without depending on short-lived free SOCKS5 proxies. Archive the legacy SOCKS5 infrastructure (do not delete) so a rollback is a single git operation.

## Requirements

### Proxy Infrastructure

- [x] **PROXY-06**: A curated pool of VLESS+Reality exit nodes, geo-verified to exit from Russian IP addresses, is fetched from public sources and stored locally with per-node metadata (host, port, uuid, reality params, last-seen timestamp)
- [x] **PROXY-07**: A local `xray-core` process runs on both dev (Windows) and production (EC2 / systemd), exposing a SOCKS5 listener on `127.0.0.1:10808` that tunnels outbound traffic over the VLESS+Reality pool; the process is managed (start, health-check, graceful restart) by the application *(code + systemd units + deploy/verify scripts shipped; dev live-verified; EC2 rollout pending operator — see `phases/56-vless-proxy-migration/56-VERIFICATION.md`)*
- [x] **PROXY-08**: The proxy pool refreshes once per day, and also early-refreshes when the current node fails with a timeout and no other healthy nodes are available
- [x] **PROXY-09**: Proxy failures are classified by cause: VkusVill-specific blocks (timeout, HTTP 403/429/451, content mismatch) enter a 4-hour quarantine cooldown; node-level failures (TLS handshake fail, outbound unreachable, xray-reported error) cause immediate removal from the active pool
- [x] **PROXY-10**: `from proxy_manager import ProxyManager` continues to work unchanged in all 7 production files and 3 test files via a compatibility shim; the legacy SOCKS5 implementation is archived under `legacy/proxy-socks5/` with a documented one-git-operation rollback procedure

## v2 Requirements

### Future Follow-Ups

- **PROXY-11**: Support a paid/commercial RU proxy tier as an optional fallback when the free VLESS pool drops below a healthy threshold
- **PROXY-12**: Expose proxy pool health (alive count, cooldown count, last-refresh-at, last-node-used) on `/admin/status` so the operator can diagnose pool exhaustion from the browser
- **PROXY-13**: Auto-rotate between VLESS nodes inside xray on every outbound request (round-robin / least-recently-used) rather than sticky-per-process

## Out of Scope

| Feature | Reason |
|---------|--------|
| Paid RU proxy providers | v1 relies entirely on free public VLESS pool; paid fallback deferred to PROXY-11 |
| New auth system or checkout changes | v1.15 is infrastructure-only; cart-truth / history semantics were handled in v1.13-v1.14 |
| Replacing EC2 or Vercel deployment | The migration is at the network layer only — the application servers stay where they are |
| Admin UI redesign | Proxy health surface (PROXY-12) is deferred — out of scope for v1.15 |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| PROXY-06 | Phase 56 | Complete |
| PROXY-07 | Phase 56 | Complete (code + dev live-verify); EC2 rollout pending operator |
| PROXY-08 | Phase 56 | Complete |
| PROXY-09 | Phase 56 | Complete |
| PROXY-10 | Phase 56 | Complete |

**Coverage:**
- v1.15 requirements: 5 total
- Mapped to phases: 5
- Unmapped: 0 ✓

## Prior Milestone (v1.14) — Archived

v1.14 Cart Truth & History Semantics shipped 2026-04-21 and was archived 2026-04-22. See `.planning/milestones/v1.14-REQUIREMENTS.md` for the archived requirements.

The user-facing cart-add failure observed at the end of v1.14 was determined to be proxy-pool exhaustion (0% alive), not a cart-logic regression — which is the direct driver of this v1.15 milestone.

---
*Requirements defined: 2026-04-22*
*Prior milestone v1.14 archived: 2026-04-22*
