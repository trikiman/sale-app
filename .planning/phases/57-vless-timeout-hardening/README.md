# Phase 57: VLESS Timeout Hardening (v1.17) — Executing AI Orientation

**If you are an AI model tasked with executing this phase: read this file first, in full, before touching any code.**

This phase fixes the mid-connection timeout bug the user reported on 2026-04-23 against the v1.15 VLESS migration + v1.16 follow-up patches. The inspection report in `../56-vless-proxy-migration/INSPECTION-2026-04-23.md` traces **three P0 root causes** and **five symptom-level bugs** that together produce the "request starts OK, hangs, then times out" behavior.

This phase does NOT re-architect anything. It is narrow, surgical, and targeted at the specific lines identified in the inspection report. Total edit surface: ~6 files, under 100 lines of code changed.

---

## Reading Order (MANDATORY)

Read these files, in this order, before writing any code:

1. **`../56-vless-proxy-migration/INSPECTION-2026-04-23.md`** — the forensic report that diagnosed all 8 bugs. **This is your primary source of truth for WHY each fix is needed.** Every plan in this phase references specific sections of this report.
2. **`57-CONTEXT.md`** — this phase's architectural decisions and non-goals
3. **`../56-vless-proxy-migration/56-CONTEXT.md`** — to understand the original plan's D-05 (geo verification) and D-08 (leastPing deferral), both of which feed into this phase's fixes
4. **`../56-vless-proxy-migration/56-VERIFICATION.md`** — shows the 0/15 RU-egress finding that proves S5 (geo filter) is actually broken
5. The specific PLAN file you are about to execute

**Do NOT skim.** The inspection report is 500 lines and cites specific file:line locations. Those citations are your implementation contract.

---

## Execution Order

Execute the plans strictly in this sequence. Do not start N+1 until N is committed and its tests pass.

| Step | Plan | What ships | Files touched | Risk |
|------|------|------------|----------------|------|
| 1 | `57-01-PLAN.md` | xray `policy` + `observatory` + `leastPing` balancer (fixes R1, R2) | `vless/config_gen.py`, `tests/test_vless_config_gen.py` | Low — pure Python, unit-testable |
| 2 | `57-02-PLAN.md` | Python timeout alignment + `remove_proxy` rotation (fixes R3, S1, S2, S3) | `vless/manager.py`, `backend/main.py`, `cart/vkusvill_api.py`, tests | Medium — touches hot paths, needs careful timeout math |
| 3 | `57-03-PLAN.md` | Restore egress geo-verification in admission probe (fixes S5, honors D-05) | `vless/manager.py`, `vless/sources.py`, tests | Medium — re-enables a check that was explicitly removed in v1.16 PR #7 |
| 4 | `57-04-PLAN.md` | Deploy to EC2 + live verify + document v1.17 | `scripts/verify_v1_15.sh` → `scripts/verify_v1_17.sh`, `docs/PROXY_MIGRATION.md`, `57-VERIFICATION.md` | Medium — touches production |

Each plan has its own `## Acceptance Criteria` section. Treat those as the gating contract.

---

## Hard Rules (NON-NEGOTIABLE)

### Rule 1: One plan = one atomic commit

Each of 57-01, 57-02, 57-03 ships as a single commit with the message shown at the bottom of its PLAN file. 57-04 has two commits (verify-script update, EC2 verification evidence). No exceptions.

### Rule 2: Never modify scope

Each PLAN has `**Scope:**` with "in scope" / "out of scope" subsections. Stay inside. If a task seems necessary but is out of scope, stop, write a note in that PLAN file, wait for human review. Do NOT drive-by refactor.

### Rule 3: Do NOT touch the working pieces

The inspection report has a `## What I Would Not Touch` section. Read it. Treat the listed files as **read-only for this phase**:

- `vless/xray.py` — production-grade subprocess wrapper, do not modify
- `vless/installer.py` — clean, verified, do not modify
- `vless/parser.py` — works; do not change the TLS branch
- `vless/pool_state.py` — atomic writes, forward-compatible schema, do not change
- `legacy/proxy-socks5/` — archived, read-only per repo policy
- systemd units — correct; scripts/deploy_v1_17.sh may reference them but shall NOT modify them

### Rule 4: Tests before commits

Every plan ends with `pytest -v` passing on the full suite. Ruff clean. If you need to add a new test helper, add it to `tests/conftest.py` in that plan's commit.

### Rule 5: No emojis in NEW code you write

The existing code has emojis in log messages (🛒, ✅, etc.). If a file already uses emojis, match that style. Do NOT introduce emojis into files that don't have them. No emojis in commit messages, docstrings, or module headers.

### Rule 6: Commit-message convention

Each PLAN's last section specifies the exact commit message. Copy it verbatim. Scope the commit with `(phase 57-NN)` so `git log` can find it.

### Rule 7: Do NOT revive the legacy SOCKS5 rotation logic

Some of the fixes look similar to v1.0-era proxy rotation (remove_proxy on failure, next_proxy). Do NOT restore the per-host rotation loop. The new `remove_proxy(bridge_addr)` fix is a single method change, not an architectural revert.

### Rule 8: Preserve backward compatibility with the v1.16 pool JSON schema

`data/vless_pool.json` has fields `security`, `tls_sni`, `tls_allow_insecure` added in PR #9 (`2d3f6b4`). If you need to add new fields, add them optionally (default to empty), and make `_node_from_entry` tolerate their absence. An EC2 rollback to v1.16 must be able to read the v1.17-written pool file.

### Rule 9: Re-running refresh must fully rebuild xray

After 57-01 adds `observatory`, any existing `bin/xray/configs/active.json` on EC2 is stale (missing the new blocks). The deploy script in 57-04 must force a refresh on startup. Do NOT rely on the 24h refresh timer to pick up the new config.

---

## Verification Commands (for every plan)

```bash
# Plan-specific tests:
pytest tests/test_<area>.py -v

# Full suite — nothing else should have broken:
pytest -v

# Ruff check:
ruff check .

# Config round-trip smoke (confirms xray will accept the generated config):
python -m vless.sources --skip-geo
```

After committing:

```bash
git log -1 --stat   # expected files only
git log -1 --format="%s%n%n%b"   # matches the PLAN's template
```

---

## What the User Will Check After You're Done

When you say "phase 57 complete," the user / reviewer will verify:

1. All 4 sub-plans have commits in `git log` with matching subject lines
2. `pytest -v` passes on main
3. The generated xray config at `bin/xray/configs/active.json` contains `policy` and `observatory` sections
4. `curl -x socks5h://127.0.0.1:10808 https://ipinfo.io/json` through the bridge returns an RU country (egress verification now passing)
5. On EC2: `scripts/verify_v1_17.sh` all checks PASS, including step 5 (miniapp cart-add via Vercel — was skipped in v1.15)
6. The admitted pool size after refresh is ≥ 7 RU-verified nodes (not 22 mixed-egress nodes)
7. `57-VERIFICATION.md` contains real timestamped output, not templated text
8. Cart requests that previously timed out mid-connection now succeed (user confirms via miniapp)

If any of these fail, the phase is not done. Fix and re-verify.

---

## Common Pitfalls Specific to This Phase

- **"I'll raise the timeout even higher to be safe."** — No. The timeouts in 57-02 are tuned to match xray's corrected `connIdle=30s` + measured VLESS handshake cost (3-5s). Padding past 10s makes the miniapp feel sluggish. Follow the exact values in 57-02-PLAN.md.

- **"Observatory probes will burn bandwidth; I'll set a long interval."** — Default observatory probe every 5 minutes is fine. xray's `generate_204` probe is ~200 bytes per outbound per 5 min. With 22 outbounds that is 900 bytes/min = 1.3 MB/day total. Trivial.

- **"Geo-verification is slow; I'll skip it on restart and use the cached pool."** — Only geo-verify *new* candidates during admission. Already-admitted nodes in the pool file were verified at their admission time — do not re-verify on every startup. That's what the `.cache/ip_country.json` file is for.

- **"Probe through candidate to ipinfo.io requires starting a per-candidate xray."** — Correct. `_probe_candidates_in_parallel` already does this for the vkusvill probe at `vless/manager.py:623-702`. Extend the existing probe function — do NOT duplicate the subprocess spawn logic.

- **"Random balancer with observatory is good enough; leastPing adds complexity."** — No. The inspection report explicitly calls out that random across {healthy, unhealthy} is the root cause. Observatory alone only marks nodes; without `leastPing` the balancer still picks uniformly among healthy nodes. Use leastPing.

---

## When to Stop and Ask a Human

- EC2 deploy shows the new `observatory` block but xray logs say "observatory: skipped, balancer not configured" → stop, the balancer-observatory wiring is subtly misconfigured; check xray-core v24 docs
- Egress country check returns RU for a candidate but the subsequent VkusVill probe fails → not a real problem, move on (ipinfo.io and vkusvill.ru can disagree about the same IP)
- Re-enabling geo verification admits ZERO nodes → stop, the geo_providers cache may be corrupt or the consensus threshold may be too strict (currently 2/10); document and ask
- Deploy succeeds but user still reports mid-connection timeouts → stop, do NOT patch symptoms; diagnose with `bin/xray/logs/xray.log` tail and `journalctl -u saleapp-xray -n 100`

---

## Contact / Escalation

Plan authored by assistant during the 2026-04-23 post-ship inspection session. Upstream references:

- `../56-vless-proxy-migration/INSPECTION-2026-04-23.md` — the forensic report that drove this phase
- `../56-vless-proxy-migration/56-VERIFICATION.md` — shows what v1.15 actually shipped with
- `.planning/REQUIREMENTS.md` — PROXY-06..10 must stay satisfied after v1.17
- `.planning/ROADMAP.md` — v1.17 section will be added in 57-04

If user instructions during execution conflict with these plans, user instructions take precedence. Document the deviation in `57-NN-SUMMARY.md`.

---

*Phase: 57-vless-timeout-hardening*
*Plan authored: 2026-04-23*
*Executing AI: follow the plans, cite your evidence, ship the work.*
