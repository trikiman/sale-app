---
phase: 39
slug: sale-continuity-guardrails
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-05
---

# Phase 39 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest backend/test_sale_continuity.py -q` |
| **Full suite command** | `pytest backend/test_admin_routes.py backend/test_sale_continuity.py backend/test_notifier.py -q` |
| **Estimated runtime** | ~20 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/test_sale_continuity.py -q`
- **After every plan wave:** Run `pytest backend/test_admin_routes.py backend/test_sale_continuity.py backend/test_notifier.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 20 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 39-01-01 | 01 | 1 | OPS-02 | unit | `pytest backend/test_sale_continuity.py -q -k cycle_state` | ❌ W0 | ⬜ pending |
| 39-01-02 | 01 | 1 | OPS-02 | route | `pytest backend/test_admin_routes.py -q -k cycle_state` | ✅ | ⬜ pending |
| 39-02-01 | 02 | 2 | HIST-08 | unit | `pytest backend/test_sale_continuity.py -q -k grace_window` | ❌ W0 | ⬜ pending |
| 39-02-02 | 02 | 2 | HIST-08 | regression | `pytest backend/test_sale_continuity.py -q -k reentry` | ❌ W0 | ⬜ pending |
| 39-03-01 | 03 | 3 | BOT-07 | unit | `pytest backend/test_notifier.py -q -k confirmed_entry` | ✅ | ⬜ pending |
| 39-03-02 | 03 | 3 | BOT-07 | integration | `pytest backend/test_sale_continuity.py backend/test_notifier.py -q -k confirmed_entry` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/test_sale_continuity.py` — fixtures and assertions for cycle-state, grace-window, and confirmed re-entry semantics
- [ ] Temporary helpers for writing a fake `data/scrape_cycle_state.json` and a temporary SQLite sale-history database inside tests

*Existing infrastructure already covers pytest wiring, admin-route testing, and notifier unit tests once the new continuity test file exists.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Red item missed by a bad cycle stays one continuous history session | HIST-08 | Requires running the real scheduler/merge path with live-ish data timing | Trigger one degraded cycle, inspect history for the same product, then run a healthy cycle and confirm no fake new appearance was created |
| Detailed keep/close/reopen reason codes are understandable in operator output | OPS-02 | Human judgment needed to confirm debugging usefulness | Review `logs/scheduler.log` and `/admin/status` after one healthy-miss case and one degraded cycle, confirm the reason text clearly explains the chosen action |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 20s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
