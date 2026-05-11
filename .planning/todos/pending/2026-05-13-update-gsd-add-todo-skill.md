---
created: 2026-05-13T01:25:00Z
title: Update /gsd-add-todo skill to match /gsd-check-todos priority frontmatter
area: tooling
priority: P4
files:
  - ~/.kiro/skills/gsd-add-todo/SKILL.md
  - ~/.kiro/get-shit-done/workflows/add-todo.md
  - ~/.kiro/get-shit-done/bin/lib/init.cjs (may need capture-time priority inference)
---

## Problem

v1.22 Phase 73 added `priority: P1|P2|P3|P4` frontmatter to todos + P1-first sort to `/gsd-check-todos`. But the **sibling skill** `/gsd-add-todo` wasn't updated — new todos captured via the skill don't get a priority field written at capture time.

Consequence: every auto-captured todo defaults to P3 (the loader's default), which is mostly fine but loses information the operator could provide at capture time.

User-reported 2026-05-13: "also updated /gsd-add-todo" → same skill update.

## Solution

### SKILL.md and workflow

- Workflow reads the new priority ladder doc from `/gsd-check-todos` (P1/P2/P3/P4 — same semantics).
- On capture, if the user's description strongly hints at urgency (e.g. "crash", "outage", "broken", "blocked"), **offer** to set priority to P1 or P2 via AskUserQuestion with 4 options.
- If the description is more UX-polish tone ("nice to have", "polish", "copy clarification"), **default** to P3 silently.
- If the area is `tooling`, default to P4.
- Always write the `priority:` line into the frontmatter regardless of value.

### Optional keyword-based priority inference heuristic

Rough first pass for the AskUserQuestion prompt:

```
P1 keywords: outage, blocks, crash, 500, data loss, can't deploy
P2 keywords: broken, regression, users see, mismatch, visible, bug
P3 keywords: polish, ux, clarify, copy, improve (default)
P4 keywords: tooling, skill, workflow, script, dx
```

Area-based defaults:
- `reliability`, `api` with crash/outage keywords → P1
- `ui`, `api` with regression/bug keywords → P2
- `ui` without specific signal → P3
- `tooling` → P4

### Frontmatter capture logic in the workflow

Existing `/gsd-add-todo` workflow probably already writes `created`, `title`, `area`, `files`. Add:

```yaml
priority: <inferred-or-asked>
```

Keep it optional in the writer — missing fallback stays P3 at read time.

### Validation against existing todos

Running `node ~/.kiro/get-shit-done/bin/gsd-tools.cjs init todos` after this change should still work: existing todos without `priority` fall back to P3, new todos carry explicit values.

## Acceptance

- [ ] `/gsd-add-todo` workflow updated to optionally capture priority at capture time.
- [ ] When urgency keywords detected in the description, ask user via AskUserQuestion to confirm P1/P2/P3/P4.
- [ ] When no strong signal, default silently to P3 (or P4 for tooling area).
- [ ] Frontmatter schema doc in `/gsd-check-todos` SKILL.md links to `/gsd-add-todo` SKILL.md and vice versa.
- [ ] New todos created via the skill have explicit `priority:` line in frontmatter.
- [ ] Existing todos without priority continue to default to P3 at read time (no migration required).

## Candidate for

v1.23 or a `/gsd-quick` task — fully Kiro-side, no product code, ~40 LOC workflow edit. Natural pair with v1.22 Phase 73's `/gsd-check-todos` polish.
