// v1.26 Phase 83 Plan 83-02 (TEST-03): pins the v1.23 UX-CART-02 fix.
//
// Root cause being pinned: `window.Telegram.WebApp.showConfirm` is truthy
// EVERYWHERE the Telegram SDK script loads (miniapp loads the SDK in
// index.html), including desktop Chrome. But the callback only fires
// inside a real Telegram WebView. Without this check, Promise-wrapped
// showConfirm() hangs forever in desktop browser, blocking "Очистить".
//
// The initData string is only non-empty when loaded via Telegram's launch
// URL (t.me/.../startapp=). In desktop Chrome it's either missing or ''.

import { describe, it, expect, beforeEach } from 'vitest'
import { isTelegramRuntime } from '../isTelegramRuntime'

describe('isTelegramRuntime', () => {
  beforeEach(() => {
    // test-setup.js already deletes window.Telegram, but be explicit.
    delete window.Telegram
  })

  it('returns false when window.Telegram is missing (plain browser)', () => {
    expect(isTelegramRuntime()).toBe(false)
  })

  it('returns false when Telegram.WebApp is missing', () => {
    window.Telegram = {}
    expect(isTelegramRuntime()).toBe(false)
  })

  it('returns false when initData is undefined', () => {
    window.Telegram = { WebApp: {} }
    expect(isTelegramRuntime()).toBe(false)
  })

  it('returns false when initData is empty string (desktop browser with SDK loaded)', () => {
    // This is the exact v1.23 UX-CART-02 scenario — SDK script loads and
    // sets WebApp, but initData stays as empty string outside a real
    // Telegram launch. Old code truthy-checked `showConfirm` here and hung.
    window.Telegram = { WebApp: { initData: '', showConfirm: () => {} } }
    expect(isTelegramRuntime()).toBe(false)
  })

  it('returns true when initData is a non-empty string', () => {
    window.Telegram = {
      WebApp: {
        initData: 'query_id=abc&user=%7B%22id%22%3A123%7D',
        showConfirm: () => {},
      },
    }
    expect(isTelegramRuntime()).toBe(true)
  })

  it('returns false when initData is a non-string value (defensive)', () => {
    window.Telegram = { WebApp: { initData: 123 } }
    expect(isTelegramRuntime()).toBe(false)

    window.Telegram = { WebApp: { initData: null } }
    expect(isTelegramRuntime()).toBe(false)
  })
})
