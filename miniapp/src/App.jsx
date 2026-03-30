import { useState, useEffect, useMemo, useRef, useCallback, memo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import CartPanel from './CartPanel'
import ProductDetail from './ProductDetail'
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

  // Type badge config
  const typeConfig = {
    green: { bg: 'bg-green-500/20', text: 'text-green-400', label: '🟢 Зелёная', border: 'border-green-500/30', priceColor: '#4ade80', tint: 'card-tint-green' },
    red: { bg: 'bg-red-500/20', text: 'text-red-400', label: '🔴 Красная', border: 'border-red-500/30', priceColor: '#f87171', tint: 'card-tint-red' },
    yellow: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: '🟡 Жёлтая', border: 'border-yellow-500/30', priceColor: '#facc15', tint: 'card-tint-yellow' },
    _default: { bg: 'bg-gray-500/20', text: 'text-gray-400', label: '📦 Другое', border: 'border-gray-500/30', priceColor: '#9ca3af', tint: '' }
  }
  const config = typeConfig[product.type] || typeConfig._default

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
        <motion.button
          whileTap={{ scale: 0.8 }}
          onClick={(e) => {
            e.stopPropagation()
            if (!favoritesLoading) onToggleFavorite(product)
          }}
          disabled={favoritesLoading}
          className={`card-fav-btn ${isFavorite ? 'active' : ''} ${favoritesLoading ? 'loading' : ''}`}
        >
          {favoritesLoading ? (
            <div className="w-5 h-5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
          ) : (
            isFavorite ? '❤️' : '🤍'
          )}
        </motion.button>

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
          <motion.button
            whileTap={{ scale: 0.85 }}
            onClick={(e) => {
              e.stopPropagation()
              if (cartState !== 'loading') onAddToCart(product)
            }}
            className={`cart-btn ${cartState === 'success' ? 'cart-btn-success' : ''} ${cartState === 'error' ? 'cart-btn-error' : ''}`}
            aria-label="Добавить в корзину"
            disabled={cartState === 'loading'}
          >
            {cartState === 'loading' ? (
              <span className="cart-btn-spinner" />
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
          </motion.button>
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

function CategoryFilter({ selected, onSelect, categories }) {
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
    <div className="relative group">
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
        {categories.map((cat) => (
          <motion.button
            key={cat.id}
            onClick={() => onSelect(cat.id)}
            className={`category-chip ${selected === cat.id ? 'active' : ''}`}
            whileTap={{ scale: 0.95 }}
          >
            {cat.label}
          </motion.button>
        ))}
      </div>
    </div>
  )
}

function App() {
  const [products, setProducts] = useState([])
  const [resolvedWeights, setResolvedWeights] = useState({})
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [loading, setLoading] = useState(true)
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
  const [updatedAt, setUpdatedAt] = useState(null)
  const updatedAtRef = useRef(null)
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
  const [greenLiveCount, setGreenLiveCount] = useState(null)
  const [dataStale, setDataStale] = useState(false)
  const [greenMissing, setGreenMissing] = useState(false)
  const [scraperRunning, setScraperRunning] = useState(false)
  const [scraperDone, setScraperDone] = useState(false)
  const [showTokenInput, setShowTokenInput] = useState(false)
  const [tokenInputValue, setTokenInputValue] = useState('')
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('vv_view_mode') || 'grid')
  const [theme, setTheme] = useState(() => localStorage.getItem('vv_theme') || 'dark')
  const [categorizingRunning, setCategorizingRunning] = useState(false)
  const [categorizingDone, setCategorizingDone] = useState(false)
  const [categorizingStatus, setCategorizingStatus] = useState(null)

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
    // Load favorites
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
        // console.error('Failed to load favorites:', err)
      })
      .finally(() => setFavoritesLoading(false))

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
            .then(cart => { if (cart.items_count != null) setCartCount(cart.items_count) })
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
    if (!isAutoRefresh) setLoading(true)
    fetch('/api/products')
      .then(res => {
        if (!res.ok) throw new Error('Failed to load data')
        return res.json()
      })
      .then(data => {
        if (data.products && Array.isArray(data.products)) {
          // On auto-refresh, only update if data actually changed
          if (isAutoRefresh && data.updatedAt === updatedAtRef.current) return
          setProducts(data.products.map(p => ({ ...p, category: normalizeCategory(p.category) })))
          setUpdatedAt(data.updatedAt)
          updatedAtRef.current = data.updatedAt
          if (data.greenLiveCount !== undefined) setGreenLiveCount(data.greenLiveCount)
          setDataStale(!!data.dataStale)
          setGreenMissing(!!data.greenMissing)
        } else if (Array.isArray(data) && data.length > 0) {
          setProducts(data.map(p => ({ ...p, category: normalizeCategory(p.category) })))
        } else if (!isAutoRefresh) {
          setError('Товары не найдены')
        }
      })
      .catch(err => {
        if (isAutoRefresh) return // Silently ignore auto-refresh errors
        console.error('API Error:', err)
        setError('Не удалось загрузить данные. Проверьте подключение.')
      })
      .finally(() => {
        if (!isAutoRefresh) setLoading(false)
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

  // Per-product cart button state: 'loading' | 'success' | 'error' | null
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
  const [showFavoritesOnly, setShowFavoritesOnly] = useState(false)

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
          price_type: priceType
        })
      })

      const data = await res.json()
      console.log('[cart/add]', res.status, data)
      if (res.ok && data.success) {
        setCartStates(s => ({ ...s, [pid]: 'success' }))
        setCartCount(data.cart_items || cartCount + 1)
        setTimeout(() => setCartStates(s => ({ ...s, [pid]: null })), 2000)
      } else {
        if (res.status === 401) {
          setIsAuthenticated(false)
          setShowLogin(true)
        } else {
          setToastMessage({ text: 'Этот продукт уже раскупили', type: 'error' })
          setTimeout(() => setToastMessage(null), 4000)
          if (res.status === 400) {
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
      }
    } catch (err) {
      console.error(err)
      setCartStates(s => ({ ...s, [pid]: 'error' }))
      setToastMessage({ text: 'Ошибка сети', type: 'error' })
      setTimeout(() => setCartStates(s => ({ ...s, [pid]: null })), 2000)
      setTimeout(() => setToastMessage(null), 3000)
    }
  })

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
      const categoryMatch = selectedCategory === 'all' || p.category === selectedCategory
      const typeMatch = activeTypes.includes(p.type)
      const favMatch = !showFavoritesOnly || favorites.has(p.id)
      return categoryMatch && typeMatch && favMatch
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
  }, [enrichedProducts, typeFilters, selectedCategory, showFavoritesOnly, favorites, soldOutIds])

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

    Promise.allSettled(
      productsNeedingWeight.map(async (product) => {
        const res = await fetch(`/api/product/${product.id}/details`)
        if (!res.ok) {
          throw new Error(`Failed to load weight for ${product.id}`)
        }
        const data = await res.json()
        return {
          id: product.id,
          weight: String(data?.weight || '').trim(),
        }
      }),
    )
      .then((results) => {
        if (cancelled) return

        setResolvedWeights((prev) => {
          let changed = false
          const next = { ...prev }

          for (const result of results) {
            if (result.status !== 'fulfilled') continue
            if (!result.value.weight) continue
            if (next[result.value.id]) continue

            next[result.value.id] = result.value.weight
            changed = true
          }

          return changed ? next : prev
        })
      })
      .finally(() => {
        for (const product of productsNeedingWeight) {
          pendingWeightIdsRef.current.delete(product.id)
        }
      })

    return () => {
      cancelled = true
    }
  }, [filteredProducts, resolvedWeights])

  const categoryRunView = useMemo(
    () => buildCategoryRunView(categorizingStatus),
    [categorizingStatus],
  )

  // Build dynamic categories from products (after type filtering)
  const categories = useMemo(() => {
    const activeTypes = Object.entries(typeFilters).filter(([, active]) => active).map(([k]) => k)
    const productsAfterTypeFilter = enrichedProducts.filter(p => activeTypes.includes(p.type))
    const noveltyCount = productsAfterTypeFilter.filter(p => p.category === 'Новинки').length
    // Sort all categories except 'Новинки' (pinned to position 1)
    const uniqueCategories = [...new Set(
      productsAfterTypeFilter.filter(p => p.category !== 'Новинки').map(p => p.category)
    )].sort()
    const chips = [
      { id: 'all', label: '🏷️ Все' },
      ...uniqueCategories.map(cat => ({ id: cat, label: `${getCategoryEmoji(cat)} ${cat}` }))
    ]
    if (noveltyCount > 0) {
      chips.splice(1, 0, { id: 'Новинки', label: `🆕 Новинки (${noveltyCount})` })
    }
    return chips
  }, [enrichedProducts, typeFilters])

  // Calculate counts for header
  const totalCount = enrichedProducts.length
  const countGreen = enrichedProducts.filter(p => p.type === 'green').length
  const countRed = enrichedProducts.filter(p => p.type === 'red').length
  const countYellow = enrichedProducts.filter(p => p.type === 'yellow').length

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
      <motion.div
        className="login-prompt-card"
        initial={{ opacity: 0, scale: 0.9, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
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
      </motion.div>
    </div>
  )

  return (
    <div className="min-h-screen p-4 app-container">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-6"
      >
        <h1 className="text-2xl font-bold mb-2">{headerEmoji} {headerTitle}</h1>

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
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-2 px-4 py-2 rounded-xl bg-yellow-500/20 border border-yellow-500/50 text-yellow-300 text-center text-xs"
          >
            ⚠️ Данные устарели — товары и цены могут не совпадать с сайтом
          </motion.div>
        )}

        {/* Green products missing warning */}
        {greenMissing && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-2 px-4 py-2 rounded-xl bg-green-500/10 border border-green-500/30 text-green-400 text-center text-xs"
          >
            🟢 Зелёные ценники недоступны — требуется авторизация тех. аккаунта
          </motion.div>
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
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-3 px-4 py-2 rounded-xl bg-red-500/20 border border-red-500/50 text-red-400 text-center"
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
                        .then(r => r.status === 403 ? (localStorage.removeItem('vv_admin_token'), null) : r.json())
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
                      .then(r => r.status === 403 ? (localStorage.removeItem('vv_admin_token'), null) : r.json())
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
              <motion.button
                whileTap={{ scale: 0.95 }}
                disabled={scraperRunning}
                onClick={() => {
                  const storedToken = localStorage.getItem('vv_admin_token')
                  if (storedToken) {
                    // Token already stored — fire immediately
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
                    // No token — show inline input (prompt() is blocked in Telegram WebApp)
                    setShowTokenInput(true)
                  }
                }}
                className={`mt-2 px-4 py-1.5 rounded-lg text-xs font-bold border transition-all ${scraperRunning
                  ? 'bg-red-500/10 border-red-500/30 opacity-60 cursor-wait'
                  : 'bg-red-500/30 border-red-500/50 hover:bg-red-500/40 cursor-pointer'
                  }`}
              >
                {scraperRunning ? '⏳ Запускаем…' : '🔄 Обновить данные'}
              </motion.button>
            )}
          </motion.div>
        )}
      </motion.div>

      {/* Type Filter Toggles */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
        className="flex gap-2 mb-3 justify-center relative z-20 flex-wrap items-center"
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
      </motion.div>

      {/* Category Filter */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.2 }}
        className="mb-4"
      >
        <CategoryFilter
          selected={selectedCategory}
          onSelect={setSelectedCategory}
          categories={categories}
        />
      </motion.div>

      {/* Новинки banner — shown when user selects uncategorized products chip */}
      {selectedCategory === 'Новинки' && (
        <motion.div
          initial={{ opacity: 0, scale: 0.95 }}
          animate={{ opacity: 1, scale: 1 }}
          className="mb-4 px-4 py-3 rounded-xl bg-yellow-500/10 border border-yellow-500/30 text-center"
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
              <motion.button
                whileTap={{ scale: 0.95 }}
                disabled={categorizingRunning}
                onClick={triggerCategoryScraper}
                className={`header-pill header-pill-action ${categorizingRunning ? 'opacity-60 cursor-wait' : ''}`}
              >
                {categorizingRunning ? '⏳ Определяем...' : '🔄 Определить категории'}
              </motion.button>
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
        </motion.div>
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
          {filteredProducts.map((product, index) => (
            <ProductCard
              key={product.id}
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

        {filteredProducts.length === 0 && !loading && !error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-8 opacity-60"
            style={{ gridColumn: '1 / -1' }}
          >
            В этой категории пока нет товаров. Попробуйте другой фильтр
          </motion.div>
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
      <AnimatePresence>
        {toastMessage && (
          <motion.div
            initial={{ opacity: 0, y: -30 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -30 }}
            className={`fixed top-16 left-1/2 -translate-x-1/2 px-4 py-2.5 rounded-xl shadow-[0_0_20px_rgba(0,0,0,0.3)] z-[200] text-sm font-medium whitespace-nowrap border ${toastMessage.type === 'error' ? 'bg-[#2a1313] text-red-400 border-red-500/30' : 'bg-[#132a18] text-green-400 border-green-500/30'
              }`}
          >
            {toastMessage.text}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}

export default App
