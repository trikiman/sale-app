---
name: documenting-brainstorms
description: Use when finishing a brainstorming session, before moving to implementation, or when you have reached agreement on a design but haven't saved it to persistent memory.
---

# Documenting Brainstorms

## Overview
Brainstorming discussions happen in the chat context, which is ephemeral. If a session ends or hands off to a new session before the brainstorm is formally documented, all the design decisions, data structures, and agreed-upon approaches are lost. This skill enforces the immediate translation of chat-based brainstorms into permanent markdown design documents (`docs/memory/plans/`) **before** moving on to other tasks or handing off the session.

## When to Use

- You just finished a `@/brainstorming` workflow and the user says "looks good", "continue", or agrees to your proposed design.
- You have just figured out a complex logical problem or designed a new feature with the user in chat.
- The user asks "what's next?" after a design discussion.
- **Do NOT use:** If you are still in the middle of gathering requirements and haven't proposed a final synthesis yet.

## Core Pattern: Immediate Documentation

When a brainstorm concludes, you must **IMMEDIATELY** write the synthesis to the project's permanent memory. Do not wait for the user to ask for documentation. Do not leave it in an ephemeral task checklist. Do not assume the next agent will read the chat history.

1. **Create the Document:** Write the design to `docs/memory/plans/YYYY-MM-DD-<topic>.md`.
2. **Commit it:** Add and commit the new design document to Git so it is permanently tracked.
3. **Notify the User:** Tell the user the document has been saved locally and is ready for the next phase.

## Quick Reference: What goes in the design doc?

| Section | Content |
|---------|---------|
| **The Problem** | 1-2 sentences on what you are trying to solve. |
| **The Solution** | The agreed-upon approach and architecture. |
| **Logic/Data Flow** | Step-by-step bullet points of how the feature will work. |
| **Data Structures** | Any JSON, DB, or API schemas agreed upon during the brainstorm. |
| **Integration** | How this new feature connects to the existing codebase (files affected). |

## Anti-Patterns & Common Mistakes

| Excuse/Rationalization | Reality |
|------------------------|---------|
| "I'll just summarize it in the `CURRENT_TASK.md` Handoff block." | Handoff blocks are for immediate next steps and blockers, not entire feature specs. Design specs belong in their own files under `docs/memory/plans/`. |
| "I'll document it later when we start implementing." | Sessions crash, context limits are reached, or users log off. "Later" means lost. Document it *now*. |
| "I'll use a temporary `.gemini/artifacts/task.md` section." | Ephemeral artifacts do not persist across session boundaries. The next agent will never see it. |
| "The user didn't explicitly ask me to save it." | Users expect you to manage project state proactively. It is your job to persist agreed designs. |

## Red Flags - STOP and Start Over

**Violating the letter of the rules is violating the spirit of the rules.** If you catch yourself doing any of the following right after a brainstorm concludes, STOP, delete your response, and write the design doc:
- Saying "Great! Let's start coding this." without having written a `.md` file first.
- Proceeding to execute `@[/session-context-transfer]` without ensuring the brainstorm was saved as a standalone reference.
- Saving the outcome only to your temporary chat context.

All of these mean: **You have failed to secure the project's memory. Start over and write the `docs/memory/plans/` document.**
