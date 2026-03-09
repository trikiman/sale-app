import test from 'node:test'
import assert from 'node:assert/strict'

import { buildCategoryRunView } from './categoryRunStatus.js'

test('running status without output shows a fallback progress summary', () => {
  const view = buildCategoryRunView({
    running: true,
    last_run: '2026-03-07 08:32:21',
    last_output: '',
    exit_code: null,
  })

  assert.equal(view.summary, 'Идет определение категорий. Обычно это занимает 1-3 минуты.')
  assert.deepEqual(view.lines, [])
  assert.equal(view.isError, false)
})

test('running status keeps only the most recent non-empty progress lines', () => {
  const view = buildCategoryRunView({
    running: true,
    last_output: 'line 1\n\nline 2\nline 3\nline 4\nline 5',
    exit_code: null,
  })

  assert.deepEqual(view.lines, ['line 2', 'line 3', 'line 4', 'line 5'])
  assert.equal(view.summary, 'Идет определение категорий...')
})

test('failed status is marked as an error', () => {
  const view = buildCategoryRunView({
    running: false,
    last_output: 'boom',
    exit_code: 1,
  })

  assert.equal(view.summary, 'Не удалось определить категории.')
  assert.equal(view.isError, true)
  assert.deepEqual(view.lines, ['boom'])
})
