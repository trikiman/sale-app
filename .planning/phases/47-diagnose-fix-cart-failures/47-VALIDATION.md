---
phase: 47
slug: diagnose-fix-cart-failures
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-08
---

# Phase 47 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x |
| **Config file** | tests/conftest.py |
| **Quick run command** | `python -m pytest tests/test_cart.py -x -q` |
| **Full suite command** | `python -m pytest tests/ -x -q` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python -m pytest tests/test_cart.py -x -q`
- **After every plan wave:** Run `python -m pytest tests/ -x -q`
- **Before `/gsd-verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 47-01-01 | 01 | 1 | CART-15 | — | Cart add returns typed error_type | unit | `python -m pytest tests/test_cart.py -k error_type -x` | ❌ W0 | ⬜ pending |
| 47-01-02 | 01 | 1 | CART-16 | — | Diagnostic logs contain root cause | unit | `python -m pytest tests/test_cart.py -k diagnostic -x` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_cart.py` — stubs for CART-15, CART-16 error classification
- [ ] `tests/conftest.py` — shared fixtures for cart mocking

---

## Validation Architecture

Derived from 47-RESEARCH.md:
- VkusVillCart.add() error classification coverage
- cart_add_endpoint error_type passthrough
- Diagnostic logging verification
