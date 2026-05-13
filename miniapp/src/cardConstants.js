// v1.26 Phase 83 Plan 83-03: shared card-rendering constants + helpers
// extracted from App.jsx so ProductCard.jsx can import them without
// circular dependencies with App.

// VkusVill CDN images are public — load directly (no proxy needed).
// referrerPolicy="no-referrer" on <img> tags prevents referer-based blocking.
export function proxyImg(url) {
  return url || ''
}

// Emoji lookup for known categories
export const CATEGORY_EMOJIS = {
  'Овощи': '🥬',
  'Фрукты': '🍎',
  'Мясо': '🥩',
  'Заморозка': '❄️',
  'Напитки': '🥤',
  'Бакалея': '🛒',
  'Молочка': '🥛',
  'Рыба': '🐟',
  'Косметика': '💄',
  'Зоотовары': '🐾',
  'Закуски': '🥨',
  'Салаты': '🥗',
  'Хлеб': '🥖',
  'Готовая еда': '🍱',
  'Сладости': '🍰',
  'Другое': '📦',
  'Новинки': '🆕',
}

export function getCategoryEmoji(category) {
  // Simple partial match for categories not in the exact map
  if (CATEGORY_EMOJIS[category]) return CATEGORY_EMOJIS[category]
  if (category?.includes?.('Сладости')) return CATEGORY_EMOJIS['Сладости']
  if (category?.includes?.('Хлеб')) return CATEGORY_EMOJIS['Хлеб']
  return '📦'
}

// Type badge config — defined once, not re-created per card render.
// Must stay in sync with index.css .card-tint-* rules.
// v1.26 Phase 84: priceColor removed from the config — colors now come
// from CSS scoped to the tint class (.card-tint-{green,red,yellow}
// .card-price) rather than an inline style prop. Kept TYPE_CONFIG as
// a single source of truth for label/tint mapping.
export const TYPE_CONFIG = {
  green: { bg: 'bg-green-500/20', text: 'text-green-400', label: '🟢 Зелёная', border: 'border-green-500/30', tint: 'card-tint-green' },
  red: { bg: 'bg-red-500/20', text: 'text-red-400', label: '🔴 Красная', border: 'border-red-500/30', tint: 'card-tint-red' },
  yellow: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: '🟡 Жёлтая', border: 'border-yellow-500/30', tint: 'card-tint-yellow' },
  _default: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: '📦 Другое', border: 'border-gray-500/30', tint: '' },
}
