---
phase: 43
slug: backend-cart-response-contract
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-06
validated: 2026-04-06
---

# Phase 43 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest backend/test_cart_pending_contract.py -q` |
| **Full suite command** | `pytest backend/test_cart_items_fallback.py backend/test_cart_pending_contract.py -q` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/test_cart_pending_contract.py -q`
- **After every plan wave:** Run `pytest backend/test_cart_items_fallback.py backend/test_cart_pending_contract.py -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 43-01-01 | 01 | 1 | CART-06 | unit | `pytest backend/test_cart_items_fallback.py -q -k bootstrap_uses_saved_metadata` | ✅ | ✅ green |
| 43-01-02 | 01 | 1 | CART-09 | unit | `pytest backend/test_cart_items_fallback.py -q -k timeout_returns_pending_without_inline` | ✅ | ✅ green |
| 43-02-01 | 02 | 2 | CART-09 | contract | `pytest backend/test_cart_pending_contract.py -q -k allow_pending_returns_202` | ✅ | ✅ green |
| 43-02-02 | 02 | 2 | CART-08 | contract | `pytest backend/test_cart_pending_contract.py -q -k duplicate_pending_adds_reuse` | ✅ | ✅ green |
| 43-02-03 | 02 | 2 | CART-06 | contract | `pytest backend/test_cart_pending_contract.py -q -k status_can_transition_pending_to_success` | ✅ | ✅ green |
| 43-03-01 | 03 | 3 | CART-06 | regression | `pytest backend/test_cart_pending_contract.py -q -k status_can_transition_pending_to_failed` | ✅ | ✅ green |
| 43-03-02 | 03 | 3 | CART-09 | regression | `pytest backend/test_cart_items_fallback.py -q -k cart_add_maps_upstream_timeout` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

- [x] `backend/test_cart_items_fallback.py` — metadata bootstrap and bounded timeout path
- [x] `backend/test_cart_pending_contract.py` — pending contract, dedupe, and status reconciliation

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| In-memory attempt tracking durability across process restarts | CART-06 | Requires multi-process deployment scenario | Restart backend while a pending add is in flight, confirm attempt ID is lost gracefully |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 2s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved 2026-04-06

---

## Validation Audit 2026-04-06

| Metric | Count |
|--------|-------|
| Gaps found | 0 |
| Resolved | 0 |
| Escalated | 0 |
| Manual-only | 1 |
