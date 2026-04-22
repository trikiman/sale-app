# Phase 56: VLESS Proxy Migration - Context

**Gathered:** 2026-04-22
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace the dead free-SOCKS5 proxy pool with a VLESS+Reality proxy pool tunneled through a local `xray-core` SOCKS5 bridge. The phase covers: VLESS URL parsing, xray-core process bootstrap and lifecycle management, a drop-in replacement for `proxy_manager.ProxyManager` that preserves the existing public API, archival of the legacy SOCKS5 implementation for rollback, and production deployment on EC2 with a rollback rehearsal.

Out of this phase: redesigning `/admin/status`, introducing paid proxy providers, refactoring callers of `proxy_manager`, or changing cart / history / scraper business logic.

</domain>

<decisions>
## Implementation Decisions

### Proxy Transport
- **D-01:** Use VLESS+Reality as the sole proxy transport for this milestone. Do not mix SOCKS5 and VLESS at runtime — the migration is all-or-nothing, with the old SOCKS5 path archived behind a single-operation rollback.
- **D-02:** Run `xray-core` as a local subprocess exposing a SOCKS5 listener on `127.0.0.1:10808`. All Python HTTP clients (scraper, cart, backend) continue to speak SOCKS5 unchanged; xray is the single point of translation to VLESS+Reality.
- **D-03:** xray is managed by the application (start, stop, health-check, graceful restart), not by the OS. On EC2, a thin systemd unit invokes the same Python bootstrap so lifecycle logic stays in one place.

### Source of VLESS Configs
- **D-04:** Start with the `igareck/vpn-configs-for-russia` public repo as the single source (~191 configs, ~55 unique RU IPs after geo-filtering — already validated during preparatory research). Additional sources can be added later without changing the parser or lifecycle code.
- **D-05:** Always geo-verify exit IPs using the multi-provider resolver in `scripts/geo_providers.py` before admitting a node to the active pool. Never trust the source repo's country labels.

### Pool Refresh Strategy
- **D-06:** Daily full-refresh (fetch → parse → geo-filter RU → test → rebuild xray config) runs at a fixed scheduler hour. A partial early-refresh triggers when the current outbound node fails with a timeout AND the pool has no other healthy nodes.
- **D-07:** Failure classification is reused from v1.14-prep work in `proxy_manager.py` / `test_ru_proxy_pipeline.py`: VkusVill-specific failures (timeout, HTTP 403/429/451, content mismatch) enter the existing 4-hour cooldown cache (`.cache/vkusvill_cooldowns.json`). Node-level failures (TLS handshake failure, xray-reported error, outbound unreachable) cause immediate removal.

### API Compatibility
- **D-08:** `from proxy_manager import ProxyManager` must continue to work without any caller changes. Implementation path: the new `vless_manager.ProxyManager` class lives at `proxy_manager.py` (same file path), and the old implementation moves to `legacy/proxy-socks5/proxy_manager.py`. Rollback is `git revert` of a single commit.
- **D-09:** The public method surface stays identical: `check_direct`, `check_direct_cached`, `get_working_proxy`, `get_proxy_for_chrome`, `pool_count`, `pool_healthy`, `remove_proxy`, `ensure_pool`, `mark_blocked_by_vkusvill`, `is_in_vkusvill_cooldown`, `note_direct_result`. Return types and semantics are preserved. `get_working_proxy` always returns `"127.0.0.1:10808"` when the pool has at least one healthy VLESS node; node-level rotation happens inside xray, not in Python.

### the agent's Discretion
- Exact xray-core version (pinned in one place, but version bump is fine if upstream releases bugfixes)
- Directory layout for `vless/` package internals
- Whether daily refresh runs in-process (scheduler thread) or via a standalone entrypoint the scheduler invokes
- Test harness (pytest vs plain script) for the URL parser — follow the pattern in `tests/`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase Scope
- `.planning/ROADMAP.md` — v1.15 milestone goal, Phase 56 success criteria (6 items)
- `.planning/REQUIREMENTS.md` — PROXY-06..PROXY-10 define the acceptance contract

### Existing Proxy Code (to be replaced / archived)
- `proxy_manager.py` — Full SOCKS5 implementation, 697 lines. Public API on lines ~89-200. 4h VkusVill cooldown logic already present (lines ~148-246, ~281-314) — KEEP this logic in the new vless_manager.
- `proxy_manager.py:_socks5_preflight` — kernel-level SOCKS5 handshake. No longer relevant for VLESS (xray handles outbound); retired on archive.
- `proxy_manager.py:_probe_vkusvill` — HTTP probe against vkusvill.ru. REUSE pattern: probe `127.0.0.1:10808` through xray instead of a remote SOCKS5.

### Prior Research Artifacts (preserve, do not re-derive)
- `scripts/test_ru_proxy_pipeline.py` — multi-protocol proxy tester with CLI timeouts, consensus geo-filter, failure classification. The VLESS probing code in 56-01 should follow the same classification taxonomy.
- `scripts/geo_providers.py` — 10-provider geo-IP resolver with persistent cache (`.cache/ip_country.json`) and consensus verification. USE AS-IS.
- `scripts/survey_ru_proxy_sources.py` — proxy-source survey with fetch / parse / dedupe / geo-filter pipeline. Pattern carries over to VLESS.
- `.cache/alive_ru_proxies.json` — 2026-04-22 snapshot, 0 alive out of 269 SOCKS5/HTTP tested. Documents why we are migrating.

### Callers of ProxyManager (must keep working)
- `backend/main.py`, `cart/vkusvill_api.py`, `scraper/vkusvill.py`, `scraper/session.py`, `scrape_green.py`, `scrape_yellow.py`, `scrape_red.py` — production callers
- `tests/test_proxy_manager.py`, `tests/test_vkusvill_cart.py`, `tests/test_cart_errors.py` — test callers

### Codebase Guides
- `.planning/codebase/CONVENTIONS.md` — backend patterns, error handling
- `.planning/codebase/TESTING.md` — pytest conventions

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `proxy_manager.py` already has a persistent VkusVill cooldown cache in `.cache/vkusvill_cooldowns.json` with load/save/prune helpers. The new vless_manager inherits this file and logic unchanged — no migration needed.
- `proxy_manager.py` already has event logging to `data/proxy_events.jsonl`. Keep the same event schema: `{ts, event, addr, reason, ...}`. Downstream stats tools depend on this.
- `scripts/geo_providers.py` already has a 10-provider resolver with consensus and per-provider rate limiting. The VLESS refresh pipeline calls it with the list of VLESS host IPs.
- `httpx` is already the HTTP client across the codebase. It speaks SOCKS5 natively via `httpx[socks]`. For VLESS via xray, client code needs zero changes — xray exposes SOCKS5 on 127.0.0.1:10808.

### Established Patterns
- Proxy cache files live under `data/` (pool state) and `.cache/` (research / geo / cooldown). Preserve this split in vless_manager.
- Event logging goes through a tolerant `_track_event` helper that never crashes the caller on disk failure. Preserve this pattern.
- Long-running background refresh is wrapped by an outer timeout (`REFRESH_OUTER_TIMEOUT_SLACK = 15.0`) so the main thread never blocks indefinitely. Preserve this pattern for daily refresh.

### Integration Points
- Every HTTP client caller today does either: (a) `pm.get_working_proxy()` → `"ip:port"` passed to `socks5://` URL construction, or (b) `pm.get_proxy_for_chrome()` → full `socks5://ip:port` string for Chrome CLI. Both must return the local xray address `127.0.0.1:10808` (or `None`) in the new implementation.
- `scraper/session.py` and `scrape_green.py` rotate proxies on failure using `pm.remove_proxy(addr)`. In the VLESS world, there is only one address (127.0.0.1:10808), so `remove_proxy` becomes a no-op on the address and instead classifies the failure internally (VkusVill cooldown vs node removal) and may trigger xray config regeneration.
- EC2 deployment uses `start_app.sh` / systemd. The scheduler and the xray process need to start in a defined order: xray first, then scheduler / backend. The systemd unit for xray ships in 56-05.

</code_context>

<specifics>
## Specific Ideas

- VLESS URL format: `vless://<uuid>@<host>:<port>?encryption=none&flow=xtls-rprx-vision&security=reality&sni=<sni>&fp=<fingerprint>&pbk=<public-key>&sid=<short-id>&spx=<spider-x>&type=tcp&headerType=none#<name>`. Parser must tolerate optional params (`flow`, `spx`, `sid` can be absent), URL-encoded names, and preserve unknown params for future use.
- xray-core supports multiple outbounds in a single config. Use the `balancer` selector with strategy `random` or `leastPing` to load-balance across all healthy VLESS nodes without Python doing the rotation.
- Geo-filter verification must cache results in `.cache/ip_country.json` (already present) to stay friendly to free providers' rate limits. ~55 unique RU IPs were verified once during prep — reuse the cache, only re-verify on daily refresh or when a new URL appears.
- For the rollback plan (56-05), the single-operation rollback is: `git revert <commit-hash-of-56-04-archive>`. The revert restores `proxy_manager.py` to the SOCKS5 implementation and re-deletes the `legacy/` folder in one commit. Verify this is atomic by running the revert in the rehearsal.

</specifics>

<deferred>
## Deferred Ideas

- Multiple VLESS source repositories (PROXY-11 for paid, and a second free repo if igareck ever goes stale) — deferred; not required for the 55-node pool we already have.
- Exposing proxy pool health on `/admin/status` (PROXY-12) — deferred to the next milestone to keep v1.15 infra-only.
- Per-request VLESS node rotation (PROXY-13) — xray's built-in balancer is good enough for v1; round-robin per-request is a future optimization if we see hot-node blocks.
- Migrating the Chrome CLI proxy path — Chrome will continue to receive `socks5://127.0.0.1:10808`, which works without any further change. No deferred work here.

</deferred>

---

*Phase: 56-vless-proxy-migration*
*Context gathered: 2026-04-22*
