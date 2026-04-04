import test from 'node:test'
import assert from 'node:assert/strict'

import { getHistorySearchState } from './historySearchState.js'

test('classifies active sale products as live search matches', () => {
  assert.deepEqual(
    getHistorySearchState({
      is_currently_on_sale: true,
      total_sale_count: 4,
    }),
    {
      kind: 'live',
      label: 'Сейчас на скидке',
      detail: 'Акция активна прямо сейчас',
    },
  )
})

test('classifies historical products without active sale as history-only matches', () => {
  assert.deepEqual(
    getHistorySearchState({
      is_currently_on_sale: false,
      total_sale_count: 2,
    }),
    {
      kind: 'history',
      label: 'Была скидка',
      detail: 'Сейчас без активной акции, но история уже есть',
    },
  )
})

test('classifies zero-history products as catalog-only matches', () => {
  assert.deepEqual(
    getHistorySearchState({
      is_currently_on_sale: false,
      total_sale_count: 0,
    }),
    {
      kind: 'catalog',
      label: 'Есть в каталоге',
      detail: 'Скидок пока не было',
    },
  )
})
