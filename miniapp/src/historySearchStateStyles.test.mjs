import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const css = readFileSync(new URL('./index.css', import.meta.url), 'utf8')

test('history search cards define a shared result-state chip style', () => {
  assert.match(css, /\.hcard-state-chip\s*\{/)
  assert.match(css, /\.hcard-state-detail\s*\{/)
})

test('history search cards define live, history, and catalog chip variants', () => {
  assert.match(css, /\.hcard-state-chip-live\s*\{/)
  assert.match(css, /\.hcard-state-chip-history\s*\{/)
  assert.match(css, /\.hcard-state-chip-catalog\s*\{/)
})
