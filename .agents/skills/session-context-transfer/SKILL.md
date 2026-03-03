---
name: session-context-transfer
description: Use when finishing a work session, pausing a task, handing off to a new session, or when explicitly asked by the user to save context.
---

# Session Context Transfer

## Overview
Large Language Model agents are inherently stateless across sessions. Furthermore, **session-specific artifacts (e.g., `task.md`, `implementation_plan.md` created in temporary `.codex` or `.gemini` folders) are NOT accessible to the next session**. When a session ends, granular context—like recent errors, current blockers, and immediate next steps—is lost unless explicitly recorded in persistent project files. This skill enforces a "Memory Sweep" protocol to permanently save detailed agent state into the project's local `docs/memory/` directory and `README.md`, ensuring identical context continuity for the next session.

## When to Use

- The user says they need to go, are done for the day, or asks to end the session.
- The user explicitly asks you to "save context", "write down where we are", or "prepare for handoff".
- You are pausing a major task to wait for user feedback over a long period.
- **You have just finished a `@/brainstorming` session** (or any major design discussion) and need to persist the agreed-upon architecture before the session is lost.
- **Do NOT use:** For minor operations within a continuous active session where no handoff is occurring (unless documenting a brainstorm).

## Core Pattern: The Memory Sweep

When triggered, you must perform a comprehensive "Memory Sweep" across the local `docs/memory/` directory. A simple checklist update in an ephemeral artifact is **insufficient**. You ONLY have access to `docs/` and `README.md` across sessions.

You must update the following files comprehensively before concluding your turn:

1. **`docs/memory/CURRENT_TASK.md`**
   - **Artifact Extraction:** If you wrote a detailed `implementation_plan.md` or `task.md` artifact during the session, you MUST copy the remaining uncompleted steps into `CURRENT_TASK.md`! The artifacts will be gone next session.
   - **Status/Sprint Update:** Move completed items to Sprint/Done blocks.
   - **Handoff State Block [CRITICAL]:** Write an explicit "Handoff State" section detailing:
     - What file/function is currently broken or being worked on.
     - The exact last error message or test failure encountered.
     - The immediate, precise next step the future agent should take.

2. **`docs/memory/PROJECT_CONTEXT.md` & `docs/memory/LOGIC_FLOW.md`**
   - Document any new services, architectural patterns, or fundamental logic additions made during the session.
   - Do not assume the next agent will deduce these from reading the codebase.

3. **`docs/memory/BUG_REPORT.md`**
   - Log any subtle issues, edge cases, or API quirks noticed during the session but deferred or not fully fixed.

4. **`docs/memory/plans/YYYY-MM-DD-<topic>.md` (For Brainstorms/Designs)**
   - If the session included a significant brainstorm or architectural decision, you MUST write the agreed-upon design into a dedicated markdown file in `docs/memory/plans/`. 
   - **Do not** just summarize the design in the Handoff block. The handoff block is for *next steps*, not for permanent specs. Write the full spec to a dedicated file and commit it.

## Quick Reference: Handoff State Example

```markdown
### 🛑 Handoff State (Added 2026-03-03)
- **Current Focus:** `backend/api/cart.py`
- **Current Blocker:** The `POST /api/cart/items` endpoint returns `401 Unauthorized` because the `__Host-PHPSESSID` cookie is being stripped by the proxy.
- **Next Immediate Step:** Implement cookie rewriting in the FastAPI middleware to manually inject the missing `__Host-` prefix before sending the downstream request. Do NOT attempt to use `requests.Session` as it was already tried and failed.
```

## Anti-Patterns & Common Mistakes

| Excuse/Rationalization | Reality |
|------------------------|---------|
| "I'll just do a quick update to the `task.md` checklist." | Checklists lack granular qualitative detail. Additionally, `task.md` artifacts are wiped between sessions! |
| "The next agent can just read the `implementation_plan.md`." | The next agent **cannot see** artifacts from previous sessions. They only see `docs/` and `README.md`. |
| "The git diff is enough for the next agent." | Git diffs show what changed, but they do not explain *why* something is broken currently, or what the logical next step is. |
| "I'll keep this in my conversation memory." | Your conversation memory is ephemeral and wiped upon session restart. The next session starts entirely blank. |
| "I'll just say goodbye and close the session." | Failure to run the Memory Sweep leaves the project state orphaned. |

## Red Flags - STOP and Start Over

**Violating the letter of the rules is violating the spirit of the rules.** If you catch yourself doing any of the following, STOP, delete your response, and execute the full Memory Sweep:
- Saying "Goodbye! Let me know if you need anything else." without updating the `docs/memory/` files.
- Updating only a local session artifact (`task.md`) and calling it a "handoff".
- Relying on the user to remember what needs to happen next.
- Concluding a brainstorming session and saying "Let's start coding" or "Handoff ready" without first writing a dedicated `docs/memory/plans/` design document.

All of these mean: **You have failed the context transfer. Start over and run the full Memory Sweep.**
