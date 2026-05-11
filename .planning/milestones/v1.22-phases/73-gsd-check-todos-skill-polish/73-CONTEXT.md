# Phase 73 — gsd-check-todos Skill Polish — Context

**Milestone:** v1.22 UX Debt Cleanup + Tooling Polish
**Phase number:** 73
**Phase slug:** gsd-check-todos-skill-polish
**Date captured:** 2026-05-12
**Requirements covered:** TOOL-01 + continuing OPS-15/16/17

---

## Domain

Original 2026-05-12 todo: `/gsd-check-todos` today lists todos with title + area + age. Doesn't surface priority, doesn't correlate with roadmap, doesn't support multi-select for fold-into-milestone. With 5+ open items (some P1 reliability, some P3 polish), the flat list makes triage slow.

This is a Kiro-side polish. It edits skill files under `~/.kiro/` and the gsd-tools CLI at `~/.kiro/get-shit-done/bin/lib/init.cjs`. **No product-code changes, no EC2 deploy.** Runs locally only.

Scope chosen from TOOL-01 SPEC Lock:
- Add `priority: P1|P2|P3|P4` frontmatter to todos; default P3 for existing/silent todos.
- Sort the list P1 → P4, then by age (oldest first within priority).
- Document frontmatter schema in SKILL.md.
- Update the 1 remaining pending todo in-place with an explicit priority value (and the 3 already-consumed ones too since they still have "skeleton" frontmatter).

**Out of scope for Phase 73:**
- `fold into milestone` multi-select (deferred — needs AskUserQuestion multi-select which doesn't exist in current Kiro tooling; capture as v1.23 candidate).
- `--by-area` flag (deferred — the priority sort covers the primary user need; area grouping can be added later without breaking change).
- Roadmap correlation enhancement (workflow already does per-todo match; no change here).

---

## SPEC Lock

LOCKED — planner must NOT re-litigate:

- **Frontmatter:** add `priority: P1|P2|P3|P4` as a new optional field. Existing todos without the field default to P3. Validation: any value outside `P1|P2|P3|P4` is also treated as P3.
- **Semantics:**
  - P1 = critical reliability / active production impact (bugs that block users, outage triggers).
  - P2 = user-visible defect or v.N gap that didn't get closed (history search regression, admin badge never wired).
  - P3 = UX refinement / nice-to-have (copy clarification, minor visual polish). Default.
  - P4 = tooling / developer-experience (skills, scripts, workflow).
- **CLI change:** `cmdInitTodos` in `~/.kiro/get-shit-done/bin/lib/init.cjs` parses the new field, emits it in the JSON output, and sorts by `(priorityRank, created_ts)`. Rank: P1→1, P2→2, P3→3, P4→4.
- **Workflow change:** `~/.kiro/get-shit-done/workflows/check-todos.md` reflects new list format with priority badges.
- **SKILL.md change:** documents the frontmatter schema block and notes P3 default.
- **Backward compat:** todos with NO priority field still work (default P3). No migration script required.
- **In-tree todo updates:** the 4 currently pending + 3 just-completed todos get explicit priority values added in-place. They're under .planning/todos/ which IS in the workspace.
- **No unit tests for the CLI:** the gsd-tools CLI doesn't have a test suite in this repo; validation is "run `init todos` and see the new fields + ordering".

---

## Decisions

### D1. Why priority as frontmatter, not filename prefix

Filename-encoding priority would require renaming every todo when its priority changes. Frontmatter is plain edit-in-place. Also keeps the existing filename date-prefix convention intact (sortable chronologically at the filesystem level).

### D2. Why P1-P4 not P0-P4

P0 typically means "drop everything and fix right now" — a different category than milestone candidates. Todos that demand P0 treatment usually become hotfixes, not pending items. Starting at P1 keeps the ladder clean.

### D3. Default to P3

Most todos captured during work are "nice to have" UX or dev-experience items. Defaulting to P3 matches captured reality. Users who want to mark something urgent explicitly write `priority: P1`.

### D4. Sort tiebreaker is age, not title

Within the same priority, the operator wants oldest-first — a P2 from April 2 is more likely being lost to drift than a P2 from May 12. Title-sort would hide chronologically stale items.

### D5. No unit tests in this phase

gsd-tools at `~/.kiro/get-shit-done/bin/` is a Kiro-managed CLI without a test harness in this project repo. Adding one is out of scope for this 4-phase milestone. Validation is visible: run `init todos` before + after, confirm priority field + sorting appear.

### D6. fold-into-milestone deferred

Multi-select UI requires AskUserQuestion's multi-select mode which doesn't exist in current Kiro tooling. When Kiro gets multi-select, we can reopen this as a v1.23 or later polish. Single-select "Add to phase plan" (existing) + "Create a phase" (existing) already cover the primary fold pattern.

---

## Locked Defaults

- Frontmatter key: `priority`
- Valid values: `P1`, `P2`, `P3`, `P4` (case-sensitive; uppercase P)
- Default on missing/invalid: `P3`
- CLI field name in JSON output: `priority` (matches frontmatter verbatim)
- Sort: primary `(P1=1, P2=2, P3=3, P4=4)`, secondary `created` ISO timestamp ascending (oldest first)

---

## Files Modified

- `~/.kiro/get-shit-done/bin/lib/init.cjs`:
  - `cmdInitTodos` parses `priority` field from frontmatter.
  - Emits `priority` in each todo object.
  - Sorts `todos` array by `(priorityRank, created_ts)`.
- `~/.kiro/skills/gsd-check-todos/SKILL.md`:
  - Adds a new "## Todo Frontmatter Schema" section documenting all fields including priority.
- `~/.kiro/get-shit-done/workflows/check-todos.md`:
  - `list_todos` step updated to include priority badge in display.
  - Example list format includes `[P1]` / `[P2]` / `[P3]` / `[P4]` prefix.
- In-tree todos (workspace — commitable):
  - `.planning/todos/pending/2026-05-12-update-gsd-check-todos-skill.md` → add `priority: P4`.
  - `.planning/todos/completed/2026-04-02-history-search-...` → add `priority: P2` (consumed by Phase 70).
  - `.planning/todos/completed/2026-04-06-clarify-stale-banner-...` → add `priority: P3` (consumed by Phase 71).
  - `.planning/todos/completed/2026-05-10-v1-16-admin-html-bug-reports-badge-missing.md` → add `priority: P2` (consumed by Phase 72).
- `scripts/verify_v1.22.sh` Phase 73 block:
  - 73-A: priority field present in this todo.
  - 73-B: skill/workflow files on disk contain the new schema doc.
  - 73-C: running `init todos` locally returns the priority field and sorted order.

---

## Verification

- Local: `node ~/.kiro/get-shit-done/bin/gsd-tools.cjs init todos` shows `priority` field in each todo.
- Smoke 73-A/B/C: file-presence greps (no EC2 needed; this is skill-file-only).
- NEEDS_OPERATOR (73-VERIFICATION.md):
  - Re-invoke `/gsd-check-todos` in Kiro and confirm the list displays priority-first sorted + priority badges visible.
  - Rollback rehearsal: git revert the .planning/todos changes; skill/workflow/CLI edits sit outside the repo so revert is a manual `git -C ~/.kiro` equivalent (documented, not rehearsed automatically).
  - v1.21 + v1.20 + v1.19 regression green.

---

## Phase Boundary

**Ships:** `priority` frontmatter support + P1-first sort + documentation + 4 in-tree todo priority annotations + smoke 73-A/B/C.

**Does NOT ship:**
- `fold into milestone` multi-select (deferred to v1.23+ when multi-select tooling exists)
- `--by-area` flag (deferred — sort-by-priority is the primary value)
- Roadmap-correlation enhancement (already adequate)
- Unit tests for gsd-tools CLI (no test harness in scope)

**Acceptance gate:** `init todos` returns priority field + sorts correctly + SKILL.md documents the schema + in-tree todos carry explicit priorities.
