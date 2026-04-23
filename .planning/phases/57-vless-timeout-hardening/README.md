# Phase 57: VLESS Timeout Hardening — Executing AI Orientation

**If you are an AI model tasked with executing this phase: read this file first, in full, before touching any code.**

This directory contains the plan for hardening the VLESS+xray bridge shipped in Phase 56 (v1.15) and the v1.16 hotfix chain (PRs #4–#11). Phase 56 proved that VLESS+xray works end-to-end; Phase 57 makes it *reliably* work in the presence of flaky backends, flaky TLS handshakes, and flaky VkusVill-side errors. The plan is scoped so it can be executed autonomously, one sub-plan at a time, with atomic commits.

---

## Context: What v1.15 + v1.16 Already Ship

- **Phase 56 (v1.15):** VLESS URL parser, xray config generator, `VlessProxyManager`, systemd units, deploy/verify scripts, legacy SOCKS5 archival. Merged in PR #1.
- **v1.16 hotfix chain** (PRs #4 through #11):
  - `saleapp-backend.service` now requires `saleapp-xray.service` and reuses the external xray bridge on `127.0.0.1:10808` (PR #4)
  - `VlessProxyManager._cache` compat shim restores `/api/product/:id/details` (PR #5)
  - VkusVill probe rejects `/vpn-detected/` redirects (PR #6)
  - Parser accepts `security=tls` + `flow=xtls-rprx-vision` + `type=tcp`; pool filters by 🇷🇺 emoji (PR #7)
  - Probe relaxed to drop over-tuned catalog-marker check (PR #8)
  - Pool JSON round-trip persists `security` / `tls_sni` / `tls_allow_insecure` (PR #9)
  - `CART_ADD_HOT_PATH_DEADLINE_SECONDS` bumped 3.5s → 10.0s (PR #10)
  - `_perform_http_request` + `DETAIL-PROXY` retry up to 3x through the xray bridge on transient TLS errors (PR #11)

Phase 57 starts from commit `1cae426` on `main` (post-PR #11), with these pending symptoms verified on the live miniapp on 2026-04-23:

1. **Cart badge vs drawer mismatch** — header shows `🛒N` (optimistic count) but the drawer shows fewer or zero items after the server-side cart fetch resolves. Every failed cart-add still bumps the optimistic counter.
2. **`PRODUCT_GONE 410` shows the same red X as transient TLS errors** — users can't tell "VkusVill removed this product" apart from "bridge was unlucky, try again".
3. **Pool admission is one-shot** — the 14 admitted nodes were probed once at refresh time. Nodes that start failing mid-day stay in the pool until the next daily refresh; they just lose the per-request xray round-robin coin flip to a healthier node.
4. **No mid-flight xray reconfiguration** — when a node is conclusively dead, we have no way to rebuild `active.json` and reload xray without a full pool refresh.

These are the four sub-plans.

---

## Reading Order (MANDATORY)

Read these files, in this order, before writing any code:

1. **`.planning/REQUIREMENTS.md`** — existing acceptance requirements (PROXY-06..10 from Phase 56). Phase 57 will add PROXY-11..14.
2. **`.planning/ROADMAP.md`** — v1.16 section (if present) and the post-v1.15 milestone list
3. **`.planning/phases/56-vless-proxy-migration/README.md`** — the Phase 56 execution orientation (this file mirrors its structure)
4. **`.planning/phases/56-vless-proxy-migration/56-CONTEXT.md`** — D-01..D-09 architecture decisions; Phase 57 does NOT change any of them
5. **`cart/vkusvill_api.py`** (full file) — especially `_perform_http_request` (lines ~189–248 on `main`) and `_is_transient_proxy_error` (lines ~42–56). PR #11 introduced the retry loop; Phase 57 builds on it.
6. **`backend/main.py` DETAIL-PROXY block** (lines ~549–612 on `main`) — PR #11's retry loop for product detail
7. **`miniapp/src/App.jsx`** — the optimistic cart state and the drawer rendering code. Search for `setCartState`, `cartItems`, `cartQuantity`.
8. **`vless/manager.py`** — especially `refresh_proxy_list`, `_probe_candidate`, and the pool persistence round-trip from PR #9

Then, read the plan you are about to execute (`57-01-PLAN.md`, `57-02-PLAN.md`, etc.).

---

## Execution Order

Execute the plans strictly in this sequence. Do not start N+1 until N is committed and its tests pass.

| Step | Plan | What ships | Risk |
|------|------|------------|------|
| 1 | `57-01-PLAN.md` | Distinguish `PRODUCT_GONE` / permanent VkusVill errors from transient bridge errors in the miniapp UI (surface "товар снят" icon, not red retry) | Low — UI + backend error-type passthrough, no network layer changes |
| 2 | `57-02-PLAN.md` | Cart badge ↔ drawer sync: make the optimistic counter reconcile against server truth on every POST result (success, permanent-failure, transient-failure) | Medium — touches React state management and `/api/cart/items` flow |
| 3 | `57-03-PLAN.md` | Mid-day pool re-probe: add a lightweight probe that runs every N minutes, drops nodes that fail twice in a row, and triggers an early daily-refresh if pool dips below threshold | Medium — scheduler thread + node-health tracking, no xray reload yet |
| 4 | `57-04-PLAN.md` | Live xray reconfiguration: rewrite `active.json` + SIGHUP xray when a node is dropped, without a full pool refresh | High — touches xray process lifecycle, must preserve in-flight SOCKS5 connections |

Each plan has its own `## Acceptance Criteria` section. Treat those as the gating contract. Do not claim a plan is done until every checkbox in its acceptance section is verified.

---

## Hard Rules (NON-NEGOTIABLE)

### Rule 1: One plan = one atomic commit

Each of 57-01, 57-02, 57-03, 57-04 ships as a single commit. Do not split a plan across multiple commits. Do not merge two plans into one commit.

### Rule 2: Never modify scope

Each PLAN file has `**Scope:**` with "in scope" and "out of scope" subsections. Stay inside the in-scope list. If you think you need something that is out of scope, stop, write a note in the PLAN file explaining why, and wait for human review.

### Rule 3: Do not break the Phase 56 public API

`VlessProxyManager`'s public method surface (D-09 in `56-CONTEXT.md`) must stay identical. Phase 57 may add methods. It may NOT rename, remove, or change signatures of existing methods. `get_working_proxy()` must continue to return `"127.0.0.1:10808"` whenever the pool has ≥ 1 healthy node.

### Rule 4: Retry logic stays in one place

PR #11 centralized retry in `_perform_http_request` for cart and in the `DETAIL-PROXY` block for product detail. Phase 57 MUST NOT add a second, parallel retry layer. If a plan needs different retry semantics, extend `_perform_http_request` (e.g. add an optional `max_proxy_attempts` parameter) rather than reimplementing the loop elsewhere.

### Rule 5: Tests must pass before commit

Every plan ends with `pytest` passing. Do NOT skip, delete, or weaken tests to make them pass. Locked-in behaviors from prior phases (e.g. `test_perform_http_request_falls_back_from_proxy_to_direct` expecting `_BRIDGE_RETRY_ATTEMPTS` proxied attempts + 1 direct) MUST stay intact unless the plan explicitly changes that contract and documents why.

### Rule 6: No emojis added to code

Match the existing style. The emoji in cart-add log lines (`🛒[CART-ADD]`) exists; do not remove it. Do not add new emojis in comments, docstrings, commit messages, or test assertions.

### Rule 7: Preserve error taxonomy

`cart/vkusvill_api.py` emits structured error types (`product_gone`, `vpn_detected`, `timeout`, etc.). `backend/main.py` maps these to HTTP status codes (400, 410, 503) and log lines (`[CART-ADD] PRODUCT_GONE 410`). Phase 57 MUST preserve every existing error type and MUST NOT collapse distinct upstream errors into a single bucket. New error types are additive only.

### Rule 8: Do not touch unrelated code paths

This phase is scoped to: cart-add hot path, product detail hot path, miniapp cart state, and the VLESS pool lifecycle. Do NOT touch: scraper (`scripts/scrape_green.py`), scheduler-driven cart-add (works today), history endpoints, database schema, or the Phase-56 parser/config_gen. If a test in one of those areas is already failing before you start, that is not your problem.

### Rule 9: Flakiness is real — design for it

The lesson of the v1.16 hotfix chain: the bridge IS flaky by design (free RU-exit VLESS nodes, some serving <10 req/s, some blocked mid-day). Every new code path MUST assume ≥ 1 TLS handshake timeout per minute in production. Tests MUST include a "transient error on first 2 attempts, success on 3rd" case for any new proxied request path.

### Rule 10: Network-layer + UI only

Phase 57 touches `cart/`, `backend/` (routing + error mapping), `miniapp/src/App.jsx` + related React components, and `vless/manager.py` only. Do NOT change `database/`, the scraper package, the VLESS parser, or the xray config generator. Rule 9 from Phase 56 still applies: no business-logic changes.

---

## Commit Message Convention

Each PLAN's last section specifies the exact commit message to use. Copy it verbatim. Prefix conventions used in this repo:

- `feat(<area>):` — new capability
- `fix(<area>):` — bug fix
- `chore(<area>):` — mechanical / housekeeping
- `docs(<area>):` — documentation only

Scope the commit with the phase number: end the first line with `(phase 57-NN)` so the commit is findable in `git log`.

---

## Verification Commands (for every plan)

At the end of each plan, before committing, run:

```bash
# Unit tests for the plan's test files:
pytest tests/test_<area>.py -v

# Full suite — nothing else should have broken:
pytest -v

# Ruff check — keep style consistent:
ruff check .
```

After committing, verify the commit is clean:

```bash
git log -1 --stat
git log -1 --format="%s%n%n%b"
```

---

## What the User Will Check After You're Done

When you say "phase 57 complete," the user (or a reviewer) will verify:

1. All 4 sub-plans have commits in `git log` with matching subject lines
2. `pytest -v` passes on main
3. On EC2: after ≥ 1 minute on the live miniapp, clicking add-to-cart on a `PRODUCT_GONE` item shows a distinct icon/label (not the generic red X)
4. On EC2: cart header badge always matches the drawer contents after the server reconciliation completes (within 1s of the POST result)
5. On EC2: `/api/admin/pool` shows `consecutive_failures` per node and drops any node that fails 2x in a row without a full refresh
6. On EC2: xray is hot-reloaded at least once in a 30-minute window (log line `[XRAY] reload due to node drop`) without any cart-add failures during the reload
7. `.planning/REQUIREMENTS.md` PROXY-11..14 are checked off
8. No regressions in Phase 56 acceptance (PROXY-06..10 still pass)

If ANY of these fails, the milestone is not done. Fix and re-verify.

---

## Common Pitfalls (Learned From v1.16 Hotfix Chain)

- **"I'll reduce the retry count to make tests faster."** — No. The 3-attempt retry budget is a product decision (covers ~60–70% success rate nodes). Tests should mock the clock or the httpx client, not change the retry constant.
- **"`PRODUCT_GONE` is basically the same as a timeout, I'll map both to red X."** — No. That is the exact UX bug we are fixing. Users need to know "don't retry, VkusVill removed it".
- **"The badge updates optimistically, that's fine for UX."** — Optimistic updates are fine IF they reconcile. The bug is that the cart badge keeps its optimistic increment even when the POST returns 400/410/503. Reconciliation must be unconditional on response.
- **"I'll add a second retry loop in the frontend."** — No. See Rule 4. Retries live in `_perform_http_request` (cart) and the DETAIL-PROXY block (product detail). The frontend treats the response as authoritative.
- **"Pool re-probe runs every 10 seconds to be safe."** — No. That floods the VkusVill probe endpoint and can itself get IP-flagged. Start at 5 minutes; only tighten with data.
- **"I'll hot-reload xray by killing and re-spawning it."** — No. That drops every in-flight cart-add connection. 57-04 requires xray config reload via SIGHUP or API, not process restart.

---

## When to Stop and Ask a Human

- A plan says "out of scope" but you genuinely believe a task is required → stop, document the conflict, ask
- A test in an unrelated area starts failing during your work → stop, investigate; it may be a real regression you introduced
- Pool size drops below 3 nodes during your testing → stop, do NOT refresh; a healthy pool is assumed by these plans and a low-count pool needs Phase 56-level investigation
- xray refuses to hot-reload and restart is the only option → stop, ask; 57-04 has explicit guidance that restart is forbidden on the hot path
- Miniapp cart reconciliation causes items to disappear from VkusVill (not just from the local drawer) → STOP IMMEDIATELY; that is a data-loss bug

---

## Contact / Escalation

This plan was authored by the assistant during the 2026-04-23 session after live-testing PR #11 on https://vkusvillsale.vercel.app/ and confirming the four pending symptoms listed above. Canonical references:

- `.planning/phases/56-vless-proxy-migration/README.md` — the phase this hardens
- `.planning/phases/56-vless-proxy-migration/56-CONTEXT.md` — architectural decisions (unchanged)
- PRs #4–#11 — the v1.16 hotfix chain Phase 57 builds on
- Live test report: `test_evidence/pr11-test-report.md` (in session attachments)

If the user comments during your execution and you get instructions that conflict with these plans, the user instructions take precedence. Document the deviation in the relevant `57-NN-SUMMARY.md` file.

---
