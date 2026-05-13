// v1.26 Phase 83 Plan 83-02 (TEST-03): pins v1.23 Phase 76 helpers shipped
// without unit coverage. Covers all 6 public functions exported from
// miniapp/src/productMeta.js.

import { describe, it, expect } from 'vitest'
import {
  normalizeUnit,
  isWeightedUnit,
  formatQuantity,
  parseQuantityInput,
  getCardMetaBadges,
  mergeResolvedWeights,
  shouldFetchMissingWeight,
} from '../productMeta'

describe('normalizeUnit', () => {
  it('maps English unit aliases to Russian canonical form', () => {
    expect(normalizeUnit('kg')).toBe('кг')
    expect(normalizeUnit('ml')).toBe('мл')
    expect(normalizeUnit('l')).toBe('л')
    expect(normalizeUnit('pcs')).toBe('шт')
  })

  it('maps legacy Russian "гр" to canonical "г"', () => {
    expect(normalizeUnit('гр')).toBe('г')
  })

  it('preserves already-canonical Russian units', () => {
    expect(normalizeUnit('кг')).toBe('кг')
    expect(normalizeUnit('шт')).toBe('шт')
    expect(normalizeUnit('л')).toBe('л')
  })

  it('returns "шт" for empty/null/undefined inputs', () => {
    expect(normalizeUnit('')).toBe('шт')
    expect(normalizeUnit(null)).toBe('шт')
    expect(normalizeUnit(undefined)).toBe('шт')
  })

  it('lowercases and trims input', () => {
    expect(normalizeUnit('  KG  ')).toBe('кг')
    expect(normalizeUnit('ШТ')).toBe('шт')
  })

  it('passes through unknown units unchanged (lowercased)', () => {
    // Defensive: no allowlist, just passthrough for forward compat.
    expect(normalizeUnit('foo')).toBe('foo')
  })
})

describe('isWeightedUnit', () => {
  it('returns true for all 4 weighted units (кг, г, л, мл)', () => {
    expect(isWeightedUnit('кг')).toBe(true)
    expect(isWeightedUnit('г')).toBe(true)
    expect(isWeightedUnit('л')).toBe(true)
    expect(isWeightedUnit('мл')).toBe(true)
  })

  it('returns false for piece units', () => {
    expect(isWeightedUnit('шт')).toBe(false)
  })

  it('normalizes before checking (accepts English aliases)', () => {
    expect(isWeightedUnit('kg')).toBe(true)
    expect(isWeightedUnit('pcs')).toBe(false)
  })
})

describe('formatQuantity', () => {
  it('formats integers without decimals', () => {
    expect(formatQuantity(1)).toBe('1')
    expect(formatQuantity(10)).toBe('10')
  })

  it('formats floats with trailing-zero trim', () => {
    expect(formatQuantity(0.5)).toBe('0.5')
    expect(formatQuantity(0.25)).toBe('0.25')
    expect(formatQuantity(1.5)).toBe('1.5')
  })

  it('returns empty string for zero, negative, NaN, null', () => {
    expect(formatQuantity(0)).toBe('')
    expect(formatQuantity(-1)).toBe('')
    expect(formatQuantity(NaN)).toBe('')
    expect(formatQuantity(null)).toBe('')
    expect(formatQuantity(undefined)).toBe('')
  })
})

describe('parseQuantityInput', () => {
  it('accepts decimal values for weighted units', () => {
    expect(parseQuantityInput('0.5', 'кг')).toBe(0.5)
    expect(parseQuantityInput('1.234', 'кг')).toBe(1.234)
  })

  it('accepts comma as decimal separator (RU locale)', () => {
    expect(parseQuantityInput('0,5', 'кг')).toBe(0.5)
  })

  it('rejects decimals for piece units', () => {
    expect(parseQuantityInput('0.5', 'шт')).toBe(null)
    expect(parseQuantityInput('2', 'шт')).toBe(2)
  })

  it('allows zero (user intends to remove item)', () => {
    expect(parseQuantityInput('0', 'кг')).toBe(0)
    expect(parseQuantityInput('0', 'шт')).toBe(0)
  })

  it('rejects negative, non-numeric, empty', () => {
    expect(parseQuantityInput('-1', 'кг')).toBe(null)
    expect(parseQuantityInput('abc', 'кг')).toBe(null)
    expect(parseQuantityInput('', 'кг')).toBe(null)
    expect(parseQuantityInput(null, 'кг')).toBe(null)
  })

  it('rounds to 3 decimals for weighted precision', () => {
    expect(parseQuantityInput('1.23456', 'кг')).toBe(1.235)
  })
})

describe('getCardMetaBadges', () => {
  it('returns stock badge for positive stock', () => {
    const badges = getCardMetaBadges({ stock: 0.5, unit: 'кг' })
    expect(badges).toEqual([{ kind: 'stock', text: '📦 0.5 кг' }])
  })

  it('returns weight badge only for non-weighted unit with weight string', () => {
    const badges = getCardMetaBadges({ stock: 2, unit: 'шт', weight: '200 г' })
    expect(badges).toContainEqual({ kind: 'stock', text: '📦 2 шт' })
    expect(badges).toContainEqual({ kind: 'weight', text: '200 г' })
  })

  it('hides weight for weighted units (would be redundant)', () => {
    const badges = getCardMetaBadges({ stock: 0.5, unit: 'кг', weight: '500 г' })
    expect(badges.some((b) => b.kind === 'weight')).toBe(false)
  })

  it('returns empty array for zero-stock product with no weight', () => {
    expect(getCardMetaBadges({ stock: 0, unit: 'шт', weight: '' })).toEqual([])
  })
})

describe('mergeResolvedWeights', () => {
  it('leaves products with existing weight untouched', () => {
    const products = [{ id: 1, weight: '200 г' }]
    const merged = mergeResolvedWeights(products, { 1: '999 г' })
    expect(merged[0].weight).toBe('200 г')
  })

  it('backfills empty weight from resolved map', () => {
    const products = [{ id: 1, weight: '' }]
    const merged = mergeResolvedWeights(products, { 1: '250 мл' })
    expect(merged[0].weight).toBe('250 мл')
  })

  it('does not mutate original array', () => {
    const products = [{ id: 1, weight: '' }]
    const merged = mergeResolvedWeights(products, { 1: '250 мл' })
    expect(products[0].weight).toBe('')
    expect(merged[0]).not.toBe(products[0])
  })
})

describe('shouldFetchMissingWeight', () => {
  it('returns true for piece-unit product with zero weight + positive stock', () => {
    expect(shouldFetchMissingWeight({ stock: 2, unit: 'шт', weight: '' })).toBe(true)
  })

  it('returns false if weight already populated', () => {
    expect(shouldFetchMissingWeight({ stock: 2, unit: 'шт', weight: '200 г' })).toBe(false)
  })

  it('returns false for weighted units (weight would be redundant)', () => {
    expect(shouldFetchMissingWeight({ stock: 0.5, unit: 'кг', weight: '' })).toBe(false)
  })

  it('returns false for out-of-stock products', () => {
    expect(shouldFetchMissingWeight({ stock: 0, unit: 'шт', weight: '' })).toBe(false)
  })
})
