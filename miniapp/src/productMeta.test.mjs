import test from 'node:test'
import assert from 'node:assert/strict'

import { getCardMetaBadges, mergeResolvedWeights } from './productMeta.js'

test('shows unit stock and package weight together for piece-based items', () => {
  const badges = getCardMetaBadges({
    stock: 2,
    unit: 'шт',
    weight: '300 г',
  })

  assert.deepEqual(badges, [
    { kind: 'stock', text: '📦 2 шт' },
    { kind: 'weight', text: '300 г' },
  ])
})

test('shows weighted stock directly for weight-sold items', () => {
  const badges = getCardMetaBadges({
    stock: 2.5,
    unit: 'кг',
    weight: '',
  })

  assert.deepEqual(badges, [
    { kind: 'stock', text: '📦 2.5 кг' },
  ])
})

test('keeps package weight visible even when stock is zero', () => {
  const badges = getCardMetaBadges({
    stock: 0,
    unit: 'шт',
    weight: '50 г',
  })

  assert.deepEqual(badges, [
    { kind: 'weight', text: '50 г' },
  ])
})

test('fills missing weight from resolved lookup without overwriting existing weight', () => {
  const merged = mergeResolvedWeights(
    [
      { id: 'bread', weight: '' },
      { id: 'berries', weight: '150 г' },
    ],
    {
      bread: '300 г',
      berries: '500 г',
    },
  )

  assert.equal(merged[0].weight, '300 г')
  assert.equal(merged[1].weight, '150 г')
})
