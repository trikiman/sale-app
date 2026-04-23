# Phase 57: VLESS Timeout Hardening — Context

**Gathered:** 2026-04-23
**Status:** Ready for planning
**Predecessor:** Phase 56 (v1.15) + v1.16 follow-up PRs #2-#10

<domain>
## Phase Boundary

Fix three root-cause bugs (xray config policy, xray observatory, `remove_proxy` no-op) and five symptom-level bugs (backend/cart timeouts, geo-verification removal) identified in `../56-vless-proxy-migration/INSPECTION-2026-04-23.md` that together produce the user-visible "middle-of-connection timeout" behavior.

**In scope:** narrow edits to `vless/config_gen.py`, `vless/manager.py`, `vless/sources.py`, `backend/main.py`, `cart/vkusvill_api.py`, plus a v1.17 verification script and docs update. Total estimated edit surface is under 100 lines of code.

**Out of scope:** redesigning the balancer, adding new VLESS source repos, changing the VLESS URL parser, refactoring proxy callers, touching systemd units, or introducing paid proxy providers. This is a tuning phase, not an architecture phase.

</domain>

<decisions>
## Implementation Decisions

### xray Configuration (addresses R1, R2)
- **D-01:** Add explicit `policy.levels["0"]` block with `connIdle=30s` (default is 300s). This is the primary fix for the mid-connection hang — xray no longer keeps dead upstream connections alive for 5 minutes.
- **D-02:** Add `observatory` block that probes every outbound with a 204-response URL every 5 minutes. Wire the balancer to `leastPing` so dead / slow outbounds are auto-excluded within one probe cycle.
- **D-03:** Keep the existing `random` selector as a fallback for when observatory has no data yet (xray handles this natively when `leastPing` falls back to round-robin on uninitialized nodes). No special config needed.

### Python Timeouts (addresses S1, S2, S3)
- **D-04:** Align `CART_REQUEST_TIMEOUT` in `cart/vkusvill_api.py` with the measured VLESS cost. `connect=8.0, read=8.0, write=5.0, pool=3.0` — keeps per-call total under 10s while giving the VLESS handshake (3-5s per PR #10) room.
- **D-05:** Raise the phase-1 HEAD health check in `backend/main.py:product_details` from 1s to 5s connect / 3s read. Or remove it entirely and rely on xray observatory — the plan picks the simpler timeout-raise fix.
- **D-06:** Image proxy `timeout=8` scalar → structured `httpx.Timeout(connect=5, read=10, write=3, pool=3)`.

### `remove_proxy` Rotation (addresses R3)
- **D-07:** When `remove_proxy` is called with the local bridge address (`127.0.0.1:10808`), interpret it as "current upstream failed — rotate." Implementation: call the existing `mark_current_node_blocked` helper, which puts the presumed head-of-list node into VkusVill 4h cooldown. This is correct in expectation because the balancer would have had equal chance of selecting that node.
- **D-08:** Do NOT query xray stats API to identify the "actually failed" outbound. That would require bringing up xray's `api` inbound and is out of scope. Accept the small inaccuracy (cooling down a possibly-innocent node) for the big gain (breaking the hang-retry-hang loop).

### Geo Verification (addresses S5, restores plan D-05 from phase 56)
- **D-09:** Restore multi-provider egress geo verification in `_probe_candidates_in_parallel`. After the vkusvill probe succeeds (indicating the node functionally proxies), do a second probe to `https://ipinfo.io/json` through the same candidate xray to learn the real egress country. Reject candidates whose egress is not RU.
- **D-10:** Keep the emoji pre-filter as a cheap first-pass gate — it correctly drops US/DE/NL-labeled entries that don't need a probe at all. The emoji filter is additive, not a replacement for geo verification.

### Scope of Change
- **D-11:** Do NOT touch `vless/parser.py`, `vless/xray.py`, `vless/installer.py`, `vless/pool_state.py`, or anything under `legacy/`. These were identified as "do not touch" in the inspection report.
- **D-12:** Do NOT add new dependencies. All fixes use existing packages (`httpx`, `xray-core` already installed).

### The agent's Discretion
- Exact line-by-line placement of the new config sections in `build_xray_config`
- Naming of new test functions (follow the existing `test_vless_*` naming convention)
- Whether to add a `VLESS_HANDSHAKE_BUDGET_S = 5.0` constant in `cart/vkusvill_api.py` for the timeouts, or inline them
- Whether to add a helper `_verify_egress_country(candidate, test_port)` or inline it in `_probe_one`

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### This Phase's Driver
- `../56-vless-proxy-migration/INSPECTION-2026-04-23.md` — the forensic report. Every fix in this phase maps to a specific finding there. The "Recommended Fixes" section lists F1-F6 with suggested code snippets.

### Predecessor Phase
- `../56-vless-proxy-migration/56-CONTEXT.md` — D-05 (geo-verify always) and D-08 (leastPing deferred); this phase re-opens both
- `../56-vless-proxy-migration/56-VERIFICATION.md` — shows 0/15 non-RU egress finding that motivates D-09
- `../56-vless-proxy-migration/README.md` — for the "commit message convention" and "when to stop and ask" patterns

### Production Code You'll Edit
- `vless/config_gen.py:118-148` — `build_xray_config` function (add policy + observatory, change strategy)
- `vless/manager.py:165-182` — `remove_proxy` (fix local-bridge-addr no-op)
- `vless/manager.py:623-702` — `_probe_candidates_in_parallel` (add geo verification sub-probe)
- `vless/sources.py:175-203` — `filter_ru_nodes` (no changes to signature, but tests need updating if geo path returns)
- `backend/main.py:558, 583, 726, 740, 754` — raise timeouts on detail fetch + image proxy
- `cart/vkusvill_api.py:29` — raise `CART_REQUEST_TIMEOUT`

### Production Code You MUST NOT Edit
- `vless/xray.py` — subprocess wrapper, correct as-is
- `vless/installer.py` — binary installer, correct as-is
- `vless/parser.py` — URL parser, correct as-is
- `vless/pool_state.py` — persistence, correct as-is
- `legacy/proxy-socks5/**` — archived, read-only
- `systemd/**` — correct, drop-in override files stay as-is
- `scripts/geo_providers.py` — already reused by phase 56, no changes needed

### Tests You'll Write / Update
- `tests/test_vless_config_gen.py` — new assertions for policy + observatory + leastPing (57-01)
- `tests/test_vless_manager.py` — update `remove_proxy` tests to expect rotation instead of no-op (57-02); add geo-verification tests (57-03)
- `tests/test_cart_errors.py` — regression test that cart operations don't hit CART_REQUEST_TIMEOUT budget over a mocked slow proxy (57-02)

### Supporting References
- xray-core v24 observatory docs: https://xtls.github.io/en/config/observatory.html (check current syntax before implementing)
- xray-core v24 policy docs: https://xtls.github.io/en/config/policy.html
- httpx timeout semantics: https://www.python-httpx.org/advanced/#timeout-configuration (note: scalar `timeout=N` means N seconds for each phase, not total)

</canonical_refs>

<code_context>
## Existing Code Insights

### Why Each Bug Happened

- **R1 (connIdle default):** The phase-56 plan authored `build_xray_config` with just the minimum fields needed to route VLESS traffic. Nobody told the author that xray defaults `connIdle` to 300s — the xray docs only mention it in the `policy` page, not the "balancer" or "outbound" pages. The plan's acceptance criteria focused on "does it start and egress?" not "does it close dead connections promptly?"

- **R2 (no observatory):** The phase-56 plan D-08 said "leastPing is deferred for v1 — random is fine." The author implemented literally that (balancer strategy = random, no observatory). "Deferred" should have meant "wire observatory now, use random strategy with observatory available, switch to leastPing later," but was interpreted as "don't wire observatory at all." This is the clearest plan-to-code gap.

- **R3 (remove_proxy no-op):** When Devin wrote `remove_proxy` for the VlessProxyManager, the natural interpretation of "remove this address" for the local bridge was "this address is the bridge, I can't remove the bridge." That's technically correct but misses the intent: callers call `remove_proxy` meaning "rotate away from whatever proxy I just used." The fix is reinterpreting the intent, not adding a new method.

- **S1/S2 (short timeouts):** The timeouts were copied from v1.0-era direct SOCKS5 budgets. Direct SOCKS5 handshake is ~1s; VLESS+Reality is ~3-5s. Devin raised only the one budget the EC2 failure surfaced (cart-add hot-path in PR #10). The other call sites stayed at the v1.0 budgets and are silently over-tight.

- **S5 (geo-verify removed):** Devin's PR #7 correctly identified that VLESS *server* IPs don't geolocate the egress. But the fix was to remove geo-verification entirely rather than moving it from "geolocate the server host" to "probe through the node and geolocate the egress." Plan D-05 was clear; the substitution was a unilateral scope change.

### Patterns to Reuse

- `_probe_candidates_in_parallel` at `vless/manager.py:623-702` already spawns per-candidate xray processes, issues probe traffic, and tears them down. Extend this same function to do the geo probe — do NOT duplicate the subprocess plumbing.
- `build_xray_config` already has the balancer / selector / strategy tuple. Just extend the strategy dict value and add `observatory` as a sibling of `outbounds`.
- `XrayProcess.verify_egress` at `vless/xray.py:235-261` already does an ipinfo.io probe through a local xray. Reuse it in the geo-verification path — do NOT write a new HTTP client.

### Integration Points
- xray restart is required after config changes. `VlessProxyManager._rebuild_and_restart_xray()` at `vless/manager.py:802-837` already handles this. Your changes must flow through the same method — do NOT write a parallel restart code path.
- The deploy script `scripts/deploy_v1_15.sh` will need a small update in 57-04 to `force_refresh=True` on post-deploy so the new observatory block appears immediately. Do NOT delete `active.json` — the `_rebuild_and_restart_xray` flow handles it.

</code_context>

<specifics>
## Specific Ideas

### Exact xray policy block to add

```python
config["policy"] = {
    "levels": {
        "0": {
            "handshake": 8,
            "connIdle": 30,
            "uplinkOnly": 5,
            "downlinkOnly": 10,
            "bufferSize": 4096,
            "statsUserUplink": False,
            "statsUserDownlink": False,
        },
    },
    "system": {
        "statsInboundUplink": False,
        "statsInboundDownlink": False,
    },
}
```

Values come from the inspection report's F1 recommendation. `handshake=8` accommodates worst-case VLESS+Reality (5s observed). `connIdle=30` kills dead connections without being aggressive enough to drop bursty legitimate traffic.

### Exact observatory block to add

```python
config["observatory"] = {
    "subjectSelector": ["node-"],
    "probeUrl": "https://www.google.com/generate_204",
    "probeInterval": "5m",
}
```

Subject selector `["node-"]` is a prefix match — xray probes every outbound whose tag starts with "node-" (which `_build_outbound` produces for all VLESS outbounds). `generate_204` returns 204 No Content with a tiny body, so probe bandwidth is trivial.

### Exact strategy change

```python
"strategy": {"type": "leastPing"},  # was {"type": "random"}
```

xray's `leastPing` strategy reads observatory data; if an outbound has no probe data yet (startup edge case) xray falls back to round-robin among that subset. No additional "fallback" config is needed.

### `remove_proxy` bridge-addr branch

```python
def remove_proxy(self, addr: str) -> None:
    with self._lock:
        if addr.startswith(f"{XRAY_LISTEN_HOST}:"):
            self._log(
                "remove_proxy called with local xray endpoint — "
                "rotating via mark_current_node_blocked"
            )
            self.mark_current_node_blocked("remove_proxy_local_addr")
            return
        host = addr.split(":", 1)[0]
        self._remove_host_and_restart(host, reason="remove_proxy")
```

### Geo verification extension to `_probe_one`

After the vkusvill probe at `vless/manager.py:660-664` succeeds, add:

```python
if ok:
    egress_ok, egress_country = proc.verify_egress(
        expected_country="RU",
        url="https://ipinfo.io/json",
        timeout=10.0,
    )
    if not egress_ok:
        node.extra["rejected_reason"] = f"egress_country={egress_country}"
        return None
    node.extra["egress_country"] = egress_country
```

This uses the existing `XrayProcess.verify_egress` helper.

</specifics>

<deferred>
## Deferred Ideas (NOT in this phase)

- **Per-outbound statistics dashboard** — `/admin/proxy-status` showing which outbound was picked for each recent request. Requires bringing up xray's `api` inbound. Defer to next milestone.
- **Automated pool size alerting** — if pool drops below MIN_HEALTHY after geo verification, notify ops via Telegram. Defer — for now, ops checks stats manually.
- **Burst observatory** (`burstObservatory`) — a more aggressive variant of observatory with per-connection probing. Only needed if 5-minute observatory interval proves too slow. Defer until measured.
- **Per-outbound affinity** — pin one Python caller's connections to one outbound for session continuity. Defer; VkusVill has no session affinity needs today.
- **HTTPS probe URL override** — make `probeUrl` configurable via env var so users can swap from Google's generate_204 to their own. Defer; no current need.
- **Graceful xray config reload without restart** — via xray's API inbound. Defer; restart is fast (<2s).

</deferred>

---

*Phase: 57-vless-timeout-hardening*
*Context gathered: 2026-04-23*
