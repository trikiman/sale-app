import test from 'node:test'
import assert from 'node:assert/strict'

// jsdom-like minimal globals so consoleBuffer.js can install listeners
globalThis.window = globalThis.window || {}
const listeners = {}
globalThis.window.addEventListener = (event, fn) => {
  if (!listeners[event]) listeners[event] = []
  listeners[event].push(fn)
}

const { installConsoleBuffer, getConsoleBuffer, clearConsoleBuffer } = await import('./consoleBuffer.js')

test('captures console.error calls', () => {
  installConsoleBuffer()
  clearConsoleBuffer()
  console.error('Cart timeout', { product: 33215 })
  const buf = getConsoleBuffer()
  assert.equal(buf.length, 1)
  assert.equal(buf[0].level, 'error')
  assert.match(buf[0].msg, /Cart timeout/)
  assert.match(buf[0].msg, /33215/)
})

test('captures console.warn calls', () => {
  installConsoleBuffer()
  clearConsoleBuffer()
  console.warn('Slow render')
  const buf = getConsoleBuffer()
  assert.equal(buf.length, 1)
  assert.equal(buf[0].level, 'warn')
  assert.equal(buf[0].msg, 'Slow render')
})

test('does not capture console.log (too noisy)', () => {
  installConsoleBuffer()
  clearConsoleBuffer()
  console.log('debug-info-here')
  const buf = getConsoleBuffer()
  assert.equal(buf.length, 0)
})

test('serialises Error instances with stack', () => {
  installConsoleBuffer()
  clearConsoleBuffer()
  const err = new Error('Network down')
  console.error(err)
  const buf = getConsoleBuffer()
  assert.equal(buf.length, 1)
  assert.match(buf[0].msg, /Error: Network down/)
})

test('caps buffer at 100 entries even on spam', () => {
  installConsoleBuffer()
  clearConsoleBuffer()
  for (let i = 0; i < 250; i++) {
    console.error(`spam-${i}`)
  }
  const buf = getConsoleBuffer()
  assert.ok(buf.length <= 100, `buffer should be capped, got ${buf.length}`)
  // Most recent entries preserved
  assert.match(buf[buf.length - 1].msg, /spam-249/)
})

test('window error listener captures uncaught errors', () => {
  installConsoleBuffer()
  clearConsoleBuffer()
  // Simulate a window.error event
  const handler = listeners.error?.[0]
  assert.ok(typeof handler === 'function', 'error handler installed')
  handler({
    message: 'Uncaught TypeError: bad',
    filename: 'app.js',
    lineno: 42,
    colno: 7,
    error: new TypeError('bad'),
  })
  const buf = getConsoleBuffer()
  assert.equal(buf.length, 1)
  assert.equal(buf[0].level, 'uncaught')
  assert.match(buf[0].msg, /Uncaught TypeError/)
  assert.match(buf[0].msg, /app.js:42:7/)
})

test('clearConsoleBuffer empties buffer', () => {
  installConsoleBuffer()
  console.error('one')
  console.error('two')
  clearConsoleBuffer()
  assert.equal(getConsoleBuffer().length, 0)
})
