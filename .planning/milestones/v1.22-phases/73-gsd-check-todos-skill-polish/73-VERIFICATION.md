# Phase 73 Verification — /gsd-check-todos Skill Polish

## Status: CODE SHIPPED locally; Kiro-side only, no EC2 deploy required

**Ships locally:**
- [x] 73-01 `~/.kiro/get-shit-done/bin/lib/init.cjs` `cmdInitTodos` priority parsing + sort (commit `43b4fc8`)
- [x] 73-01 `~/.kiro/skills/gsd-check-todos/SKILL.md` frontmatter schema doc (commit `43b4fc8`)
- [x] 73-01 `~/.kiro/get-shit-done/workflows/check-todos.md` priority-badge display (commit `43b4fc8`)
- [x] 73-01 4 in-tree todo files annotated with explicit priority (commit `43b4fc8`)
- [x] 73-01 In-tree post-73 snapshots of modified files (commit `43b4fc8`)
- [x] 73-02 `scripts/verify_v1.22.sh` + `scripts/_ec2_smoke_v122.sh` Phase 73 block + this runbook (this commit)
- [x] Local smoke `bash scripts/verify_v1.22.sh 73` = 3/3 green
- [x] CLI validation: `node ~/.kiro/get-shit-done/bin/gsd-tools.cjs init todos` emits `priority` field; synthetic P1 fixture sorts before pre-existing P4 todo despite newer timestamp
- [x] `bash -n scripts/verify_v1.22.sh` exit 0

**NEEDS_OPERATOR:**

### NEEDS_OPERATOR-1: Re-invoke `/gsd-check-todos` in Kiro

After a Kiro context reload (or just on next skill invocation), run:

```
/gsd-check-todos
```

Confirm:
- List header reads "Pending Todos (by priority):"
- Each row is prefixed with `[P1]` / `[P2]` / `[P3]` / `[P4]` badge
- Order is P1 first, then P2/P3/P4 in rank order
- Within the same priority, oldest first

The Kiro skill cache may need a reload via `/gsd-health` or a restart to pick up the SKILL.md + check-todos.md changes — the CLI changes (init.cjs) are picked up immediately.

### NEEDS_OPERATOR-2: Cross-version regression

```bash
bash scripts/verify_v1.22.sh 70    # 3/3 expected
bash scripts/verify_v1.22.sh 71    # 3/3 expected
bash scripts/verify_v1.22.sh 72    # 4/4 expected
bash scripts/verify_v1.22.sh 73    # 3/3 expected
bash scripts/verify_v1.22.sh all   # all v1.22 + v1.21 13/13 + v1.20 19/19 + v1.19 24/24
```

### NEEDS_OPERATOR-3: Rollback rehearsal

Kiro-side files live outside this repo, so rollback is:

```bash
# Restore CLI + skill + workflow from the backups taken in 73-01:
cp ~/.kiro/get-shit-done/bin/lib/init.cjs.bak-pre73 ~/.kiro/get-shit-done/bin/lib/init.cjs
cp ~/.kiro/skills/gsd-check-todos/SKILL.md.bak-pre73 ~/.kiro/skills/gsd-check-todos/SKILL.md
cp ~/.kiro/get-shit-done/workflows/check-todos.md.bak-pre73 ~/.kiro/get-shit-done/workflows/check-todos.md

# In-tree revert:
git revert 43b4fc8    # reverts the 4 todo frontmatter annotations + snapshots

# Verify CLI no longer emits priority field:
node ~/.kiro/get-shit-done/bin/gsd-tools.cjs init todos | grep -c priority
# Expect: 0
```

The `.bak-pre73` suffix files are kept next to the live files as long as needed for rollback safety.

## Success Criteria

| Criterion | Status | Evidence |
|---|---|---|
| 1. `cmdInitTodos` parses priority frontmatter (default P3) | code_complete | commit `43b4fc8` + live CLI output shows `"priority": "P4"` |
| 2. `cmdInitTodos` sorts P1 → P4, then oldest-first | code_complete | synthetic P1 fixture test — P1 sorted before existing P4 despite newer ts |
| 3. SKILL.md documents frontmatter schema + priority ladder | code_complete | appended via Add-Content; snapshot captured in `SKILL.md.post73` |
| 4. Workflow displays `[P1]`..`[P4]` badges in list | code_complete | `check-todos.md` `list_todos` step updated; snapshot in `check-todos.md.post73` |
| 5. 4 in-tree todos annotated with explicit priority (P4, P2, P3, P2) | code_complete | frontmatter updates |
| 6. In-tree snapshots preserve the changed files in git history | code_complete | `.post73` files in phase dir |
| 7. Smoke 73-A/B/C green locally | code_complete | `bash scripts/verify_v1.22.sh 73` 3/3 green |
| 8. `/gsd-check-todos` renders priority-sorted in Kiro | needs_operator | NEEDS_OPERATOR-1 |
| 9. Cross-version regression green | needs_operator | NEEDS_OPERATOR-2 |
| 10. Rollback rehearsal green | needs_operator | NEEDS_OPERATOR-3 |

## Phase Boundary

**Ships:** `priority` frontmatter support + P1-first sort + SKILL.md schema doc + workflow badge display + 4 in-tree todo annotations + snapshots + smoke 73-A/B/C.

**Does NOT ship:**
- `fold into milestone` multi-select (deferred — AskUserQuestion multi-select doesn't exist in current Kiro tooling; candidate for v1.23+)
- `--by-area` flag (deferred — priority sort covers the primary value)
- Roadmap-correlation enhancement (workflow already does adequate per-todo match)
- Unit tests for gsd-tools CLI (no test harness in scope for this repo)

**Acceptance gate:** smoke 3/3 green + Kiro `/gsd-check-todos` displays priority-sorted list with badges.
