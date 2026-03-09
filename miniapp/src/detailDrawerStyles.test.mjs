import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const css = readFileSync(new URL('./index.css', import.meta.url), 'utf8')

test('detail drawer uses a mostly solid dark surface', () => {
  assert.match(
    css,
    /\.detail-drawer\s*\{[\s\S]*background:\s*rgba\(10,\s*14,\s*24,\s*0\.96\);/,
  )
})

test('detail drawer uses a nearly solid light surface in light theme', () => {
  assert.match(
    css,
    /\[data-theme="light"\]\s+\.detail-drawer\s*\{[\s\S]*background:\s*rgba\(255,\s*255,\s*255,\s*0\.98\);/,
  )
})
