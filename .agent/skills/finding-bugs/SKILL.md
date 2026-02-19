---
name: finding-bugs
description: Use when reviewing code for defects, doing pre-commit checks, analyzing a PR, auditing a module for correctness, or whenever asked to "find bugs", "check for issues", or "audit this code"
---

# Finding Bugs

## Overview

Reactive debugging reacts to failures. **Bug finding is proactive** — you inspect code before it fails.

**Core principle:** Bugs hide in predictable places. Systematic category-by-category inspection finds them; skimming misses them.

## When to Use

- Code review / PR audit
- Pre-commit self-review
- "Find any bugs in this file"
- Preparing code for production
- After a major refactor
- Security audit

**NOT for:** Investigating a known failure (use `systematic-debugging` for that)

## The Five-Category Sweep

Work through **all five categories**. Don't stop after finding one bug — there are usually more.

---

### Category 1 — Logic Errors

| Pattern | What to look for |
|---------|-----------------|
| Off-by-one | `<` vs `<=`, array bounds, slice indices |
| Wrong operator | `&&` vs `\|\|`, `=` vs `==`, `is` vs `==` in Python |
| Incorrect condition | Negation errors, flipped comparisons |
| Short-circuit side effects | `a && sideEffect()` — effect skipped when `a` is false |
| Unreachable code | Conditions that can never be true |
| Wrong variable | Typo using `userId` instead of `productId` |
| **Over-strict filter → silent empty result** | Filter condition that happens to exclude ALL items in a specific context (e.g., checking for text label `"В наличии"` on products that don't use that label). No exception is raised — output is silently empty. A save guard (`if not products: skip`) then preserves the old stale file. Bug is invisible: script exits 0, no error logged. **Red flag: output file mtime never advances.** |
| **Copy-paste logic mismatch across entity types** | Logic correct for Type A copy-pasted to Type B where it doesn't apply (e.g., stock-count label filter designed for "limited stock" products applied to "card discount" products that show only "В корзину"). Always verify that each type-specific code path matches the actual data contract for THAT type. |

**How to review:** Read each condition aloud as English. "If user is NOT admin OR NOT logged in..." — does that match intent?

**For scraper/data-pipeline code specifically:**
1. Run the scraper and check the **output file mtime** — was it actually updated?
2. Check the **output count** — is it > 0? Consistent with previous runs?
3. Check a **sample record** — do fields like `stock`, `oldPrice` have reasonable values or suspicious defaults (0, 1, null)?
4. If count=0 or mtime unchanged: the save guard silently skipped saving — look for over-strict filters.

---

### Category 2 — Null / Undefined / Empty

| Pattern | What to look for |
|---------|-----------------|
| Missing null guard | `obj.field` without checking `obj != null` |
| Empty collection assumed non-empty | `list[0]` on potentially empty list |
| Uninitialized variable used | Variable declared, never assigned before use |
| Optional chaining gap | `a?.b.c` — `.c` still throws if `b` is null |
| Default value wrong | `default=[]` mutable default in Python |

**Quick check:** For every variable first used inside a block, ask: "Can this be null/undefined/empty here?"

---

### Category 3 — Resource & Concurrency

| Pattern | What to look for |
|---------|-----------------|
| Unclosed resource | File/DB/socket opened without `finally` / context manager / `using` |
| Race condition | Shared state read-modify-write without lock |
| Deadlock risk | Two locks acquired in different order in different places |
| Missing await | Async function called without `await` (result is a Promise, not value) |
| Thread-unsafe singleton | Lazy-init checked without synchronization |
| Memory leak | Object added to global list/cache, never removed |
| **Hanging subprocess** | Process launched but never produces a completion entry (OK or ERROR) — hangs silently, invisible unless you count |
| **Single-run sampling bias** | Checking only the one successful run in a repeated scheduler masks persistent failures in other runs |

**Quick check:** Search for `open(`, `connect(`, `new Thread(`, `setTimeout` — trace each to its close/cleanup.

**For scheduled/parallel systems:** Count launch lines vs completion lines across **ALL runs** in the log. A "Launching X" with no matching "OK: X" or "ERROR: X" before the next cycle starts = hanging subprocess. Never declare "working" from a single successful run — read all runs.

---

### Category 4 — Error Handling

| Pattern | What to look for |
|---------|-----------------|
| Swallowed exception | `catch (e) {}` or `except: pass` |
| Too-broad catch | `catch (Exception e)` catches programmer errors too |
| Error ignored on return | Return value checked nowhere (`if err != nil` missing in Go) |
| Wrong error type thrown | Throwing generic `Error` instead of domain-specific |
| Partial failure not rolled back | Step 1 succeeds, step 2 fails, step 1 not undone |
| Retry without backoff | Immediate infinite retry hammers a down service |

---

### Category 5 — Security & Input Validation

| Pattern | What to look for |
|---------|-----------------|
| Injection | User input concatenated into SQL/shell/HTML |
| Path traversal | `../` in user-supplied filename |
| Hardcoded secret | `password = "abc123"` or API key in source |
| Insecure comparison | `==` for hashes/tokens (timing attack); use constant-time compare |
| Missing auth check | Endpoint/function callable without verifying identity |
| Over-permissive CORS | `Access-Control-Allow-Origin: *` on sensitive API |
| Prototype pollution | Merging user-supplied object into `{}` in JS |

---

## Reporting Bugs Found

For each bug:

```
[CATEGORY] Short description
  File: path/to/file.py  Line: 42
  Why it's a bug: <one sentence>
  Reproducer: <minimal scenario or None if obvious>
  Severity: Critical / High / Medium / Low
  Fix: <concrete suggestion>
```

**Severity guide:**

| Level | Criteria |
|-------|----------|
| Critical | Data loss, security breach, crash in hot path |
| High | Wrong output silently, common path error |
| Medium | Edge case failure, degraded performance |
| Low | Code smell, future maintainability risk |

---

## Quick Reference — High-Yield Bug Locations

Spend extra time on these areas — they account for ~70% of bugs:

1. **Boundary conditions** — first item, last item, empty, single item, max value
2. **Caller/callee contract** — does caller guarantee what callee assumes?
3. **Error paths** — lines that only run when something goes wrong
4. **Concurrency entry points** — anything touched by multiple threads/tasks
5. **External input** — HTTP params, file content, env vars, CLI args

---

## Common Rationalization Traps

| Thought | Reality |
|---------|---------|
| "This is simple code, no bugs here" | Simple code has off-by-ones and null deref too |
| "The tests cover this" | Tests cover happy path; bugs live in edge cases |
| "I found one bug, that's probably it" | Bugs cluster — finish all five categories |
| "This is legacy code, too risky to touch" | Documenting bugs is still valuable; severity guides action |
| "The type system prevents this" | Null still exists in typed languages; logic errors don't care about types |

---

## Red Flags — STOP and Recheck

If you:
- Skipped a category because "this file doesn't do that"
- Stopped after finding the first bug
- Didn't check error handling paths
- Skimmed rather than read conditions aloud
- Checked only the **most recent successful run** of a scheduler/parallel system and declared "it works"
- Found launch log entries without verifying matching completion entries for **every** launched process
- **Declared a scraper/pipeline "working" after it ran without error** — but never checked whether the output file was actually updated (mtime) and has non-zero, non-stale data
- **Accepted `count=0` as normal** without tracing back to WHY the filter produced nothing

→ **Go back. Finish the sweep.**

---

## Related Skills

- **systematic-debugging** — use AFTER finding a bug to trace root cause and fix it
- **test-driven-development** — write failing test for each bug found before fixing
- **verification-before-completion** — verify fix is complete after addressing bugs found
- **requesting-code-review** — structured code review workflow
