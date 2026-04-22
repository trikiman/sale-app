# Phase 56: VLESS Proxy Migration — Executing AI Orientation

**If you are an AI model tasked with executing this phase: read this file first, in full, before touching any code.**

This directory contains the complete plan for replacing the dead free-SOCKS5 proxy pool with a VLESS+Reality pool tunneled through a local `xray-core` SOCKS5 bridge. The plan is designed to be executed autonomously, one sub-plan at a time, with atomic commits and passing tests at every step.

---

## Reading Order (MANDATORY)

Read these files, in this order, before writing any code:

1. **`.planning/REQUIREMENTS.md`** — the 5 acceptance requirements (PROXY-06 through PROXY-10)
2. **`.planning/ROADMAP.md`** — the v1.15 section, includes the 6-point milestone success criteria
3. **`56-CONTEXT.md`** — architectural decisions (D-01 through D-09), canonical refs, code context, what is out of scope
4. **`proxy_manager.py`** (full file, 697 lines) — the existing implementation you are replacing. Your new `VlessProxyManager` must preserve its public API exactly.
5. **`scripts/geo_providers.py`** — the geo-IP resolver you will reuse (do not rewrite)
6. **`scripts/test_ru_proxy_pipeline.py`** — the proxy-testing pipeline you will draw patterns from (classification taxonomy, parallel probing)
7. **`.cache/alive_ru_proxies.json`** — the 2026-04-22 snapshot documenting why we are migrating (0/269 alive)

Then, read the plan you are about to execute (`56-01-PLAN.md`, `56-02-PLAN.md`, etc.).

---

## Execution Order

Execute the plans strictly in this sequence. Do not start N+1 until N is committed and its tests pass.

| Step | Plan | What ships | Risk |
|------|------|------------|------|
| 1 | `56-01-PLAN.md` | VLESS URL parser + xray config generator (pure Python) | Lowest — no external deps, no runtime integration |
| 2 | `56-02-PLAN.md` | xray-core installer + subprocess wrapper | Medium — external binary, OS differences |
| 3 | `56-03-PLAN.md` | `VlessProxyManager` drop-in replacement | High — API compatibility contract, process ownership |
| 4 | `56-04-PLAN.md` | Archive SOCKS5 + install shim (single atomic commit) | Medium — rollback contract, `git mv` history preservation |
| 5 | `56-05-PLAN.md` | Deploy to EC2 + live verify + rehearse rollback | High — touches production |

Each plan has its own `## Acceptance Criteria` section. Treat those as the gating contract. Do not claim a plan is done until every checkbox in its acceptance section is verified.

---

## Hard Rules (NON-NEGOTIABLE)

### Rule 1: One plan = one atomic commit

Each of 56-01, 56-02, 56-03, 56-04 ships as a single commit with the message shown at the bottom of its PLAN file. Do not split a plan across multiple commits. Do not merge two plans into one commit. 56-05 has two commits (deploy infra + verification evidence) — that is the only exception.

### Rule 2: Never modify scope

Each PLAN file has `**Scope:**` with "in scope" and "out of scope" subsections. Stay inside the in-scope list. If you think you need something that is out of scope, stop, write a note in the PLAN file explaining why, and wait for human review. Do NOT silently extend scope. Do NOT "drive-by refactor" neighboring code.

### Rule 3: Read before writing

When a PLAN says "read X first," read it in full. Do not skim. The plans reference specific line ranges and specific method signatures — those matter. Do not reinvent anything that already exists (especially `scripts/geo_providers.py` — use it as-is).

### Rule 4: Tests must pass before commit

Every plan ends with `pytest` passing. If tests fail, fix them before committing. Do NOT commit with failing tests and a "will fix in next plan" note. Do NOT skip, delete, or weaken tests to make them pass. If a test needs to be changed, the change must make it a stronger test, not a weaker one.

### Rule 5: No emojis in code

The existing code uses emojis in log messages (✅, ❌, 🔄, etc.). Match the existing style. Do NOT add emojis elsewhere (comments, docstrings, commit messages) unless the existing code in that file already uses them.

### Rule 6: Preserve data file schemas

`data/proxy_events.jsonl` and `.cache/vkusvill_cooldowns.json` have schemas that downstream tools read. Do NOT change their schemas. Add new event types, do not rename existing ones. Read 56-CONTEXT.md `<code_context>` for the exact schemas.

### Rule 7: Preserve the public API

`VlessProxyManager` must have every public method that `ProxyManager` has today, with matching signatures. 56-03 includes a table of every method and how its semantics translate. If you find a method that is not in the table and is used by a caller, stop and add it. Do NOT silently drop methods.

### Rule 8: Never commit the xray binary

`bin/` is gitignored in 56-02. The xray binary is downloaded per-machine. Do NOT add `bin/**/xray` or `bin/**/xray.exe` to git.

### Rule 9: No business-logic changes

This milestone is network-layer only. Do NOT touch `cart/`, `database/`, `miniapp/`, or anything under `backend/` except systemd-related. If a test of one of those areas is already failing before you start, that is not your problem — do not try to fix it.

---

## Commit Message Convention

Each PLAN's last section specifies the exact commit message to use. Copy it verbatim. Prefix conventions used in this repo:

- `feat(<area>):` — new capability
- `chore(<area>):` — mechanical / housekeeping
- `fix(<area>):` — bug fix
- `docs(<area>):` — documentation only
- `feat(ops):` — operational / deploy / systemd work

Scope the commit with the phase number: end the first line with `(phase 56-NN)` so the commit is findable in `git log`.

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

# Find any accidental emoji additions (if you're uncertain):
python -c "import re; import sys; [print(p, l, re.search(r'[\\U0001F300-\\U0001FAFF\\U00002600-\\U000027BF]', open(p,encoding='utf-8').read())) for p in sys.argv[1:]]" <your-new-files>
```

After committing, verify the commit is clean:

```bash
git log -1 --stat  # expected files only
git log -1 --format="%s%n%n%b"  # commit message matches the PLAN's template
```

---

## What the User Will Check After You're Done

When you say "phase 56 complete," the user (or a reviewer) will verify:

1. All 5 sub-plans have commits in `git log` with matching subject lines
2. `pytest -v` passes on main
3. On EC2: `systemctl is-active saleapp-xray` = `active`
4. On EC2: `scripts/verify_v1_15.sh` all 5 checks PASS
5. `legacy/proxy-socks5/proxy_manager.py` exists with full history (`git log --follow` shows v1.0-era commits)
6. `proxy_manager.py` is the shim (≤ 30 lines of executable code)
7. `docs/PROXY_MIGRATION.md` exists and is actually useful, not boilerplate
8. `56-VERIFICATION.md` contains real timestamped output, not templated text
9. `.planning/REQUIREMENTS.md` PROXY-06..10 are checked off
10. `git revert <56-04 commit>` would restore the old SOCKS5 code path (verified by 56-05 rehearsal)

If ANY of these fails, the milestone is not done. Fix and re-verify.

---

## Common Pitfalls (Learned From This Codebase's Prior Milestones)

- **"I'll fix that test later."** — No, you won't. v1.13 shipped with broken cart-add because tests were green on the paper path. Every test must exercise real behavior, and regressions must be caught before commit.
- **"This constant is unused, I'll remove it."** — Don't. Many constants in this repo are referenced by name in log-parsing scripts or in admin endpoints. Only remove after grepping the whole repo including `.planning/` and confirming no references.
- **"The old code is ugly, I'll clean it up while I'm there."** — No. Each plan is scoped. Cleanup is a separate milestone (or it lives in `legacy/` forever, which is also fine).
- **"xray logs are empty, it must be working."** — No. Verify with `curl --socks5-hostname 127.0.0.1:10808 https://ipinfo.io/json` and check the country. An xray that silently exits with no error still leaves an empty log.
- **"The pool has 0 nodes after first refresh, I'll add a fallback."** — No. Fail loud. Pool=0 after a refresh is a real failure that a human needs to see. Do not paper over it by silently using direct connection.
- **"Ruff complains about line length, I'll add `# noqa`."** — Only if the existing file uses `# noqa` already. Otherwise, wrap the line.

---

## When to Stop and Ask a Human

- A plan says "out of scope" but you genuinely believe a task is required → stop, document the conflict, ask
- A test in an unrelated area starts failing during your work → stop, investigate; it may be a real regression you introduced
- The VLESS source URL (`igareck/vpn-configs-for-russia`) returns HTTP error or no RU nodes → stop, document, ask (may need to pick a different source, which is a planning decision)
- xray-core v24.11.30 (pinned version) no longer exists on GitHub → stop, ask; do NOT auto-latest
- EC2 deployment fails and rollback rehearsal also fails → STOP IMMEDIATELY, do not retry; ask for human review — double-failure indicates a deeper bug

---

## Contact / Escalation

This plan was authored by the assistant during the 2026-04-22 planning session. Canonical references:

- `56-CONTEXT.md` — architectural decisions
- `.planning/REQUIREMENTS.md` — user-visible acceptance contract
- `.planning/ROADMAP.md` — v1.15 section with 6-point success criteria
- Prior milestone archives in `.planning/milestones/v1.14-*` — for understanding the milestone pattern in this repo

If the user comments during your execution and you get instructions that conflict with these plans, the user instructions take precedence. Document the deviation in the relevant `56-NN-SUMMARY.md` file.

---

*Phase: 56-vless-proxy-migration*
*Plan authored: 2026-04-22*
*Executing AI: follow the plans, cite your evidence, ship the work.*
