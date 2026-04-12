---
status: partial
phase: 49-error-recovery-polish
source: [49-VERIFICATION.md]
started: 2026-04-12T15:06:00Z
updated: 2026-04-12T15:06:00Z
---

## Current Test

[awaiting human testing]

## Tests

### 1. Retryable error shows replay icon and allows retry
expected: Trigger a cart-add timeout → 🔄 replay icon appears on cart button for 4s → tapping re-invokes add-to-cart
result: [pending]

### 2. Sold-out error shows distinct message without retry
expected: Trigger product_gone error → "Этот продукт уже раскупили" toast → ❌ icon for 2s → no retry option
result: [pending]

### 3. Session expiry triggers login prompt
expected: Trigger auth_expired error → login screen appears (no toast error shown) → user can re-authenticate
result: [pending]

## Summary

total: 3
passed: 0
issues: 0
pending: 3
skipped: 0
blocked: 0

## Gaps
