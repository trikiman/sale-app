// v1.26 Phase 83 Plan 83-02 (TEST-03): pins getCartStep extracted from
// App.jsx. This function drives the +/− quantity stepper in ProductCard
// and CartPanel — if the step is wrong, users can't adjust weighted
// products (needs 0.01 step) or get 0.5-step bugs on piece items.

import { describe, it, expect } from 'vitest'
import { getCartStep } from '../cartStep'

describe('getCartStep', () => {
  describe('cartItem.step takes precedence when valid', () => {
    it('uses numeric step from cart item', () => {
      expect(getCartStep('шт', { step: 2 })).toBe(2)
    })

    it('uses decimal step from cart item for weighted units', () => {
      expect(getCartStep('кг', { step: 0.05 })).toBe(0.05)
    })

    it('falls back to koef when step is absent', () => {
      expect(getCartStep('кг', { koef: 0.05 })).toBe(0.05)
    })

    it('step wins over koef when both set', () => {
      expect(getCartStep('кг', { step: 0.1, koef: 0.05 })).toBe(0.1)
    })
  })

  describe('falls back to unit-based default when cartItem invalid', () => {
    it('returns 0.01 for weighted units with no cart item', () => {
      expect(getCartStep('кг', null)).toBe(0.01)
      expect(getCartStep('г', null)).toBe(0.01)
      expect(getCartStep('л', null)).toBe(0.01)
      expect(getCartStep('мл', null)).toBe(0.01)
    })

    it('returns 1 for piece units with no cart item', () => {
      expect(getCartStep('шт', null)).toBe(1)
    })

    it('returns 0.01 when cart item step is zero (invalid)', () => {
      expect(getCartStep('кг', { step: 0 })).toBe(0.01)
    })

    it('returns 1 when cart item step is negative (invalid)', () => {
      expect(getCartStep('шт', { step: -1 })).toBe(1)
    })

    it('returns default when cart item has no step/koef fields', () => {
      expect(getCartStep('кг', {})).toBe(0.01)
      expect(getCartStep('шт', {})).toBe(1)
    })

    it('returns default when step field is a non-numeric string', () => {
      expect(getCartStep('кг', { step: 'abc' })).toBe(0.01)
    })
  })

  describe('normalizes unit before checking', () => {
    it('accepts English aliases', () => {
      expect(getCartStep('kg', null)).toBe(0.01)
      expect(getCartStep('pcs', null)).toBe(1)
    })
  })

  describe('defensive handling of undefined cartItem', () => {
    it('treats undefined like null', () => {
      expect(getCartStep('шт', undefined)).toBe(1)
    })
  })
})
