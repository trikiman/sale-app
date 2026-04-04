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
| 36-01-01 | 01 | 1 | DATA-04 | unit | `pytest backend/test_catalog_discovery.py -q -k query_contract` | ❌ W0 | ⬜ pending |
| 36-01-02 | 01 | 1 | DATA-04 | unit | `pytest backend/test_catalog_discovery.py -q -k stable_id` | ❌ W0 | ⬜ pending |
| 36-02-01 | 02 | 2 | DATA-04 | integration | `pytest backend/test_catalog_discovery.py -q -k orchestration` | ❌ W0 | ⬜ pending |
| 36-02-02 | 02 | 2 | DATA-04 | regression | `pytest backend/test_catalog_discovery.py backend/test_categories.py backend/test_history_search.py -q` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/test_catalog_discovery.py` — new test file for seed loading, stable-ID filtering, dedupe, and artifact stats
- [ ] Shared fixtures or inline helpers for temporary discovery query/artifact files

*Existing infrastructure covers command execution and pytest wiring once the new test file exists.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Known-gap query appears in discovery output | DATA-04 | Depends on live VkusVill response shape and seed quality | Run the discovery script against the checked-in seed file, then inspect `data/catalog_discovery.json` for entries sourced from the `цезарь` query |
| Discovery output remains sidecar-only | DATA-04 | Requires confirming no unintended runtime rewiring | Run discovery, then verify `category_db.json`, `product_catalog`, and `/api/history/products` remain unchanged before Phase 37 work |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
