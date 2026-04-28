// v1.16 BUG-04: Console log buffer for bug reports
// Captures last 30 seconds of console.error, console.warn, and uncaught errors.
// Cap ~100 records. Installed once at app startup via installConsoleBuffer().

const BUFFER_WINDOW_MS = 30 * 1000 // 30 seconds
const BUFFER_MAX_ENTRIES = 100

let buffer = []
let installed = false

function trim() {
  // Remove records older than the window
  const cutoff = Date.now() - BUFFER_WINDOW_MS
  while (buffer.length > 0 && buffer[0].ts < cutoff) {
    buffer.shift()
  }
  // Cap total entries (in case of extreme spam)
  if (buffer.length > BUFFER_MAX_ENTRIES) {
    buffer = buffer.slice(-BUFFER_MAX_ENTRIES)
  }
}

function safeStringify(arg) {
  if (arg == null) return String(arg)
  if (typeof arg === 'string') return arg
  if (arg instanceof Error) {
    return `${arg.name}: ${arg.message}${arg.stack ? '\n' + arg.stack : ''}`
  }
  try {
    return JSON.stringify(arg)
  } catch {
    try {
      return String(arg)
    } catch {
      return '[unserializable]'
    }
  }
}

function captureEntry(level, args) {
  trim()
  const msg = Array.from(args).map(safeStringify).join(' ').slice(0, 1000)
  buffer.push({ level, msg, ts: Date.now() })
  // Cap to MAX (defensive after each push)
  if (buffer.length > BUFFER_MAX_ENTRIES) {
    buffer.shift()
  }
}

export function installConsoleBuffer() {
  if (installed || typeof window === 'undefined') return
  installed = true

  const origError = console.error
  const origWarn = console.warn
  const origLog = console.log

  console.error = function (...args) {
    captureEntry('error', args)
    return origError.apply(console, args)
  }
  console.warn = function (...args) {
    captureEntry('warn', args)
    return origWarn.apply(console, args)
  }
  // Don't capture every console.log (too noisy), only errors/warnings.
  // But still expose original passthrough so existing code keeps working.

  // Capture window-level uncaught errors
  window.addEventListener('error', (event) => {
    captureEntry('uncaught', [
      event.message || 'Uncaught error',
      `at ${event.filename || '?'}:${event.lineno || '?'}:${event.colno || '?'}`,
      event.error ? safeStringify(event.error) : '',
    ])
  })

  // Capture unhandled promise rejections
  window.addEventListener('unhandledrejection', (event) => {
    captureEntry('rejection', [event.reason])
  })
}

export function getConsoleBuffer() {
  trim()
  // Return a copy so callers can't mutate internal state
  return buffer.slice()
}

export function clearConsoleBuffer() {
  buffer = []
}
