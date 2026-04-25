# Phase 57 — VLESS Timeout Hardening (CLOSED 2026-04-25)

Follow-up to phase 56 v1.15 + v1.16 hotfix chain. Inspection report
[`../56-vless-proxy-migration/INSPECTION-2026-04-23.md`](../56-vless-proxy-migration/INSPECTION-2026-04-23.md)
identified 3 P0 root causes + 5 symptom bugs behind the user's
"middle of cart-add request times out" report. All 8 are now remediated
and live in production.

## What shipped (4 atomic commits)

| Sub-plan | Commit  | PR  | Scope                                             |
|----------|---------|-----|---------------------------------------------------|
| 57-01    | `d92ddca`| #13 | xray policy block + observatory + `leastPing`    |
| 57-02    | `ef50253`| #14 | Python timeout alignment + `remove_proxy` rotate |
| 57-03    | `4e53817`| #15 | Restore egress geo-verification in admission     |
| 57-04    | (this)   | (this) | Deploy scripts + live verification + docs    |

## Root causes addressed

- **R1** — xray's default `policy.levels[0].connIdle` is 300s; dead
  connections lingered for 5 minutes blocking new requests. v1.17 sets
  `connIdle=30s`, `handshake=8s`. (57-01)
- **R2** — Random balancer kept picking dead outbounds because nothing
  ever marked them dead. v1.17 ships an `observatory` block that probes
  every 5min via `probeURL=http://www.gstatic.com/generate_204` and a
  `leastPing` strategy that uses observatory data. (57-01)
- **R3** — `remove_proxy("127.0.0.1:10808")` was a silent no-op (the
  bridge address is ambiguous — there are 15 outbounds behind it).
  v1.17 routes that call through `mark_current_node_blocked` so dead
  nodes actually leave the pool. (57-02)

## Symptom bugs addressed

- **S1** — `CART_REQUEST_TIMEOUT` connect/read raised 2/3s → 8/8s. (57-02)
- **S2** — `backend/main.py` image proxy: 3 sites converted from scalar
  `timeout=6/8` to structured `httpx.Timeout(connect=5, read=8/10)` so
  the connect budget can absorb VLESS handshake cost. (57-02)
- **S3** — `vless/manager.py::remove_proxy` no-op. (57-02, same as R3.)
- **S5** — Phase 56 PR #7 dropped multi-provider geo verification in
  favor of trusting the 🇷🇺 flag emoji in the URL fragment. v1.17
  restores it as a second-stage probe via `XrayProcess.verify_egress`
  through the candidate's xray (not against the server host IP).
  Caught FR-egressing nodes labeled "🇷🇺 Russia" in the deploy log. (57-03)
- **S4** — Bridge retry loop on transient TLS errors. Already shipped in
  v1.16 PR #11 (pre-57); listed here for completeness.

## Test count

- Phase 56 close (v1.15): 167/2 passing
- Phase 57 close (v1.17): **96 + 86 + 2 skipped** = 184 total / 2 skipped
  - `tests/`: 96 passed (config_gen +5, manager +4 for egress)
  - `backend/`: 86 passed
  - 2 integration tests skipped (require `RUN_LIVE=1`)

## Production verification (2026-04-25 13:55 MSK)

See [`57-VERIFICATION.md`](./57-VERIFICATION.md). Key wins:

- Egress geo: **0/15 RU (v1.15 CAVEAT) → 5/5 RU (v1.17 PASS)**
- Vercel miniapp `/api/cart/add`: **SKIPPED in v1.15 → HTTP 200 ×2 in v1.17**
- xray `active.json`: `policy`, `observatory`, `leastPing` all confirmed live

## Punted to phase 58 (if needed)

- ipinfo.io rate-limiting causes ~70% false-negatives during refresh.
  Pool still reaches 15 nodes (>MIN_HEALTHY=7), but a paced/multi-provider
  geo resolver would lift the ceiling.
- `scrape_green.py` Chromium DevTools WebSocket HTTP 500 mid-cycle.
  Independent of VLESS; deserves its own investigation.
- Pool size monitoring + alerting (15 nodes works, but no signal if it
  drops to 8 between refreshes).
