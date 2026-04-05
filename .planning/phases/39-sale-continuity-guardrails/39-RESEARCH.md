# Phase 39: Sale Continuity Guardrails - Research

**Researched:** 2026-04-05
**Domain:** Health-aware sale-session tracking and confirmed re-entry semantics for a sequential scraper pipeline
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- A product is not truly gone until it has been absent from merged sale data for **1 hour**.
- The same 1-hour disappearance rule applies to **all colors**.
- Failed or stale scraper cycles do **not** count toward disappearance confirmation.
- A product only counts as a true re-entry/new appearance after a **confirmed exit** and later healthy reappearance.
- Add detailed diagnostics for every keep/close/reopen decision, including product ID, sale type, cycle-health reason, missing duration, and chosen action.

### the agent's Discretion
- Exact implementation of "healthy cycle" vs "failed/stale cycle", as long as bad cycles never count toward disappearance.
- Exact storage surface for diagnostics (logs, JSON state, DB audit rows, admin status) as long as the detail is deep enough to debug future false re-appearances quickly.
- Exact ownership split between `sale_history.py`, `db.py`, `backend/notifier.py`, and `backend/main.py`, as long as history and notifier semantics stay aligned.

### Deferred Ideas (OUT OF SCOPE)
- Scheduler cadence rebalance for green vs red/yellow
- User-facing failure UI on the main sale screen
- Main-screen/card performance optimization
- Search/catalog completeness fixes
</user_constraints>

<research_summary>
## Summary

Phase 39 is best treated as a state-contract repair, not a scraper rewrite. The current false "daily re-appearance" bug comes from two distinct state models drifting apart:

1. `database/sale_history.py` closes an active `sale_sessions` row immediately when a product is absent from one merged cycle.
2. `backend/notifier.py` still uses `database/db.py:get_new_products()` against `seen_products`, which is "ever seen in proposals" rather than "confirmed new sale entry".

The safest path is to introduce one explicit machine-readable **cycle health snapshot** before merge history is recorded, then make `sale_history.py` count only **healthy absence time** toward closure. Once session closure/reopen semantics are reliable, notifier/admin "new products" logic should be derived from confirmed sale-session entries instead of the current ever-seen table.

**Primary recommendation:** Persist `data/scrape_cycle_state.json` in `scheduler_service.py` before `scrape_merge.py` runs, have `sale_history.py` keep active sessions open until `last_seen` is at least 60 healthy minutes old, and update notifier/API newness helpers to treat only confirmed session openings after a real exit as "new".
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `sqlite3` | stdlib | Persist `sale_sessions`, `seen_products`, and related helper queries | Already the project's state backbone for sale and notification data |
| `json` | stdlib | Persist per-cycle health snapshot and debug-friendly artifacts | Matches the repo's existing file-based state pattern |
| `pytest` | project-installed | Regression coverage for session/newness semantics | Already the established backend verification tool |
| `logging` / `print` pipeline | stdlib / existing | Emit reason-coded diagnostics into scheduler/backend logs | Fits current operator workflow better than introducing telemetry infrastructure |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `FastAPI TestClient` | existing project stack | Verify `/admin/status` and `/api/new-products` semantics | Use when checking backend route contracts |
| `datetime` / `timezone` | stdlib | Compute healthy absence window from `last_seen` | Use for close/reopen timing logic |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| JSON cycle-state snapshot | DB audit table first | DB table is richer long-term, but JSON is faster to integrate into the existing scheduler -> merge flow |
| Session-derived re-entry semantics | Keep `seen_products` as source of truth | Simpler, but cannot represent "left sale for 1 hour, then returned" correctly |
| Global stale banner only | Per-cycle reason-coded diagnostics | Global banner is not enough to debug why one product was kept, closed, or reopened |

**Installation:**
```bash
pip install -r requirements.txt
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```text
data/
├── scrape_cycle_state.json
└── proposals.json

database/
├── db.py
└── sale_history.py

backend/
├── main.py
├── notifier.py
└── test_sale_continuity.py

scheduler_service.py
scrape_merge.py
```

### Pattern 1: Pre-Merge Cycle Health Snapshot
**What:** Persist one JSON artifact per scheduler cycle before `scrape_merge.py` records sale history.
**When to use:** Whenever downstream logic needs to distinguish "product really absent" from "this cycle was unreliable".
**Example:**
```python
cycle_state = {
    "cycle_started_at": started_at,
    "cycle_finished_at": finished_at,
    "continuity_safe": continuity_safe,
    "overall_status": "healthy" if continuity_safe else "degraded",
    "reasons": reasons,
    "sources": {
        "red": {
            "status": "ok",
            "file_updated": True,
            "counted_for_continuity": True,
            "status_text": "OK (data updated)",
        },
    },
}
```

### Pattern 2: Healthy-Absence Window from `last_seen`
**What:** Leave an active session open while a product is merely missing, and close only when `continuity_safe` is true and `now - last_seen >= 60 minutes`.
**When to use:** When missed scrapes are more common than true restocks and session continuity matters more than exact disappearance minute.
**Example:**
```python
missing_minutes = int((now_dt - last_seen_dt).total_seconds() / 60)
if not continuity_safe:
    decision = "KEEP_ACTIVE_UNSAFE_CYCLE"
elif missing_minutes < 60:
    decision = "KEEP_ACTIVE_GRACE_WINDOW"
else:
    decision = "CLOSE_CONFIRMED_ABSENCE"
```

### Pattern 3: Session-Derived Sale Entry Signals
**What:** Treat "new sale item" as a newly opened active sale session after a confirmed exit, not as "product ID was never seen before".
**When to use:** For notifier/admin alerts that should fire on true restocks or confirmed returns.
**Example:**
```python
# Conceptual helper
SELECT product_id
FROM sale_sessions
WHERE is_active = 1
  AND first_seen >= ?
```

### Anti-Patterns to Avoid
- **Immediate close on first missing cycle:** creates fake re-entries whenever one scraper misses a product.
- **Using `seen_products` alone for sale-entry alerts:** cannot represent real return-to-sale semantics.
- **Treating stale/failed cycles as absence evidence:** converts operational noise into bad product history.
- **Only logging aggregate cycle failure:** operators need per-product reason codes for keep/close/reopen decisions.
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Per-product disappearance truth | Ad hoc booleans scattered across notifier/history | Existing `sale_sessions.last_seen` plus one explicit cycle-health contract | Keeps one source of truth for continuity |
| Operator debugging | Manual log reading with no structured reasons | Reason-coded cycle snapshot + per-decision log lines | Faster to diagnose false daily appearances |
| New sale entry detection | Separate first-seen cache for each alert path | One session-derived helper reused by notifier/API | Keeps admin alerts and notifier semantics aligned |

**Key insight:** The hard part is not "detect missing products"; it is deciding whether a missing observation is trustworthy. That trust decision belongs to a shared cycle-health contract, not duplicated heuristics.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Closing sessions with the wall-clock close time
**What goes wrong:** A 60-minute grace window inflates `duration_minutes` and `last_seen` even though the product was not actually observed during that window.
**Why it happens:** Close logic overwrites `last_seen` with `now` instead of the last observed timestamp.
**How to avoid:** Preserve the session's last actual observation timestamp when confirming the close and compute duration from `first_seen -> last_seen`.
**Warning signs:** Session durations jump by exactly the grace window for every confirmed close.

### Pitfall 2: Letting one unhealthy source block all debugging context
**What goes wrong:** The system knows a cycle was bad, but not whether it was `error`, `timeout`, or `exit 0 but data NOT updated`.
**Why it happens:** Health is reduced to one boolean with no reason list.
**How to avoid:** Persist per-source status text and explicit reason codes in the cycle snapshot.
**Warning signs:** Operators can tell a cycle was degraded but not why.

### Pitfall 3: Fixing history continuity but not notifier/API semantics
**What goes wrong:** Sessions stay continuous, but `/api/new-products` or notifier still uses `seen_products` and drifts from the new session contract.
**Why it happens:** History and alerts are patched independently.
**How to avoid:** Route all "new sale entry" detection through one confirmed-entry helper derived from active sessions.
**Warning signs:** History shows one long session, but notifier/admin still treats the same product as new for the wrong reasons.

### Pitfall 4: Missing regression fixtures for unhealthy cycles
**What goes wrong:** Logic looks correct in code review, but later regressions reintroduce immediate-close or fake re-entry behavior.
**Why it happens:** Tests cover only happy-path active/inactive sessions.
**How to avoid:** Create fixture cases for unhealthy cycle, healthy 59-minute absence, healthy 60+ minute absence, and confirmed reappearance.
**Warning signs:** Test coverage mentions sessions but never controls cycle-health input.
</common_pitfalls>

<code_examples>
## Code Examples

### Current Immediate-Close Hotspot
```python
# Source: database/sale_history.py
for row in active_sessions:
    if row["product_id"] not in current_ids:
        c.execute("""
            UPDATE sale_sessions
            SET is_active = 0, last_seen = ?, duration_minutes = ?
            WHERE id = ?
        """, (now, duration, row["id"]))
```

### Current Ever-Seen Newness Hotspot
```python
# Source: backend/notifier.py
product_ids = [p['id'] for p in products]
new_ids = self.db.get_new_products(product_ids)
return [p for p in products if p['id'] in new_ids]
```

### Existing Scheduler Status Source
```python
# Source: scheduler_service.py
if code == -2:
    status = "TIMEOUT (even after retry)"
elif code != 0:
    status = f"ERROR (exit {code})"
elif not file_updated:
    status = "WARNING (exit 0 but data NOT updated)"
else:
    status = "OK (data updated)"
```
</code_examples>

<validation_architecture>
## Validation Architecture

**Recommended validation loop:**
- Add `backend/test_sale_continuity.py` as the focused regression harness for cycle-state, session-close, and re-entry semantics.
- Keep `backend/test_admin_routes.py` in the loop when `/admin/status` grows a `cycleState` contract.
- Keep `backend/test_notifier.py` or route tests in scope once notifier/API newness semantics switch away from `seen_products`.

**Suggested commands:**
- Quick loop: `pytest backend/test_sale_continuity.py -q`
- Route/state loop: `pytest backend/test_admin_routes.py backend/test_sale_continuity.py -q`
- Full relevant suite: `pytest backend/test_admin_routes.py backend/test_sale_continuity.py backend/test_notifier.py -q`
</validation_architecture>

<sota_updates>
## State of the Art (2024-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Immediate close on first missing scrape | Health-aware grace-window closure | This phase | More accurate continuity for flaky scraper pipelines |
| Ever-seen cache for "new" sale items | Confirmed re-entry based on sale-session opens | This phase | Alerts line up with real restocks instead of first-ever sightings |
| Console-only failure visibility | Structured cycle-state + reason-coded logs | This phase | Faster debugging and safer operator decisions |

**New patterns to consider:**
- Persist one small JSON state artifact that downstream consumers can trust for continuity decisions.
- Use sale-session transitions, not raw visibility deltas, as the contract for restock/new-entry semantics.

**Deprecated/outdated:**
- Assuming one merged cycle is trustworthy enough to close all missing products immediately.
- Assuming "first time in proposals.json" and "newly returned to sale" are the same concept.
</sota_updates>

<open_questions>
## Open Questions

1. **Should the first implementation keep diagnostics in logs/JSON only, or also add a DB audit table?**
   - What we know: logs + JSON fit the current repo pattern and are enough for initial debugging.
   - What's unclear: whether operators will later want long-lived queryable history of keep/close/reopen reasons.
   - Recommendation: start with logs + `scrape_cycle_state.json` in this phase; revisit a DB audit table only if debugging still feels blind.

2. **Should `/api/sync` remain a sale-entry tool at all?**
   - What we know: it currently uses `mark_product_seen()` and exposes `new_products` based on `seen_products`.
   - What's unclear: whether it is still used operationally, or just legacy scaffolding.
   - Recommendation: if touched in this phase, align it with the confirmed-entry helper instead of leaving contradictory semantics behind.
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- `.planning/phases/39-sale-continuity-guardrails/39-CONTEXT.md`
- `database/sale_history.py`
- `database/db.py`
- `backend/notifier.py`
- `scheduler_service.py`
- `scrape_merge.py`
- `backend/main.py`

### Secondary (MEDIUM confidence)
- `.planning/codebase/ARCHITECTURE.md`
- `.planning/codebase/CONVENTIONS.md`
- `.planning/codebase/TESTING.md`
- `.planning/phases/33-group-subgroup-notifications/33-CONTEXT.md`

### Tertiary (LOW confidence - needs validation)
- No external ecosystem research required; remaining uncertainty is about the repo's preferred state surface, not third-party technology.
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: scheduler-driven JSON + SQLite sale state
- Ecosystem: existing backend/notifier/admin contracts
- Patterns: cycle health snapshots, grace-window session closure, session-derived re-entry alerts
- Pitfalls: immediate close, ever-seen drift, poor diagnostics

**Confidence breakdown:**
- Standard stack: HIGH — phase can be implemented entirely with existing project primitives
- Architecture: HIGH — the required integration points are already clear in scheduler, merge, sale history, and notifier
- Pitfalls: HIGH — the current bug follows directly from existing code behavior
- Code examples: HIGH — examples come from the current repo hotspots

**Research date:** 2026-04-05
**Valid until:** 2026-05-05
</metadata>

---

*Phase: 39-sale-continuity-guardrails*
*Research completed: 2026-04-05*
*Ready for planning: yes*
