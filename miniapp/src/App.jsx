import { useState, useEffect, useMemo, useRef, useCallback, memo, lazy, Suspense } from 'react'
import CartPanel from './CartPanel'
import ProductDetail from './ProductDetail'
const HistoryPage = lazy(() => import('./HistoryPage'))
const HistoryDetail = lazy(() => import('./HistoryDetail'))
import { buildCategoryRunView } from './categoryRunStatus'
import { getCardMetaBadges, mergeResolvedWeights, shouldFetchMissingWeight } from './productMeta'
import { getAuthHeaders } from './api'
import './index.css'

// VkusVill CDN images are public — load directly (no proxy needed).
// referrerPolicy="no-referrer" on <img> tags prevents referer-based blocking.
function proxyImg(url) {
  return url || ''
}

// Emoji lookup for known categories
const CATEGORY_EMOJIS = {
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

import Login from './Login'

// Normalize \xa0 (non-breaking space) to regular space in category strings
function normalizeCategory(cat) {
  return cat ? cat.replace(/\u00a0/g, ' ') : cat
}

function getCategoryEmoji(category) {
  // Simple partial match for categories not in the exact map
  if (CATEGORY_EMOJIS[category]) return CATEGORY_EMOJIS[category]
  if (category.includes('Сладости')) return CATEGORY_EMOJIS['Сладости']
  if (category.includes('Хлеб')) return CATEGORY_EMOJIS['Хлеб']
  return '📦'
}

// Type badge config — defined once outside component (not re-created per card render)
const TYPE_CONFIG = {
  green: { bg: 'bg-green-500/20', text: 'text-green-400', label: '🟢 Зелёная', border: 'border-green-500/30', priceColor: '#4ade80', tint: 'card-tint-green' },
  red: { bg: 'bg-red-500/20', text: 'text-red-400', label: '🔴 Красная', border: 'border-red-500/30', priceColor: '#f87171', tint: 'card-tint-red' },
  yellow: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: '🟡 Жёлтая', border: 'border-yellow-500/30', priceColor: '#facc15', tint: 'card-tint-yellow' },
  _default: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: '📦 Другое', border: 'border-gray-500/30', priceColor: '#9ca3af', tint: '' }
}
const CARDS_PER_PAGE = 24
const PRODUCTS_CACHE_KEY = 'vv_products_cache_v1'
const WEIGHT_CACHE_KEY = 'vv_weight_cache_v1'

function readCachedJson(key) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function writeCachedJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    // Cache is best-effort only.
  }
}

function normalizeProductsPayload(items) {
  return Array.isArray(items)
    ? items.map((p) => ({ ...p, category: normalizeCategory(p.category) }))
    : []
}

const ProductCard = memo(function ProductCard({ product, index, isFavorite, onToggleFavorite, favoritesLoading, onAddToCart, viewMode, cartState, onOpenDetail }) {
  const [imageLoaded, setImageLoaded] = useState(false)
  const [imageError, setImageError] = useState(false)
  const metaBadges = getCardMetaBadges(product)

  // Calculate real discount percentage
  const oldPriceVal = parseFloat(product.oldPrice)
  const currentPriceVal = parseFloat(product.currentPrice)
  const hasDiscount = oldPriceVal > currentPriceVal && oldPriceVal > 0
  const discount = hasDiscount
    ? Math.round(((oldPriceVal - currentPriceVal) / oldPriceVal) * 100)
    : 0

  const config = TYPE_CONFIG[product.type] || TYPE_CONFIG._default

  return (
    <div
      className={`card-vertical ${config.tint}`}
    >
      {/* Hero Image — clickable to open detail */}
      <div className="card-image-wrap" onClick={() => onOpenDetail(product)} style={{ cursor: 'pointer' }}>
        {!imageLoaded && !imageError && product.image && <div className="absolute inset-0 skeleton" />}

        {product.image && !imageError ? (
          <img
            src={proxyImg(product.image)}
            alt={product.name}
            referrerPolicy="no-referrer"
            loading="lazy"
            decoding="async"
            className={`card-hero-img ${imageLoaded ? 'loaded' : ''}`}
            onLoad={() => setImageLoaded(true)}
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="card-hero-fallback">
            <span className="text-4xl">{getCategoryEmoji(product.category)}</span>
          </div>
        )}

        {/* Discount badge on image */}
        {hasDiscount && (
          <span className="card-discount">-{discount}%</span>
        )}

        {/* Favorite button on image */}
        <button
          className={`card-fav-btn tap-scale-xs ${isFavorite ? 'active' : ''} ${favoritesLoading ? 'loading' : ''}`}
          onClick={(e) => {
            e.stopPropagation()
            if (!favoritesLoading) onToggleFavorite(product)
          }}
          disabled={favoritesLoading}
        >
          {favoritesLoading ? (
            <div className="w-5 h-5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
          ) : (
            isFavorite ? '❤️' : '🤍'
          )}
        </button>

        {/* Type badge on image */}
        <span className={`card-type-badge ${config.bg} ${config.text}`}>
          {config.label}
        </span>
      </div>

      {/* Card Body */}
      <div className="card-body">
        <h3 className="card-title">{product.name}</h3>

        <div className="card-price-row">
          <div className="card-prices">
            <span className="card-price" style={{ color: config.priceColor }}>{product.currentPrice}₽</span>
            {hasDiscount && (
              <span className="card-old-price">{product.oldPrice}₽</span>
            )}
          </div>
          <button
            className={`cart-btn tap-scale-sm ${cartState === 'success' ? 'cart-btn-success' : ''} ${cartState === 'error' ? 'cart-btn-error' : ''} ${cartState === 'pending' ? 'cart-btn-pending' : ''}`}
            onClick={(e) => {
              e.stopPropagation()
              if (cartState !== 'loading' && cartState !== 'pending') onAddToCart(product)
            }}
            aria-label="Добавить в корзину"
            disabled={cartState === 'loading' || cartState === 'pending'}
          >
            {cartState === 'loading' ? (
              <span className="cart-btn-spinner" />
            ) : cartState === 'pending' ? (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.4">
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6l4 2" />
                <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9 9 0 100-18 9 9 0 000 18z" />
              </svg>
            ) : cartState === 'success' ? (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
              </svg>
            ) : cartState === 'error' ? (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                <path strokeLinecap="round" strokeLinejoin="round" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z" />
              </svg>
            )}
          </button>
        </div>

        <div className="card-meta-row">
          {metaBadges.map((badge) => (
            <span
              key={`${badge.kind}-${badge.text}`}
              className={badge.kind === 'stock' ? 'card-stock' : badge.kind === 'stock-zero' ? 'card-stock-zero' : 'card-weight'}
            >
              {badge.text}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}, (prev, next) => {
  // Custom comparator: skip re-render if nothing card-relevant changed
  return prev.product === next.product
    && prev.isFavorite === next.isFavorite
    && prev.cartState === next.cartState
    && prev.favoritesLoading === next.favoritesLoading
    && prev.viewMode === next.viewMode
})

function ScrollableChips({ selected, onSelect, items, className = '', favoritedIds, onToggleFavorite }) {
  const scrollRef = useRef(null)
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(true)

  // Scroll selected chip to center whenever selection changes
  useEffect(() => {
    const container = scrollRef.current
    if (!container) return
    const active = container.querySelector('.category-chip.active')
    if (!active) return
    container.scrollTo({
      left: active.offsetLeft - container.clientWidth / 2 + active.offsetWidth / 2,
      behavior: 'smooth',
    })
  }, [selected])

  const checkScroll = (e) => {
    const el = e.target
    setCanScrollLeft(el.scrollLeft > 0)
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 1)
  }

  return (
    <div className={`relative group ${className}`}>
      {canScrollLeft && (
        <div className="absolute left-0 top-0 bottom-2 w-8 z-10 pointer-events-none rounded-l-xl scroll-indicator-left bg-gradient-to-r from-black/50 to-transparent" />
      )}
      {canScrollRight && (
        <div className="absolute right-0 top-0 bottom-2 w-8 z-10 pointer-events-none rounded-r-xl scroll-indicator-right bg-gradient-to-l from-black/50 to-transparent" />
      )}

      <div
        ref={scrollRef}
        className="flex gap-2 overflow-x-auto pb-2 px-4 -mx-4 scrollbar-hide relative"
        onScroll={checkScroll}
      >
        {items.map((item) => {
          const isFav = favoritedIds && item.favKey && favoritedIds.has(item.favKey)
          return (
            <button
              key={item.id ?? item.label}
              onClick={() => onSelect(item.id)}
              className={`category-chip tap-scale ${selected === item.id ? 'active' : ''} ${isFav ? 'fav' : ''}`}
            >
              {item.label}
              {onToggleFavorite && item.favKey && (
                <span
                  className="chip-fav-icon"
                  onClick={(e) => {
                    e.stopPropagation()
                    onToggleFavorite(item.favKey, item.label)
                  }}
                >
                  {isFav ? '❤️' : '🤍'}
                </span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function CategoryFilter({ selected, onSelect, categories, favoritedIds, onToggleFavorite }) {
  return <ScrollableChips selected={selected} onSelect={onSelect} items={categories} favoritedIds={favoritedIds} onToggleFavorite={onToggleFavorite} />
}

function App() {
  const initialProductsCacheRef = useRef(undefined)
  if (initialProductsCacheRef.current === undefined) {
    initialProductsCacheRef.current = readCachedJson(PRODUCTS_CACHE_KEY)
  }
  const initialProductsCache = initialProductsCacheRef.current
  const isTelegramMiniApp = Boolean(window.Telegram?.WebApp?.initData)
  const [products, setProducts] = useState(() => normalizeProductsPayload(initialProductsCache?.products))
  const [resolvedWeights, setResolvedWeights] = useState(() => readCachedJson(WEIGHT_CACHE_KEY) || {})
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [selectedSubgroup, setSelectedSubgroup] = useState(null)
  const [loading, setLoading] = useState(() => !initialProductsCache?.products?.length)
  const [favoritesLoading, setFavoritesLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(() => {
    return localStorage.getItem('vv_authenticated') === '1'
  })
  const [userPhone, setUserPhone] = useState(() => {
    return localStorage.getItem('vv_user_phone') || null
  })
  const [showLogin, setShowLogin] = useState(false)
  const [showLoginPrompt, setShowLoginPrompt] = useState(false)
  const [error, setError] = useState(null)
  const [toastMessage, setToastMessage] = useState(null)
  const [updatedAt, setUpdatedAt] = useState(() => initialProductsCache?.updatedAt || null)
  const updatedAtRef = useRef(initialProductsCache?.updatedAt || null)
  const freshnessSignatureRef = useRef(JSON.stringify(initialProductsCache?.sourceFreshness || {}))
  const [favorites, setFavorites] = useState(new Set())
  const [userId] = useState(() => {
    // Check if we previously linked a Telegram account
    const linkedId = localStorage.getItem('linked_telegram_id')
    if (linkedId) return Number(linkedId)

    // Get user ID from Telegram if available
    const telegramId = window.Telegram?.WebApp?.initDataUnsafe?.user?.id
    if (telegramId) return telegramId

    // For non-Telegram users, use a persistent guest UUID from localStorage
    let guestId = localStorage.getItem('guest_user_id')
    if (!guestId) {
      guestId = 'guest_' + Math.random().toString(36).substring(2, 15) + Date.now().toString(36)
      localStorage.setItem('guest_user_id', guestId)
    }
    return guestId
  })
  const [typeFilters, setTypeFilters] = useState({
    green: true,
    red: true,
    yellow: true
  })
  const [greenLiveCount, setGreenLiveCount] = useState(() => initialProductsCache?.greenLiveCount ?? null)
  const [dataStale, setDataStale] = useState(() => !!initialProductsCache?.dataStale)
  const [greenMissing, setGreenMissing] = useState(() => !!initialProductsCache?.greenMissing)
  const [sourceFreshness, setSourceFreshness] = useState(() => initialProductsCache?.sourceFreshness || null)
  const [scraperRunning, setScraperRunning] = useState(false)
  const [scraperDone, setScraperDone] = useState(false)
  const [showTokenInput, setShowTokenInput] = useState(false)
  const [tokenInputValue, setTokenInputValue] = useState('')
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('vv_view_mode') || 'grid')
  const [theme, setTheme] = useState(() => localStorage.getItem('vv_theme') || 'dark')
  const [categorizingRunning, setCategorizingRunning] = useState(false)
  const [categorizingDone, setCategorizingDone] = useState(false)
  const [categorizingStatus, setCategorizingStatus] = useState(null)
  const [currentPage, setCurrentPage] = useState('main') // 'main' | 'history' | 'history-detail'
  const [historyDetailId, setHistoryDetailId] = useState(null)
  const [visibleCount, setVisibleCount] = useState(CARDS_PER_PAGE)
  const loadMoreRef = useRef(null)

  // Telegram account linking
  const isGuest = typeof userId === 'string' && userId.startsWith('guest_')
  const [linkUrl, setLinkUrl] = useState(null)
  const [linkDismissed, setLinkDismissed] = useState(() => localStorage.getItem('link_dismissed') === '1')

  // Apply theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('vv_theme', theme)
  }, [theme])

  // Persist auth state
  useEffect(() => {
    localStorage.setItem('vv_authenticated', isAuthenticated ? '1' : '0')
    if (userPhone) localStorage.setItem('vv_user_phone', userPhone)
    else localStorage.removeItem('vv_user_phone')
  }, [isAuthenticated, userPhone])

  // Persist view mode
  useEffect(() => {
    localStorage.setItem('vv_view_mode', viewMode)
  }, [viewMode])

  useEffect(() => {
    writeCachedJson(WEIGHT_CACHE_KEY, resolvedWeights)
  }, [resolvedWeights])

  // Check server-side link status on load (handles new device/browser)
  // If already linked, store telegram_id locally and reload
  useEffect(() => {
    if (!isGuest) return
    fetch(`/api/link/status/${userId}`)
      .then(r => r.json())
      .then(async (data) => {
        if (data.linked && data.telegram_id) {
          // Already linked on server — restore locally
          try {
            await fetch('/api/auth/transfer-mapping', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({
                from_user_id: userId,
                to_user_id: String(data.telegram_id)
              })
            })
          } catch (e) { /* best-effort */ }
          localStorage.setItem('linked_telegram_id', String(data.telegram_id))
          localStorage.removeItem('guest_user_id')
          window.location.reload()
        }
      })
      .catch(() => { })
  }, [isGuest, userId])

  // Generate Telegram link for guest users (only if not already linked)
  useEffect(() => {
    if (!isGuest || linkDismissed) return
    fetch('/api/link/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ guest_id: userId })
    })
      .then(r => r.json())
      .then(data => {
        if (data.link) setLinkUrl(data.link)
      })
      .catch(() => { })

    // Poll for link status every 5 seconds (for when user clicks link and comes back)
    const interval = setInterval(() => {
      fetch(`/api/link/status/${userId}`)
        .then(r => r.json())
        .then(async (data) => {
          if (data.linked && data.telegram_id) {
            try {
              await fetch('/api/auth/transfer-mapping', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  from_user_id: userId,
                  to_user_id: String(data.telegram_id)
                })
              })
            } catch (e) { /* best-effort */ }
            localStorage.setItem('linked_telegram_id', String(data.telegram_id))
            localStorage.removeItem('guest_user_id')
            setLinkUrl(null)
            clearInterval(interval)
            window.location.reload()
          }
        })
        .catch(() => { })
    }, 5000)
    return () => clearInterval(interval)
  }, [isGuest, linkDismissed, userId])

  useEffect(() => {
    // Load product favorites
    setFavoritesLoading(true)
    fetch(`/api/favorites/${userId}`, {
      headers: getAuthHeaders(userId)
    })
      .then(res => res.json())
      .then(data => {
        if (data.favorites) {
          setFavorites(new Set(data.favorites.map(f => f.product_id)))
        }
      })
      .catch(err => {
        console.warn('Failed to load favorites from API, starting empty:', err)
      })
      .finally(() => setFavoritesLoading(false))

    // Load category (group/subgroup) favorites (v1.7)
    fetch(`/api/favorites/${userId}/categories`, {
      headers: getAuthHeaders(userId)
    })
      .then(res => res.json())
      .then(data => {
        if (data.categories) {
          setFavoriteCategories(new Set(data.categories.map(c => c.category_key)))
        }
      })
      .catch(() => { })

    // Check auth status, then load initial cart count
    fetch(`/api/auth/status/${userId}`)
      .then(res => res.json())
      .then(data => {
        setIsAuthenticated(data.authenticated)
        if (data.phone) setUserPhone(data.phone)
        if (data.authenticated) {
          fetch(`/api/cart/items/${userId}`, {
            headers: getAuthHeaders(userId)
          })
            .then(r => r.json())
            .then(cart => {
              if (cart.items_count != null) {
                setCartCount(cart.items_count)
                setCartItemIds(new Set((cart.items || []).map(item => String(item.id ?? item.product_id ?? ''))))
              }
            })
            .catch(() => { })
        }
      })
      .catch(err => console.warn('Failed to check auth status:', err))
  }, [userId])

  const [favBusy, setFavBusy] = useState(new Set())
  const handleToggleFavorite = useCallback(async (product) => {
    // Debounce: skip if already in-flight for this product
    if (favBusy.has(product.id)) return
    setFavBusy(s => { const n = new Set(s); n.add(product.id); return n })
    // Store original state for potential rollback
    const wasInFavorites = favorites.has(product.id)

    // Optimistic update using functional state to avoid race conditions
    setFavorites(prev => {
      const next = new Set(prev)
      if (next.has(product.id)) {
        next.delete(product.id)
      } else {
        next.add(product.id)
      }
      return next
    })

    try {
      if (wasInFavorites) {
        // Remove
        const res = await fetch(`/api/favorites/${userId}/${product.id}`, {
          method: 'DELETE',
          headers: getAuthHeaders(userId)
        })
        if (!res.ok && res.status !== 404) throw new Error('API failed')
      } else {
        // Add
        const res = await fetch(`/api/favorites/${userId}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...getAuthHeaders(userId)
          },
          body: JSON.stringify({
            product_id: product.id,
            product_name: product.name
          })
        })
        if (!res.ok && res.status !== 404) throw new Error('API failed')
      }
    } catch (err) {
      console.warn('API request failed, reverting state:', err)
      // Rollback on error
      setFavorites(prev => {
        const next = new Set(prev)
        if (wasInFavorites) {
          next.add(product.id)  // Was in favorites, add back
        } else {
          next.delete(product.id)  // Wasn't in favorites, remove
        }
        return next
      })
    } finally {
      setFavBusy(s => { const n = new Set(s); n.delete(product.id); return n })
    }
  })

  // Reusable product loader (used for initial load + auto-refresh)
  const loadProducts = (isAutoRefresh = false) => {
    const shouldBlock = !isAutoRefresh && products.length === 0
    if (shouldBlock) setLoading(true)
    fetch('/api/products')
      .then(res => {
        if (!res.ok) throw new Error('Failed to load data')
        return res.json()
      })
      .then(data => {
        if (data.products && Array.isArray(data.products)) {
          const normalizedProducts = normalizeProductsPayload(data.products)
          const freshnessSignature = JSON.stringify(data.sourceFreshness || {})
          if (
            isAutoRefresh &&
            data.updatedAt === updatedAtRef.current &&
            freshnessSignature === freshnessSignatureRef.current &&
            !!data.dataStale === dataStale &&
            !!data.greenMissing === greenMissing
          ) return

          setProducts(normalizedProducts)
          setUpdatedAt(data.updatedAt)
          updatedAtRef.current = data.updatedAt
          freshnessSignatureRef.current = freshnessSignature
          if (data.greenLiveCount !== undefined) setGreenLiveCount(data.greenLiveCount)
          setDataStale(!!data.dataStale)
          setGreenMissing(!!data.greenMissing)
          setSourceFreshness(data.sourceFreshness || null)
          setError(null)
          writeCachedJson(PRODUCTS_CACHE_KEY, {
            products: normalizedProducts,
            updatedAt: data.updatedAt,
            greenLiveCount: data.greenLiveCount,
            dataStale: !!data.dataStale,
            greenMissing: !!data.greenMissing,
            sourceFreshness: data.sourceFreshness || null,
          })
        } else if (Array.isArray(data) && data.length > 0) {
          setProducts(normalizeProductsPayload(data))
          setError(null)
        } else if (!isAutoRefresh && products.length === 0) {
          setError('Товары не найдены')
        }
      })
      .catch(err => {
        if (isAutoRefresh) return // Silently ignore auto-refresh errors
        console.error('API Error:', err)
        if (products.length === 0) {
          setError('Не удалось загрузить данные. Проверьте подключение.')
        } else {
          setToastMessage({ text: 'Не удалось обновить данные', type: 'error' })
          setTimeout(() => setToastMessage(null), 3000)
        }
      })
      .finally(() => {
        if (shouldBlock) setLoading(false)
      })
  }

  useEffect(() => {
    loadProducts(false)

    // Auto-refresh via SSE for instant updates (with reconnect limit)
    let sseErrors = 0
    const eventSource = new EventSource('/api/stream')
    eventSource.addEventListener('update', () => {
      sseErrors = 0
      loadProducts(true)
    })
    eventSource.onerror = () => {
      sseErrors++
      if (sseErrors > 5) { eventSource.close() }
    }

    // Fallback polling (covers SSE disconnections)
    const refreshInterval = setInterval(() => loadProducts(true), 60000)

    return () => {
      clearInterval(refreshInterval)
      eventSource.close()
    }
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    // Apply Telegram theme if available
    if (window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp
      tg.ready()
      tg.expand()
      if (tg.themeParams) {
        const root = document.documentElement
        Object.entries(tg.themeParams).forEach(([key, value]) => {
          root.style.setProperty(`--tg-theme-${key.replace(/_/g, '-')}`, value)
        })
      }
    }
  }, [])

  // Per-product cart button state: 'loading' | 'pending' | 'success' | 'error' | null
  const [cartStates, setCartStates] = useState({})
  const [selectedProduct, setSelectedProduct] = useState(null)
  const handleOpenDetail = useCallback((product) => setSelectedProduct(product), [])
  const pendingWeightIdsRef = useRef(new Set())
  const [soldOutIds, setSoldOutIds] = useState(() => {
    try {
      const stored = localStorage.getItem('soldOutIds')
      const expiry = localStorage.getItem('soldOutIds_expiry')
      if (stored && expiry && Date.now() < parseInt(expiry)) {
        return new Set(JSON.parse(stored))
      }
      localStorage.removeItem('soldOutIds')
      localStorage.removeItem('soldOutIds_expiry')
      return new Set()
    } catch { return new Set() }
  })
  const [cartPanelOpen, setCartPanelOpen] = useState(false)
  const [cartCount, setCartCount] = useState(0)
  const [cartItemIds, setCartItemIds] = useState(new Set())
  const pendingCartAttemptsRef = useRef(new Map())
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)
  const [favoriteCategories, setFavoriteCategories] = useState(new Set())

  const refreshCartState = useCallback(async (retries = 1, delayMs = 0) => {
    const wait = (ms) => new Promise(resolve => window.setTimeout(resolve, ms))

    for (let attempt = 0; attempt < retries; attempt++) {
      if (attempt > 0 || delayMs > 0) {
        await wait(delayMs)
      }
      try {
        const res = await fetch(`/api/cart/items/${userId}`, {
          headers: getAuthHeaders(userId)
        })
        const cart = await res.json()
        if (cart.items_count != null) {
          setCartCount(cart.items_count)
          const ids = new Set((cart.items || []).map(item => String(item.id ?? item.product_id ?? '')))
          setCartItemIds(ids)
          return { ok: true, itemsCount: cart.items_count, itemIds: ids }
        }
      } catch {
        // best-effort retry path
      }
    }

    return { ok: false, itemsCount: cartCount, itemIds: cartItemIds }
  }, [cartCount, cartItemIds, userId])

  const pollCartAttemptStatus = useCallback(async (product, attemptId) => {
    const pid = String(product.id)
    const wait = (ms) => new Promise(resolve => window.setTimeout(resolve, ms))

    pendingCartAttemptsRef.current.set(pid, attemptId)

    for (let attempt = 0; attempt < 20; attempt++) {
      await wait(attempt === 0 ? 700 : 900)

      if (pendingCartAttemptsRef.current.get(pid) !== attemptId) {
        return
      }

      try {
        const res = await fetch(`/api/cart/add-status/${attemptId}`, {
          headers: getAuthHeaders(userId),
        })

        if (res.status === 401) {
          pendingCartAttemptsRef.current.delete(pid)
          setIsAuthenticated(false)
          setShowLogin(true)
          setCartStates(s => ({ ...s, [pid]: null }))
          return
        }

        if (!res.ok) {
          throw new Error(`Status ${res.status}`)
        }

        const data = await res.json()
        if (data.status === 'pending') {
          continue
        }

        pendingCartAttemptsRef.current.delete(pid)

        if (data.status === 'success') {
          setCartItemIds(prev => {
            const next = new Set(prev)
            next.add(pid)
            return next
          })
          if (typeof data.cart_items === 'number') {
            setCartCount(data.cart_items)
          } else {
            setCartCount(prev => prev + 1)
          }
          setCartStates(s => ({ ...s, [pid]: 'success' }))
          setToastMessage({ text: 'Товар добавлен в корзину', type: 'success' })
          window.setTimeout(() => setCartStates(s => ({ ...s, [pid]: null })), 2000)
          window.setTimeout(() => setToastMessage(null), 3000)
          return
        }

        const lastError = String(data.last_error || '')
        const soldOut = lastError.toLowerCase().includes('popup_analogs') || lastError.toLowerCase().includes('распрод')
        if (soldOut) {
          setSoldOutIds(s => {
            const next = new Set([...s, pid])
            try {
              localStorage.setItem('soldOutIds', JSON.stringify([...next]))
              localStorage.setItem('soldOutIds_expiry', String(Date.now() + 4 * 60 * 60 * 1000))
            } catch { }
            return next
          })
        }
        setCartStates(s => ({ ...s, [pid]: 'error' }))
        setToastMessage({
          text: soldOut ? 'Этот продукт уже раскупили' : 'Не удалось добавить товар',
          type: 'error',
        })
        window.setTimeout(() => setCartStates(s => ({ ...s, [pid]: null })), 2000)
        window.setTimeout(() => setToastMessage(null), 3000)
        return
      } catch (err) {
        console.error(err)
      }
    }

    if (pendingCartAttemptsRef.current.get(pid) === attemptId) {
      pendingCartAttemptsRef.current.delete(pid)
      setCartStates(s => ({ ...s, [pid]: 'error' }))
      setToastMessage({ text: 'Не удалось подтвердить корзину', type: 'error' })
      window.setTimeout(() => setCartStates(s => ({ ...s, [pid]: null })), 2000)
      window.setTimeout(() => setToastMessage(null), 3000)
    }
  }, [userId])

  const handleAddToCart = useCallback(async (product) => {
    if (!isAuthenticated) {
      setShowLoginPrompt(true)
      return
    }

    const pid = product.id
    setCartStates(s => ({ ...s, [pid]: 'loading' }))

    try {
      const isGreen = product.type === 'green' ? 1 : 0
      const priceType = product.type === 'green' ? 222 : 1
      const clientRequestId = window.crypto?.randomUUID?.() || `cart-${Date.now()}-${pid}`
      const res = await fetch('/api/cart/add', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders(userId)
        },
        body: JSON.stringify({
          user_id: userId,
          product_id: parseInt(pid, 10),
          is_green: isGreen,
          price_type: priceType,
          allow_pending: true,
          client_request_id: clientRequestId,
        })
      })

      const data = await res.json()
      console.log('[cart/add]', res.status, data)
      if (res.ok && data.success) {
        pendingCartAttemptsRef.current.delete(String(pid))
        setCartItemIds(prev => {
          const next = new Set(prev)
          next.add(String(pid))
          return next
        })
        setCartStates(s => ({ ...s, [pid]: 'success' }))
        setCartCount(typeof data.cart_items === 'number' ? data.cart_items : cartCount + 1)
        setToastMessage({ text: 'Товар добавлен в корзину', type: 'success' })
        setTimeout(() => setCartStates(s => ({ ...s, [pid]: null })), 2000)
        setTimeout(() => setToastMessage(null), 3000)
        return
      }

      if (res.status === 202 && data.pending && data.status === 'pending' && data.attempt_id) {
        setCartStates(s => ({ ...s, [pid]: 'pending' }))
        setToastMessage({ text: 'Проверяем корзину…', type: 'info' })
        window.setTimeout(() => {
          setToastMessage(current => current?.text === 'Проверяем корзину…' ? null : current)
        }, 2500)
        void pollCartAttemptStatus(product, data.attempt_id)
        return
      }

      if (res.status === 401) {
        setIsAuthenticated(false)
        setShowLogin(true)
      } else {
        const detail = String(data?.detail || data?.error || '').toLowerCase()
        const soldOut =
          res.status === 400 &&
          (detail.includes('распрод') ||
           detail.includes('недоступ') ||
           detail.includes('out of stock') ||
           detail.includes('popup_analogs'))

        setToastMessage({
          text: soldOut ? 'Этот продукт уже раскупили' : 'Корзина временно недоступна',
          type: 'error'
        })
        setTimeout(() => setToastMessage(null), 4000)
        if (soldOut) {
          setSoldOutIds(s => {
            const next = new Set([...s, pid])
            try {
              localStorage.setItem('soldOutIds', JSON.stringify([...next]))
              localStorage.setItem('soldOutIds_expiry', String(Date.now() + 4 * 60 * 60 * 1000))
            } catch { }
            return next
          })
        }
      }
      setCartStates(s => ({ ...s, [pid]: 'error' }))
      setTimeout(() => setCartStates(s => ({ ...s, [pid]: null })), 2000)
    } catch (err) {
      console.error(err)
      pendingCartAttemptsRef.current.delete(String(pid))
      setCartStates(s => ({ ...s, [pid]: 'error' }))
      setToastMessage({ text: 'Ошибка сети', type: 'error' })
      setTimeout(() => setCartStates(s => ({ ...s, [pid]: null })), 2000)
      setTimeout(() => setToastMessage(null), 3000)
    }
  }, [cartCount, isAuthenticated, pollCartAttemptStatus, userId])

  // v1.7: Toggle group/subgroup category favorite
  const handleToggleCategoryFavorite = useCallback(async (categoryKey, categoryName) => {
    const wasFav = favoriteCategories.has(categoryKey)
    // Optimistic update
    setFavoriteCategories(prev => {
      const next = new Set(prev)
      if (wasFav) next.delete(categoryKey)
      else next.add(categoryKey)
      return next
    })
    try {
      const res = await fetch(`/api/favorites/${userId}/categories`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders(userId) },
        body: JSON.stringify({ category_key: categoryKey, category_name: categoryName })
      })
      if (!res.ok) throw new Error('API failed')
    } catch {
      // Rollback on error
      setFavoriteCategories(prev => {
        const next = new Set(prev)
        if (wasFav) next.add(categoryKey)
        else next.delete(categoryKey)
        return next
      })
    }
  }, [favoriteCategories, userId])

  const triggerCategoryScraper = () => {
    setCategorizingDone(false)
    setCategorizingRunning(true)
    setCategorizingStatus({
      running: true,
      last_run: new Date().toISOString(),
      last_output: '',
      exit_code: null,
    })
    const adminToken = localStorage.getItem('vv_admin_token') || ''
    fetch('/api/admin/run/categories', { method: 'POST', headers: { 'X-Admin-Token': adminToken } })
      .then(async (response) => {
        let data = null
        try {
          data = await response.json()
        } catch {
          data = null
        }

        if (!response.ok) {
          throw new Error(data?.detail || data?.message || 'Не удалось запустить определение категорий.')
        }

        setCategorizingStatus((prev) => ({
          ...(prev || {}),
          running: true,
          exit_code: null,
          last_output: data?.message || '',
        }))
      })
      .catch((err) => {
        setCategorizingRunning(false)
        setCategorizingDone(false)
        setCategorizingStatus({
          running: false,
          last_run: null,
          last_output: err.message,
          exit_code: 1,
        })
        setToastMessage({ text: err.message, type: 'error' })
        setTimeout(() => setToastMessage(null), 4000)
      })
  }

  // Poll categories scraper status while running
  useEffect(() => {
    if (!categorizingRunning) return
    const pollStatus = () => {
      fetch('/api/admin/run/categories/status')
        .then(async (response) => {
          const data = await response.json()
          if (!response.ok) {
            throw new Error(data?.detail || 'Не удалось получить статус определения категорий.')
          }
          return data
        })
        .then(data => {
          setCategorizingStatus(data)
          if (!data.running) {
            setCategorizingRunning(false)
            if (data.exit_code === 0) {
              setCategorizingDone(true)
              setSelectedCategory('all')
              loadProducts(false)
            } else {
              setCategorizingDone(false)
              setToastMessage({ text: 'Не удалось определить категории.', type: 'error' })
              setTimeout(() => setToastMessage(null), 4000)
            }
          }
        })
        .catch((err) => {
          setCategorizingRunning(false)
          setCategorizingDone(false)
          setCategorizingStatus({
            running: false,
            last_run: null,
            last_output: err.message,
            exit_code: 1,
          })
        })
    }

    pollStatus()
    const interval = setInterval(() => {
      pollStatus()
    }, 3000)
    return () => clearInterval(interval)
  }, [categorizingRunning]) // eslint-disable-line react-hooks/exhaustive-deps

  const enrichedProducts = useMemo(
    () => mergeResolvedWeights(products, resolvedWeights),
    [products, resolvedWeights],
  )

  // Apply both category and type filters + sorting (memoized for performance)
  const filteredProducts = useMemo(() => {
    const activeTypes = Object.entries(typeFilters)
      .filter(([, active]) => active)
      .map(([k]) => k)

    const filtered = enrichedProducts.filter(p => {
      if (soldOutIds.has(p.id)) return false
      // Use group field for category matching (v1.7), fallback to category
      const productGroup = p.group || p.category || ''
      const categoryMatch = selectedCategory === 'all' || productGroup === selectedCategory
      // Subgroup filter (only when a subgroup is selected)
      const subgroupMatch = !selectedSubgroup || p.subgroup === selectedSubgroup
      const typeMatch = activeTypes.includes(p.type)
      const favMatch = !showFavoritesOnly || favorites.has(p.id)
      return categoryMatch && subgroupMatch && typeMatch && favMatch
    })

    // Sort yellow products by discount % (highest first) when yellow-only is active
    const onlyYellow = activeTypes.length === 1 && activeTypes[0] === 'yellow'
    if (onlyYellow) {
      filtered.sort((a, b) => {
        const oldA = parseInt(a.oldPrice) || 0
        const curA = parseInt(a.currentPrice) || 0
        const oldB = parseInt(b.oldPrice) || 0
        const curB = parseInt(b.currentPrice) || 0
        const discA = oldA > 0 ? ((oldA - curA) / oldA) : 0
        const discB = oldB > 0 ? ((oldB - curB) / oldB) : 0
        return discB - discA
      })
    }

    return filtered
  }, [enrichedProducts, typeFilters, selectedCategory, selectedSubgroup, showFavoritesOnly, favorites, soldOutIds])

  // Reset visible count when filters change
  useEffect(() => {
    setVisibleCount(CARDS_PER_PAGE)
  }, [typeFilters, selectedCategory, selectedSubgroup, showFavoritesOnly])

  // Infinite scroll — load more cards when sentinel is visible
  useEffect(() => {
    const ref = loadMoreRef.current
    if (!ref) return
    const observer = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) {
        setVisibleCount(prev => Math.min(prev + CARDS_PER_PAGE, filteredProducts.length))
      }
    }, { rootMargin: '200px' })
    observer.observe(ref)
    return () => observer.disconnect()
  }, [filteredProducts.length])

  useEffect(() => {
    const productsNeedingWeight = filteredProducts
      .filter(shouldFetchMissingWeight)
      .filter(product => !resolvedWeights[product.id] && !pendingWeightIdsRef.current.has(product.id))
      .slice(0, 8)

    if (productsNeedingWeight.length === 0) return

    let cancelled = false
    for (const product of productsNeedingWeight) {
      pendingWeightIdsRef.current.add(product.id)
    }

    const timer = window.setTimeout(() => {
      const queue = [...productsNeedingWeight]
      const loadedWeights = {}

      const worker = async () => {
        while (queue.length > 0 && !cancelled) {
          const product = queue.shift()
          if (!product) return

          try {
            const res = await fetch(`/api/product/${product.id}/details`)
            if (!res.ok) {
              throw new Error(`Failed to load weight for ${product.id}`)
            }
            const data = await res.json()
            const weight = String(data?.weight || '').trim()
            if (weight) {
              loadedWeights[product.id] = weight
            }
          } catch {
            // Best-effort enrichment only.
          } finally {
            pendingWeightIdsRef.current.delete(product.id)
          }
        }
      }

      Promise.allSettled([
        worker(),
        worker(),
      ]).then(() => {
        if (cancelled) return
        if (Object.keys(loadedWeights).length === 0) return

        setResolvedWeights((prev) => {
          let changed = false
          const next = { ...prev }
          for (const [id, weight] of Object.entries(loadedWeights)) {
            if (next[id]) continue
            next[id] = weight
            changed = true
          }
          return changed ? next : prev
        })
      })
    }, 200)

    return () => {
      cancelled = true
      window.clearTimeout(timer)
      for (const product of productsNeedingWeight) {
        pendingWeightIdsRef.current.delete(product.id)
      }
    }
  }, [filteredProducts, resolvedWeights])

  const categoryRunView = useMemo(
    () => buildCategoryRunView(categorizingStatus),
    [categorizingStatus],
  )

  // Build dynamic group categories from products (after type filtering)
  // v1.7: Uses group field (VkusVill hierarchy) instead of flat category
  const categories = useMemo(() => {
    const activeTypes = Object.entries(typeFilters).filter(([, active]) => active).map(([k]) => k)
    const productsAfterTypeFilter = enrichedProducts.filter(p => activeTypes.includes(p.type))
    // Use group field, fallback to category for backwards compatibility
    const getGroup = (p) => p.group || p.category || ''
    const groupCounts = {}
    for (const p of productsAfterTypeFilter) {
      const g = getGroup(p)
      if (g) groupCounts[g] = (groupCounts[g] || 0) + 1
    }
    const sortedGroups = Object.entries(groupCounts)
      .sort((a, b) => b[1] - a[1]) // sort by count descending
      .map(([g]) => g)
    const chips = [
      { id: 'all', label: `🏷️ Все` },
      ...sortedGroups.map(g => ({ id: g, label: `${getCategoryEmoji(g)} ${g}`, favKey: `group:${g}` }))
    ]
    return chips
  }, [enrichedProducts, typeFilters])

  // Build subgroup chips for the selected group (v1.7)
  const subgroupChips = useMemo(() => {
    if (selectedCategory === 'all') return []
    const activeTypes = Object.entries(typeFilters).filter(([, active]) => active).map(([k]) => k)
    const groupProducts = enrichedProducts.filter(p => {
      const g = p.group || p.category || ''
      return g === selectedCategory && activeTypes.includes(p.type)
    })
    const subCounts = {}
    for (const p of groupProducts) {
      const sg = p.subgroup
      if (sg) subCounts[sg] = (subCounts[sg] || 0) + 1
    }
    const sorted = Object.entries(subCounts)
      .sort((a, b) => b[1] - a[1])
    // Only show subgroup chips if there are 2+ subgroups
    if (sorted.length < 2) return []
    return [
      { id: null, label: 'Все' },
      ...sorted.map(([sg, cnt]) => ({ id: sg, label: `${sg} (${cnt})`, favKey: `subgroup:${selectedCategory}/${sg}` }))
    ]
  }, [selectedCategory, enrichedProducts, typeFilters])

  // Calculate counts for header
  const totalCount = enrichedProducts.length
  const countGreen = enrichedProducts.filter(p => p.type === 'green').length
  const countRed = enrichedProducts.filter(p => p.type === 'red').length
  const countYellow = enrichedProducts.filter(p => p.type === 'yellow').length
  const staleColorLabels = useMemo(() => {
    if (!sourceFreshness) return []
    const labels = {
      green: 'зелёные',
      red: 'красные',
      yellow: 'жёлтые',
    }
    return Object.entries(sourceFreshness)
      .filter(([, info]) => info?.isStale)
      .map(([color]) => labels[color] || color)
  }, [sourceFreshness])

  // Dynamic header based on active filters
  const activeTypes = Object.entries(typeFilters).filter(([, active]) => active).map(([type]) => type)
  let headerTitle = 'Все акции ВкусВилл'
  let headerEmoji = '🏷️'

  if (activeTypes.length === 0) {
    headerTitle = 'Нет акций'
    headerEmoji = '❌'
  } else if (activeTypes.length === 3) {
    headerTitle = 'Все акции ВкусВилл'
    headerEmoji = '🏷️'
  } else if (activeTypes.length === 1) {
    if (activeTypes[0] === 'green') {
      headerTitle = 'Зелёные ценники'
      headerEmoji = '🟢'
    } else if (activeTypes[0] === 'red') {
      headerTitle = 'Красные ценники'
      headerEmoji = '🔴'
    } else if (activeTypes[0] === 'yellow') {
      headerTitle = 'Жёлтые ценники'
      headerEmoji = '🟡'
    }
  } else if (activeTypes.length === 2) {
    headerTitle = 'Выбранные акции'
    headerEmoji = '🏷️'
  }

  if (showLogin) {
    return (
      <div className="min-h-screen p-4 app-container">
        <button
          onClick={() => setShowLogin(false)}
          className="header-pill header-pill-action mb-4"
        >
          {'\u25c0'} Назад
        </button>
        <Login
          userId={userId}
          onLoginSuccess={(phone) => {
            setIsAuthenticated(true)
            if (phone) setUserPhone(phone)
            setShowLogin(false)
          }}
        />
      </div>
    )
  }

  // Login prompt overlay (shows when unauthenticated user tries to add to cart)
  const loginPromptOverlay = showLoginPrompt && (
    <div className="login-prompt-overlay" onClick={() => setShowLoginPrompt(false)}>
      <div
        className="login-prompt-card anim-pop"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="login-prompt-icon">🛒</div>
        <h3 className="login-prompt-title">Нужна авторизация</h3>
        <p className="login-prompt-text">
          Чтобы добавить товар в корзину ВкусВилл, нужно войти в аккаунт.
        </p>
        <button
          className="login-prompt-btn login-prompt-btn-primary"
          onClick={() => { setShowLoginPrompt(false); setShowLogin(true) }}
        >
          Войти
        </button>
        <button
          className="login-prompt-btn login-prompt-btn-secondary"
          onClick={() => setShowLoginPrompt(false)}
        >
          Не сейчас
        </button>
      </div>
    </div>
  )

  // If on history detail page, render it
  if (currentPage === 'history-detail' && historyDetailId) {
    return (
      <div className="app-container" data-theme={theme}>
        <Suspense fallback={<div style={{minHeight:'100vh',display:'flex',alignItems:'center',justifyContent:'center',opacity:0.5}}>Загружаем…</div>}>
          <HistoryDetail
            productId={historyDetailId}
            onBack={() => {
              setCurrentPage('history')
              setHistoryDetailId(null)
            }}
          />
        </Suspense>
      </div>
    )
  }

  // If on history page, render it instead
  if (currentPage === 'history') {
    return (
      <div className="app-container" data-theme={theme}>
        <Suspense fallback={<div style={{minHeight:'100vh',display:'flex',alignItems:'center',justifyContent:'center',opacity:0.5}}>Загружаем…</div>}>
          <HistoryPage
            onBack={() => setCurrentPage('main')}
            onOpenDetail={(productId) => {
              setHistoryDetailId(productId)
              setCurrentPage('history-detail')
            }}
            favorites={favorites}
            onToggleFavorite={handleToggleFavorite}
            userId={userId}
          />
        </Suspense>
      </div>
    )
  }


  return (
    <div className="min-h-screen p-4 app-container">
      {/* Header */}
      <div
        className="text-center mb-6 anim-slide-down"
      >
        <h1 className="text-2xl font-bold mb-2">{headerEmoji} {headerTitle}</h1>

        {/* Open in browser link — only shown inside a real Telegram Mini App session */}
        {isTelegramMiniApp && (
          <div
            onClick={() => {
              const url = 'https://vkusvillsale.vercel.app'
              if (window.Telegram?.WebApp?.openLink) {
                window.Telegram.WebApp.openLink(url)
              } else {
                window.open(url, '_blank')
              }
            }}
            style={{
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              gap: '4px',
              marginBottom: '6px',
              fontSize: '11px',
              color: '#2AABEE',
              cursor: 'pointer',
              opacity: 0.8,
            }}
          >
            <span>🌐</span>
            <span style={{ textDecoration: 'underline', textUnderlineOffset: '2px' }}>
              Открыть сайт в браузере
            </span>
          </div>
        )}

        {/* Small Telegram link for guest users */}
        {isGuest && linkUrl && !linkDismissed && (
          <div style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '6px',
            marginBottom: '8px',
            fontSize: '12px',
            color: 'var(--tg-theme-hint-color)',
          }}>
            <span>🔔</span>
            <span
              onClick={(e) => {
                if (!isAuthenticated) {
                  e.preventDefault()
                  setShowLoginPrompt(true)
                  return
                }
                window.open(linkUrl, '_blank', 'noopener,noreferrer')
              }}
              style={{
                color: '#2AABEE',
                cursor: 'pointer',
                textDecoration: 'underline',
                textUnderlineOffset: '2px',
              }}
            >
              Привязать Telegram
            </span>
            <span style={{ color: 'var(--tg-theme-hint-color)', opacity: 0.6 }}>для уведомлений</span>
            <button
              onClick={() => {
                setLinkDismissed(true)
                localStorage.setItem('link_dismissed', '1')
              }}
              style={{
                background: 'none',
                border: 'none',
                color: 'var(--tg-theme-hint-color)',
                fontSize: '14px',
                cursor: 'pointer',
                padding: '0 2px',
                opacity: 0.5
              }}
              aria-label="Закрыть"
            >
              ✕
            </button>
          </div>
        )}

        {/* Controls row: Auth + Theme + Admin */}
        <div className="flex items-center justify-center gap-2 mb-3 flex-wrap">
          {isAuthenticated ? (
            <>
              <button
                onClick={async () => {
                  try {
                    await fetch('/api/auth/logout', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ user_id: String(userId) })
                    })
                  } catch (e) { }
                  setIsAuthenticated(false)
                  setUserPhone(null)
                  localStorage.removeItem('vv_authenticated')
                  localStorage.removeItem('vv_user_phone')
                }}
                className="header-pill header-pill-success"
                title="Нажмите чтобы выйти"
              >
                🚪 Выйти {userPhone ? `(${userPhone.replace(/(\d{3})\d{5}(\d{2})/, '$1-***-**-$2')})` : ''}
              </button>
              <button
                onClick={() => setCartPanelOpen(true)}
                className="header-pill header-pill-cart"
                title="Корзина"
              >
                🛒{cartCount > 0 && <span className="cart-badge">{cartCount}</span>}
              </button>
            </>
          ) : (
            <>
              <button
                onClick={() => setShowLogin(true)}
                className="header-pill header-pill-action"
              >
                🔑 Войти
              </button>
              <button
                onClick={() => setShowLogin(true)}
                className="header-pill header-pill-cart"
                title="Войдите для доступа к корзине"
              >
                🛒
              </button>
            </>
          )}
          <button
            onClick={() => setCurrentPage('history')}
            className="header-pill header-pill-action"
            title="История скидок"
          >
            📊 История
          </button>
          <button
            onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
            className="header-pill header-pill-action"
            aria-label="Переключить тему"
          >
            {theme === 'dark' ? '\u2600\ufe0f' : '\ud83c\udf19'}
          </button>
          {isAuthenticated && (
            <a
              href={`${window.location.origin}/admin`}
              target="_blank"
              rel="noopener noreferrer"
              className="header-pill header-pill-action"
            >
              {'\ud83d\udee0\ufe0f'} Админ
            </a>
          )}
        </div>

        {/* Detailed Stats */}
        <div className="flex justify-center gap-4 text-xs mt-2 opacity-80 font-medium flex-wrap">
          <div className="flex items-center gap-1">
            <span className="text-lg">📦</span>
            <span>{totalCount} всего</span>
          </div>
          <div className="flex items-center gap-1 text-green-500">
            <span className="text-lg">🟢</span>
            <span>{countGreen}</span>
          </div>
          <div className="flex items-center gap-1 text-red-500">
            <span className="text-lg">🔴</span>
            <span>{countRed}</span>
          </div>
          <div className="flex items-center gap-1 text-yellow-500">
            <span className="text-lg">🟡</span>
            <span>{countYellow}</span>
          </div>
        </div>

        {/* Updated At — below stats */}
        <div className="text-center text-xs opacity-60 mt-1">
          Обновлено: {updatedAt ? new Date(updatedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : '---'}
        </div>

        {/* Stale data warning — shown when merge detected old files */}
        {dataStale && (
          <div
            className="mt-2 px-4 py-2 rounded-xl bg-yellow-500/20 border border-yellow-500/50 text-yellow-300 text-center text-xs anim-scale"
          >
            ⚠️ Данные устарели{staleColorLabels.length ? `: ${staleColorLabels.join(', ')}` : ''} — товары и цены могут не совпадать с сайтом
          </div>
        )}

        {/* Green products missing warning */}
        {greenMissing && (
          <div
            className="mt-2 px-4 py-2 rounded-xl bg-green-500/10 border border-green-500/30 text-green-400 text-center text-xs anim-scale"
          >
            🟢 Зелёные ценники недоступны — требуется авторизация тех. аккаунта
          </div>
        )}

        {/* Client-side time check — if data is older than 15 min */}
        {!dataStale && updatedAt && (Date.now() - new Date(updatedAt).getTime() > 15 * 60 * 1000) && (
          <div className="stale-info-bar">
            Обновлено {Math.round((Date.now() - new Date(updatedAt).getTime()) / 60000)} мин. назад
          </div>
        )}

        {/* Green staleness warning — shown when our green count is suspiciously low vs live site count.
            greenLiveCount = total green items on VkusVill page (~150-200)
            countGreen = our curated subset (filters by IS_GREEN, availability, etc.)
            Normal ratio is 10-30%. Warn only if we have <10% OR zero when live has items. */}
        {greenLiveCount !== null && greenLiveCount > 0 && countGreen > 0 &&
         (countGreen / greenLiveCount) < 0.05 && (
          <div
            className="mt-3 px-4 py-2 rounded-xl bg-red-500/20 border border-red-500/50 text-red-400 text-center anim-scale"
          >
            <div className="font-bold text-sm">⚠️ Зелёные ценники могли устареть</div>
            <div className="text-xs opacity-70 mt-0.5">
              На сайте {greenLiveCount} товаров, у нас {countGreen} — возможно скрапер не собрал все данные
            </div>
            {scraperDone ? (
              <div className="mt-2 text-xs text-green-400 font-medium">
                ✅ Обновление запущено — данные появятся через ~2 минуты
              </div>
            ) : showTokenInput ? (
              /* Inline token input — avoids window.prompt() which is blocked in Telegram WebApp */
              <div className="mt-2 flex gap-2 items-center justify-center">
                <input
                  type="password"
                  value={tokenInputValue}
                  onChange={e => setTokenInputValue(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && tokenInputValue) {
                      const t = tokenInputValue
                      localStorage.setItem('vv_admin_token', t)
                      setShowTokenInput(false)
                      setTokenInputValue('')
                      setScraperRunning(true)
                      fetch('/api/admin/run/green', { method: 'POST', headers: { 'X-Admin-Token': t } })
                        .then(r => { if (r.status === 403) { localStorage.removeItem('vv_admin_token'); setScraperRunning(false); setShowTokenInput(true); return null } return r.json() })
                        .then(data => { if (data) { setScraperRunning(false); setScraperDone(true) } })
                        .catch(() => setScraperRunning(false))
                    }
                    if (e.key === 'Escape') { setShowTokenInput(false); setTokenInputValue('') }
                  }}
                  placeholder="Токен администратора"
                  autoFocus
                  className="flex-1 text-xs px-2 py-1 rounded-lg bg-black/40 border border-red-500/40 text-red-200 outline-none max-w-40"
                />
                <button
                  onClick={() => {
                    if (!tokenInputValue) return
                    const t = tokenInputValue
                    localStorage.setItem('vv_admin_token', t)
                    setShowTokenInput(false)
                    setTokenInputValue('')
                    setScraperRunning(true)
                    fetch('/api/admin/run/green', { method: 'POST', headers: { 'X-Admin-Token': t } })
                      .then(r => { if (r.status === 403) { localStorage.removeItem('vv_admin_token'); setScraperRunning(false); setShowTokenInput(true); return null } return r.json() })
                      .then(data => { if (data) { setScraperRunning(false); setScraperDone(true) } })
                      .catch(() => setScraperRunning(false))
                  }}
                  className="text-xs px-3 py-1 rounded-lg bg-red-500/40 border border-red-500/60 text-red-200 font-bold"
                >Подтвердить</button>
                <button
                  onClick={() => { setShowTokenInput(false); setTokenInputValue('') }}
                  className="text-xs px-2 py-1 rounded-lg bg-black/30 text-red-400"
                  aria-label="Отмена"
                >✕</button>
              </div>
            ) : (
              <button
                className={`mt-2 px-4 py-1.5 rounded-lg text-xs font-bold border transition-all tap-scale ${scraperRunning
                  ? 'bg-red-500/10 border-red-500/30 opacity-60 cursor-wait'
                  : 'bg-red-500/30 border-red-500/50 hover:bg-red-500/40 cursor-pointer'
                  }`}
                disabled={scraperRunning}
                onClick={() => {
                  const storedToken = localStorage.getItem('vv_admin_token')
                  if (storedToken) {
                    setScraperRunning(true)
                    fetch('/api/admin/run/green', { method: 'POST', headers: { 'X-Admin-Token': storedToken } })
                      .then(r => {
                        if (r.status === 403) {
                          localStorage.removeItem('vv_admin_token')
                          setScraperRunning(false)
                          setShowTokenInput(true)
                          return null
                        }
                        return r.json()
                      })
                      .then(data => { if (data) { setScraperRunning(false); setScraperDone(true) } })
                      .catch(() => setScraperRunning(false))
                  } else {
                    setShowTokenInput(true)
                  }
                }}
              >
                {scraperRunning ? '⏳ Запускаем…' : '🔄 Обновить данные'}
              </button>
            )}
          </div>
        )}
      </div>

      {/* Type Filter Toggles */}
      <div
        className="flex gap-2 mb-3 justify-center relative z-20 flex-wrap items-center anim-fade anim-delay-1"
      >
        {/* Select All Button if any are unchecked */}
        {!Object.values(typeFilters).every(v => v) && (
          <button
            onClick={() => setTypeFilters({ green: true, red: true, yellow: true })}
            className="text-xs px-3 py-1.5 rounded-full transition-all type-chip type-chip-all active"
          >
            Все
          </button>
        )}

        <button
          onClick={() => setShowFavoritesOnly(f => !f)}
          className={`text-xs px-3 py-1.5 rounded-full transition-all type-chip ${showFavoritesOnly ? 'type-chip-fav active' : 'bg-gray-700/30 text-gray-500 border border-gray-600/30 opacity-60'}`}
        >
          ❤️{favorites.size > 0 ? ` ${enrichedProducts.filter(p => favorites.has(p.id)).length}` : ''}
        </button>

        {[
          { key: 'green', label: '🟢 Зелёные', activeClass: 'type-chip-green active' },
          { key: 'red', label: '🔴 Красные', activeClass: 'type-chip-red active' },
          { key: 'yellow', label: '🟡 Жёлтые', activeClass: 'type-chip-yellow active' }
        ].map(({ key, label, activeClass }) => (
          <button
            key={key}
            onClick={() => {
              // Smart toggle logic
              setTypeFilters(prev => {
                const allSelected = Object.values(prev).every(v => v)
                const onlyThisSelected = prev[key] && !Object.entries(prev).some(([k, v]) => k !== key && v)

                if (allSelected) {
                  return { green: false, red: false, yellow: false, [key]: true }
                }
                if (onlyThisSelected) {
                  return { green: true, red: true, yellow: true }
                }

                const next = { ...prev, [key]: !prev[key] }
                if (!Object.values(next).some(v => v)) {
                  return { green: true, red: true, yellow: true }
                }
                return next
              })
            }}
            className={`text-xs px-3 py-1.5 rounded-full transition-all type-chip ${typeFilters[key]
              ? activeClass
              : 'bg-gray-700/30 text-gray-500 border border-gray-600/30 opacity-60'
              }`}
          >
            {label}
          </button>
        ))}

        {/* View mode toggle */}
        <div className="view-toggle-group">
          <button
            onClick={() => setViewMode('list')}
            className={`view-toggle-btn ${viewMode === 'list' ? 'active' : ''}`}
            aria-label="Список"
          >
            ☰
          </button>
          <button
            onClick={() => setViewMode('grid')}
            className={`view-toggle-btn ${viewMode === 'grid' ? 'active' : ''}`}
            aria-label="Сетка"
          >
            ⊞
          </button>
        </div>
      </div>

      {/* Category Filter (Groups) */}
      <div
        className="mb-2 anim-fade anim-delay-2"
      >
        <CategoryFilter
          selected={selectedCategory}
          onSelect={(id) => {
            setSelectedCategory(id)
            setSelectedSubgroup(null) // Reset subgroup when group changes
          }}
          categories={categories}
          favoritedIds={favoriteCategories}
          onToggleFavorite={handleToggleCategoryFavorite}
        />
      </div>

      {/* Subgroup Filter (v1.7 drill-down) */}
      {subgroupChips.length > 0 && (
        <div className="mb-4 anim-fade">
          <ScrollableChips
            selected={selectedSubgroup}
            onSelect={setSelectedSubgroup}
            items={subgroupChips}
            className="subgroup-chips"
            favoritedIds={favoriteCategories}
            onToggleFavorite={handleToggleCategoryFavorite}
          />
        </div>
      )}

      {/* Новинки banner — shown when user selects uncategorized products chip */}
      {selectedCategory === 'Новинки' && (
        <div
          className="mb-4 px-4 py-3 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-center anim-scale"
        >
          <div className="text-xs opacity-70 mb-2">
            {filteredProducts.length} товаров ещё не распределены по категориям
          </div>
          {categorizingDone ? (
            <div className="text-xs text-green-400 font-medium">
              ✅ Готово — категории обновляются
            </div>
          ) : (
            <>
              <button
                className={`header-pill header-pill-action tap-scale ${categorizingRunning ? 'opacity-60 cursor-wait' : ''}`}
                disabled={categorizingRunning}
                onClick={triggerCategoryScraper}
              >
                {categorizingRunning ? '⏳ Определяем...' : '🔄 Определить категории'}
              </button>
              {categoryRunView.summary && (
                <div className={`mt-2 text-xs ${categoryRunView.isError ? 'text-red-400' : 'opacity-70'}`}>
                  {categoryRunView.summary}
                </div>
              )}
              {categoryRunView.lines.length > 0 && (
                <div className={`mt-2 mx-auto max-w-2xl rounded-xl border px-3 py-2 text-left text-[11px] whitespace-pre-wrap ${categoryRunView.isError
                  ? 'border-red-500/30 bg-red-500/10 text-red-300'
                  : 'border-yellow-500/20 bg-black/10 opacity-80'
                  }`}>
                  {categoryRunView.lines.join('\n')}
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* Loading state */}
      {loading && (
        <div className="text-center py-8 opacity-60">
          Загружаем товары…
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="text-center py-8 text-red-400">
          <div className="text-lg mb-1">😔</div>
          <div>{error}</div>
          <button onClick={() => window.location.reload()} className="mt-3 px-4 py-2 rounded-xl bg-red-500/20 border border-red-500/40 text-red-300 text-sm hover:bg-red-500/30 transition-all">Обновить страницу</button>
        </div>
      )}

      {/* Product Grid */}
      <div className={`product-grid ${viewMode === 'list' ? 'list-view' : ''}`}>
          {filteredProducts.slice(0, visibleCount).map((product, index) => (
            <ProductCard
              key={`${product.id}-${product.type}`}
              product={product}
              index={index}
              isFavorite={favorites.has(product.id)}
              onToggleFavorite={handleToggleFavorite}
              onAddToCart={handleAddToCart}
              onOpenDetail={handleOpenDetail}
              cartState={cartStates[product.id] || null}
              favoritesLoading={favoritesLoading}
              viewMode={viewMode}
            />
          ))}

          {/* Infinite scroll sentinel */}
          {visibleCount < filteredProducts.length && (
            <div ref={loadMoreRef} style={{ gridColumn: '1/-1', textAlign: 'center', padding: '20px', opacity: 0.5, fontSize: '14px' }}>
              Загружаем ещё {Math.min(CARDS_PER_PAGE, filteredProducts.length - visibleCount)} из {filteredProducts.length - visibleCount}…
            </div>
          )}

        {filteredProducts.length === 0 && !loading && !error && (
          <div
            className="text-center py-8 opacity-60 anim-fade anim-delay-3"
            style={{ gridColumn: '1 / -1' }}
          >
            В этой категории пока нет товаров. Попробуйте другой фильтр
          </div>
        )}
      </div>

      {/* Footer removed as moved to header */}

      {/* Cart Panel */}
      <CartPanel
        isOpen={cartPanelOpen}
        onClose={() => setCartPanelOpen(false)}
        userId={userId}
      />

      {/* Product Detail Drawer */}
      {selectedProduct && (
        <ProductDetail
          product={selectedProduct}
          onClose={() => setSelectedProduct(null)}
          onAddToCart={handleAddToCart}
          cartState={cartStates[selectedProduct.id] || null}
        />
      )}

      {/* Login prompt overlay */}
      {loginPromptOverlay}

      {/* Floating Toast Notification */}
      {toastMessage && (
        <div
          className={`fixed top-16 left-1/2 -translate-x-1/2 px-4 py-2.5 rounded-xl shadow-[0_0_20px_rgba(0,0,0,0.3)] z-[200] text-sm font-medium whitespace-nowrap border toast-enter ${toastMessage.type === 'error'
            ? 'bg-[#2a1313] text-red-400 border-red-500/30'
            : toastMessage.type === 'info'
              ? 'bg-[#1f2134] text-amber-200 border-amber-400/30'
              : 'bg-[#132a18] text-green-400 border-green-500/30'
            }`}
        >
          {toastMessage.text}
        </div>
      )}
    </div>
  )
}

export default App
