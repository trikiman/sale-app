---
phase: 45
slug: cart-diagnostics-verification
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-06
validated: 2026-04-06
---

# Phase 45 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + python script |
| **Config file** | `pytest.ini` |
| **Quick run command** | `pytest backend/test_admin_routes.py -q -k cart_diagnostics` |
| **Full suite command** | `pytest backend/test_cart_items_fallback.py backend/test_cart_pending_contract.py backend/test_admin_routes.py -q` |
| **Estimated runtime** | ~2 seconds |

---

## Sampling Rate

- **After every task commit:** Run `pytest backend/test_admin_routes.py -q -k cart_diagnostics`
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green (17 tests)
- **Max feedback latency:** 2 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 45-01-01 | 01 | 1 | OPS-04 | route | `pytest backend/test_admin_routes.py -q -k cart_diagnostics` | ✅ | ✅ green |
| 45-01-02 | 01 | 1 | OPS-04 | compile | `python -m py_compile backend/main.py` | ✅ | ✅ green |
| 45-02-01 | 02 | 2 | QA-04 | regression | `pytest backend/test_cart_pending_contract.py -q -k immediate_success` | ✅ | ✅ green |
| 45-02-02 | 02 | 2 | QA-04 | regression | `pytest backend/test_cart_pending_contract.py -q -k transition_pending_to_success` | ✅ | ✅ green |
| 45-02-03 | 02 | 2 | QA-04 | regression | `pytest backend/test_cart_pending_contract.py -q -k transition_pending_to_failed` | ✅ | ✅ green |
| 45-02-04 | 02 | 2 | QA-04 | regression | `pytest backend/test_cart_pending_contract.py -q -k preserve_decimal_quantity` | ✅ | ✅ green |
| 45-02-05 | 02 | 2 | QA-04 | regression | `pytest backend/test_cart_pending_contract.py -q -k set_quantity_route` | ✅ | ✅ green |
| 45-03-01 | 03 | 3 | QA-04 | script | `python -m py_compile miniapp/test_ui.py` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

- [x] `backend/test_admin_routes.py` — admin status includes cart diagnostics payload
- [x] `backend/test_cart_pending_contract.py` — full regression matrix (immediate, pending, failure, quantity, set-quantity)
- [x] `miniapp/test_ui.py` — browser sanity helper (lightweight, skips gracefully when dev server unavailable)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live authenticated cart add lifecycle shows correct diagnostics in admin panel | OPS-04 | Requires live VkusVill authentication + real cart API interaction | Log in, add a product, visit /admin, confirm cart diagnostics shows the attempt with timing and status |
| Browser sanity helper validates current cart UI surfaces | QA-04 | Requires running local dev server | Run `npm run dev` then `python miniapp/test_ui.py`, confirm it checks card and detail drawer cart controls |

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
| Manual-only | 2 |
