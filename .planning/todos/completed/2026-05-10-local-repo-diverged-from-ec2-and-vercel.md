---
created: 2026-05-10T16:26:37Z
title: local repo diverged from EC2 and Vercel production branches
area: planning
files:
  - .planning/STATE.md (claims v1.16 is current milestone)
  - .planning/ROADMAP.md (lists phases 59-61)
---

## Problem

Discovered 2026-05-10. Three environments are on three different code states:

- Local (where this session ran): HEAD b1d3b04, milestone v1.16 (phases 59-61 Bug Reports). Last feature commits 7f59f1a + f4f4ae5 + 68623c3 on 2026-04-28.
- EC2 production (ubuntu@13.60.174.46): HEAD a7ab226, running v1.20 development (phase 62 sessid keep-alive, phase 61 deep health endpoint, phase 60 observatory probeURL + 3-state breaker, phase 59 preflight probe). Includes commits local never saw.
- Vercel production (vkusvillsale.vercel.app): serving bundle index-DFayy0r0.js which contains NO BugReportPanel, NO consoleBuffer, NO bug emoji. Predates 2026-04-28 v1.16 frontend work.

Implication: the STATE.md / ROADMAP.md in local treats v1.16 as "implemented, awaiting live verification" but EC2 moved 3 milestones ahead (v1.17, v1.18, v1.19) without the v1.16 feature. v1.20 phase 62 (sessid warmup) is being planned on EC2 while local is still testing v1.16.

This is why:
1. /api/bug-reports returns 404 on prod (backend never got v1.16)
2. MiniApp shows no bug-report button (Vercel never got v1.16 frontend)
3. EC2 code has circuit breaker, observatory, pool_snapshot, /api/health/deep — none of which are in local
4. git fetch origin shows no new commits because these were committed DIRECTLY ON EC2, never pushed back

Root cause is likely that someone ran Devin or Claude-on-EC2 sessions that wrote commits locally on EC2 and deployed by committing-and-restarting, never pushing back to origin.

## Solution

TBD. Three steps:

1. Inventory: ssh to EC2, run git log --oneline origin/main..HEAD and git diff origin/main --stat to see exactly what diverged.
2. Decide: (a) merge EC2 v1.17-v1.20 changes back into origin/main and rebase local on top of them; (b) cherry-pick local v1.16 feature commits onto EC2 and deploy; (c) call one source-of-truth and revert the other.
3. Prevent: auto-deploy hook should pull from GitHub, not do local-on-EC2 edits. Or add a pre-commit hook on EC2 that blocks non-pushed commits.

Related:
- v1-16-backend-not-deployed-to-ec2 (downstream effect)
- v1-16-miniapp-not-deployed-to-vercel (downstream effect)
- v1-16-admin-html-bug-reports-badge-missing (separate gap, exists even after merge)
