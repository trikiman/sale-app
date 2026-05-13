// v1.26 Phase 83 (TEST-01): Vitest + RTL global test setup.
// See .planning/phases/83-vitest-rtl-foundation/83-CONTEXT.md.

import '@testing-library/jest-dom/vitest'
import { beforeEach, afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// Reset per-test globals so one test cannot leak state into another.
// Especially important for `window.Telegram` mutations in isTelegramRuntime tests.
beforeEach(() => {
  if (typeof window !== 'undefined' && 'Telegram' in window) {
    delete window.Telegram
  }
})

afterEach(() => {
  // RTL's automatic cleanup may already run in some jsdom builds, but calling
  // it explicitly guarantees the DOM is reset between tests.
  cleanup()
})
