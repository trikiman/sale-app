---
phase: 44
slug: frontend-bounded-add-ux
status: complete
nyquist_compliant: true
wave_0_complete: true
created: 2026-04-06
validated: 2026-04-06
---

# Phase 44 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest + node:test |
| **Config file** | `pytest.ini`, `miniapp/src/productMeta.test.mjs` |
| **Quick run command** | `pytest backend/test_cart_pending_contract.py -q && node --test miniapp/src/productMeta.test.mjs` |
| **Full suite command** | `pytest backend/test_cart_items_fallback.py backend/test_cart_pending_contract.py -q && cd miniapp && npm run build` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run quick run command
- **After every plan wave:** Run full suite command
- **Before `/gsd-verify-work`:** Full suite must be green + build passes
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 44-01-01 | 01 | 1 | CART-04 | contract | `pytest backend/test_cart_pending_contract.py -q -k allow_pending_returns_202` | ✅ | ✅ green |
| 44-01-02 | 01 | 1 | UI-19 | build | `cd miniapp && npm run build` | ✅ | ✅ green |
| 44-01-03 | 01 | 1 | CART-05 | contract | `pytest backend/test_cart_pending_contract.py -q -k can_return_immediate_success` | ✅ | ✅ green |
| 44-02-01 | 02 | 2 | CART-07 | contract | `pytest backend/test_cart_pending_contract.py -q -k preserve_decimal_quantity` | ✅ | ✅ green |
| 44-02-02 | 02 | 2 | CART-07 | contract | `pytest backend/test_cart_pending_contract.py -q -k set_quantity_route` | ✅ | ✅ green |
| 44-03-01 | 03 | 3 | CART-08 | contract | `pytest backend/test_cart_pending_contract.py -q -k duplicate_pending_adds_reuse` | ✅ | ✅ green |
| 44-03-02 | 03 | 3 | CART-05 | unit | `node --test miniapp/src/productMeta.test.mjs` | ✅ | ✅ green |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

Existing infrastructure covers all phase requirements.

- [x] `backend/test_cart_pending_contract.py` — pending contract, quantity, and dedupe
- [x] `miniapp/src/productMeta.test.mjs` — product metadata display logic
- [x] `miniapp/` build via Vite — compilation correctness for JSX/CSS changes

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Visible spinner caps at 5 seconds and switches to "checking" message | CART-04, UI-19 | Requires live browser with timed visual observation | Open MiniApp, add a product, observe spinner → pending transition timing |
| Cart panel quantity controls sync across card and detail drawer | CART-05 | Visual rendering check across two UI surfaces | Add item, open detail drawer, change quantity, confirm card reflects change |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
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
