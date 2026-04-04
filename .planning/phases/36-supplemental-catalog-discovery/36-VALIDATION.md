---
phase: 36
slug: supplemental-catalog-discovery
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-04
---

# Phase 36 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest backend/test_catalog_discovery.py -q` |
| **Full suite command** | `pytest backend/test_catalog_discovery.py backend/test_categories.py backend/test_history_search.py -q` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/test_catalog_discovery.py -q`
- **After every plan wave:** Run `pytest backend/test_catalog_discovery.py backend/test_categories.py -q`
- **Before `$gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 36-01-01 | 01 | 1 | DATA-04 | unit | `pytest backend/test_catalog_discovery.py -q -k manifest` | ❌ W0 | ⬜ pending |
| 36-01-02 | 01 | 1 | DATA-04 | unit | `pytest backend/test_catalog_discovery.py -q -k source_state` | ❌ W0 | ⬜ pending |
| 36-02-01 | 02 | 2 | DATA-04 | integration | `pytest backend/test_catalog_discovery.py -q -k admin_route` | ❌ W0 | ⬜ pending |
| 36-02-02 | 02 | 2 | DATA-04 | regression | `pytest backend/test_catalog_discovery.py backend/test_categories.py backend/test_history_search.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/test_catalog_discovery.py` — tests for source manifest extraction, source file persistence, incomplete-run handling, completion validation, and admin orchestration
- [ ] Temporary JSON-file helpers for source files and source-state files

*Existing infrastructure covers command execution and pytest wiring once the new test file exists.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Source page count matches source artifact count | DATA-04 | Depends on live VkusVill response and paging behavior | Run one source scrape, compare the source page’s visible `N товаров` count to the unique IDs in that source file |
| Failed source remains incomplete in admin panel | DATA-04 | Needs live operational run/state transition | Force an incomplete source run, then confirm admin logs/state show the mismatch and that the source is not marked complete |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
