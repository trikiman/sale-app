---
created: 2026-05-12T15:45:00Z
title: Update /gsd-check-todos skill to support priority display + multi-select
area: tooling
files:
  - ~/.kiro/skills/gsd-check-todos/SKILL.md
  - ~/.kiro/get-shit-done/workflows/check-todos.md
---

## Problem

Running /gsd-check-todos today just prints title + area + age. It doesn't surface priority (P1/P2/P3), doesn't correlate with roadmap, doesn't support multi-select for fold-into-milestone, and the init todos tool returns a flat array — no P1-first sort, no grouping by area.

For the VlusVill saleapp this was fine when there were 2-3 todos. With 5+ open items (some P1 affecting reliability, some P3 UX polish), the flat list makes it hard to triage.

## Solution

TBD. Candidates:

1. Add `priority` field to the frontmatter schema (P1/P2/P3) and sort the list by priority first, then by age. Existing todos default to P3 if unset.
2. Add a roadmap-correlation column: for each todo, check if area matches any active phase and show `→ Phase N` if yes.
3. Add "fold into milestone" as an option in the action menu — when no active milestone, offer to spawn /gsd-new-milestone with selected todo scopes.
4. Add a grouping flag: `/gsd-check-todos --by-area` or `--by-priority`.
5. Document the frontmatter schema somewhere (currently it's just area/files/created, implicit).

Start with (1) + (3) — those are the immediate value. (2) and (4) are polish.
