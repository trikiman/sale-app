// v1.26 Phase 83 Plan 83-02 (TEST-03): extracted from CartPanel.jsx for
// testability. Detects whether the MiniApp is running inside Telegram's
// WebView (where showConfirm actually invokes the callback) vs. a regular
// browser (where the SDK script loads and showConfirm is truthy, but the
// callback never fires — Promise hangs forever).
//
// v1.23 UX-CART-02 root cause: truthy check of `window.Telegram.WebApp.
// showConfirm` matches everywhere — but initData is only a non-empty string
// inside a real Telegram runtime. Pinned by
// miniapp/src/__tests__/isTelegramRuntime.test.js.

export function isTelegramRuntime() {
  return typeof window !== 'undefined'
    && typeof window.Telegram?.WebApp?.initData === 'string'
    && window.Telegram.WebApp.initData.length > 0
}
