/**
 * API utilities for VkusVill MiniApp
 * Centralized auth header management (BUG-038/039 IDOR fix)
 */

/**
 * Get authentication headers for API requests.
 * 
 * Path 1 (Telegram MiniApp): Returns `Authorization: tma <initData>`
 *   - Cryptographically proves the request came from the actual Telegram user
 *   - Backend validates HMAC-SHA256 signature using bot token
 * 
 * Path 2 (Guest/Browser): Returns `X-Telegram-User-Id: <userId>`
 *   - Fallback for direct browser access and guest users
 *   - Backend validates header matches URL/body user_id
 * 
 * @param {string|number} userId - The user ID to authenticate as
 * @returns {Object} Headers object to spread into fetch options
 */
export function getAuthHeaders(userId) {
  // Telegram MiniApp SDK provides initData with HMAC signature
  const initData = window.Telegram?.WebApp?.initData
  if (initData) {
    return {
      'Authorization': `tma ${initData}`,
      'X-Telegram-User-Id': String(userId),  // Keep for backward compat during rollout
    }
  }

  // Fallback: guest or direct browser access
  return {
    'X-Telegram-User-Id': String(userId),
  }
}
