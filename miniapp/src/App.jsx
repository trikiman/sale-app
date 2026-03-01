import { useState, useEffect, useMemo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import './index.css'

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
}

import Login from './Login'

function getCategoryEmoji(category) {
  // Simple partial match for categories not in the exact map
  if (CATEGORY_EMOJIS[category]) return CATEGORY_EMOJIS[category]
  if (category.includes('Сладости')) return CATEGORY_EMOJIS['Сладости']
  if (category.includes('Хлеб')) return CATEGORY_EMOJIS['Хлеб']
  return '📦'
}

function ProductCard({ product, index, isFavorite, onToggleFavorite, favoritesLoading, onAddToCart, viewMode }) {
  const [imageLoaded, setImageLoaded] = useState(false)
  const [imageError, setImageError] = useState(false)

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
    yellow: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: '🟡 Жёлтая', border: 'border-yellow-500/30', priceColor: '#facc15', tint: 'card-tint-yellow' }
  }
  const config = typeConfig[product.type] || typeConfig.green

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.03, 0.3) }}
      className={`card-vertical ${config.tint}`}
    >
      {/* Hero Image */}
      <div className="card-image-wrap">
        {!imageLoaded && !imageError && product.image && <div className="absolute inset-0 skeleton" />}

        {product.image && !imageError ? (
          <img
            src={product.image}
            alt={product.name}
            className={`card-hero-img ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
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
              onAddToCart(product)
            }}
            className="cart-btn"
            aria-label="Добавить в корзину"
          >
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
              <path strokeLinecap="round" strokeLinejoin="round" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z" />
            </svg>
          </motion.button>
        </div>

        {product.stock !== 99 && (
          <span className="card-stock">📦 {product.stock} {product.unit}</span>
        )}
      </div>
    </motion.div>
  )
}

function CategoryFilter({ selected, onSelect, categories }) {
  // Check if scroll is possible
  const [canScrollLeft, setCanScrollLeft] = useState(false)
  const [canScrollRight, setCanScrollRight] = useState(true)

  const checkScroll = (e) => {
    const el = e.target
    setCanScrollLeft(el.scrollLeft > 0)
    setCanScrollRight(el.scrollLeft < el.scrollWidth - el.clientWidth - 1)
  }

  return (
    <div className="relative group">
      {/* Scroll Indicators */}
      {canScrollLeft && (
        <div className="absolute left-0 top-0 bottom-2 w-8 bg-gradient-to-r from-black/50 to-transparent z-10 pointer-events-none rounded-l-xl" />
      )}
      {canScrollRight && (
        <div className="absolute right-0 top-0 bottom-2 w-8 bg-gradient-to-l from-black/50 to-transparent z-10 pointer-events-none rounded-r-xl" />
      )}

      <div
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
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [favoritesLoading, setFavoritesLoading] = useState(true)
  const [isAuthenticated, setIsAuthenticated] = useState(false)
  const [showLogin, setShowLogin] = useState(false)
  const [error, setError] = useState(null)
  const [updatedAt, setUpdatedAt] = useState(null)
  const [favorites, setFavorites] = useState(new Set())
  const [userId] = useState(() => {
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
  const [scraperRunning, setScraperRunning] = useState(false)
  const [scraperDone, setScraperDone] = useState(false)
  const [showTokenInput, setShowTokenInput] = useState(false)
  const [tokenInputValue, setTokenInputValue] = useState('')
  const [viewMode, setViewMode] = useState(() => localStorage.getItem('vv_view_mode') || 'grid')
  const [theme, setTheme] = useState(() => localStorage.getItem('vv_theme') || 'dark')

  // Apply theme
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme)
    localStorage.setItem('vv_theme', theme)
  }, [theme])

  // Persist view mode
  useEffect(() => {
    localStorage.setItem('vv_view_mode', viewMode)
  }, [viewMode])

  useEffect(() => {
    // Load favorites
    setFavoritesLoading(true)
    fetch(`/api/favorites/${userId}`)
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

    // Check auth status
    fetch(`/api/auth/status/${userId}`)
      .then(res => res.json())
      .then(data => {
        setIsAuthenticated(data.authenticated)
      })
      .catch(err => console.warn('Failed to check auth status:', err))
  }, [userId])

  const handleToggleFavorite = async (product) => {
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
          method: 'DELETE'
        })
        if (!res.ok && res.status !== 404) throw new Error('API failed')
      } else {
        // Add
        const res = await fetch(`/api/favorites/${userId}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
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
    }
  }

  useEffect(() => {
    // Load products from API
    fetch('/api/products')
      .then(res => {
        if (!res.ok) throw new Error('Failed to load data')
        return res.json()
      })
      .then(data => {
        // Handle both old format (array) and new format (object with updatedAt)
        if (data.products && Array.isArray(data.products)) {
          setProducts(data.products)
          setUpdatedAt(data.updatedAt)
          if (data.greenLiveCount !== undefined) setGreenLiveCount(data.greenLiveCount)
          if (data.dataStale) setDataStale(true)
        } else if (Array.isArray(data) && data.length > 0) {
          setProducts(data)
        } else {
          setError('Товары не найдены')
        }
      })
      .catch(err => {
        console.error('API Error:', err)
        // Fallback to static file if API fails — MUST return the promise so
        // .finally() waits for the fallback to resolve before setLoading(false)
        return fetch('./data.json')
          .then(res => res.json())
          .then(data => {
            if (data.products) {
              setProducts(data.products)
              setUpdatedAt(data.updatedAt)
              if (data.greenLiveCount !== undefined) setGreenLiveCount(data.greenLiveCount)
              if (data.dataStale) setDataStale(true)
            } else {
              setProducts(data)
            }
          })
          .catch(() => setError(err.message))
      })
      .finally(() => {
        setLoading(false)
      })

    // Apply Telegram theme if available
    if (window.Telegram?.WebApp) {
      const tg = window.Telegram.WebApp
      tg.ready()
      tg.expand()

      // Set CSS variables from Telegram theme
      if (tg.themeParams) {
        const root = document.documentElement
        Object.entries(tg.themeParams).forEach(([key, value]) => {
          root.style.setProperty(`--tg-theme-${key.replace(/_/g, '-')}`, value)
        })
      }
    }
  }, [])

  const handleAddToCart = async (product) => {
    if (!isAuthenticated) {
      setShowLogin(true)
      return
    }

    try {
      const isGreen = product.type === 'green' ? 1 : 0
      const priceType = product.type === 'green' ? 222 : 1

      const res = await fetch('/api/cart/add', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_id: userId,
          product_id: parseInt(product.id, 10),
          is_green: isGreen,
          price_type: priceType
        })
      })

      const data = await res.json()
      if (res.ok && data.success) {
        if (window.Telegram?.WebApp) {
          window.Telegram.WebApp.showAlert(`Добавлено в корзину\nВ корзине: ${data.cart_items} товаров, ${data.cart_total} ₽`)
        } else {
          alert(`Добавлено в корзину\nВ корзине: ${data.cart_items} товаров, ${data.cart_total} ₽`)
        }
      } else {
        if (res.status === 401) {
          setIsAuthenticated(false)
          setShowLogin(true)
        } else {
          const errStr = data.detail || 'Не удалось добавить в корзину. Попробуйте ещё раз'
          if (window.Telegram?.WebApp) window.Telegram.WebApp.showAlert(errStr)
          else alert(errStr)
        }
      }
    } catch (err) {
      console.error(err)
      alert("Нет связи с сервером. Попробуйте ещё раз")
    }
  }

  // Apply both category and type filters + sorting (memoized for performance)
  const filteredProducts = useMemo(() => {
    const activeTypes = Object.entries(typeFilters)
      .filter(([, active]) => active)
      .map(([k]) => k)

    const filtered = products.filter(p => {
      const categoryMatch = selectedCategory === 'all' || p.category === selectedCategory
      const typeMatch = activeTypes.includes(p.type)
      return categoryMatch && typeMatch
    })

    // Sort yellow products by discount % (highest first) when yellow-only is active
    const onlyYellow = activeTypes.length === 1 && activeTypes[0] === 'yellow'
    if (onlyYellow) {
      filtered.sort((a, b) => {
        const discA = a.oldPrice > 0 ? ((a.oldPrice - a.currentPrice) / a.oldPrice) : 0
        const discB = b.oldPrice > 0 ? ((b.oldPrice - b.currentPrice) / b.oldPrice) : 0
        return discB - discA
      })
    }

    return filtered
  }, [products, typeFilters, selectedCategory])

  // Build dynamic categories from products (after type filtering)
  const categories = useMemo(() => {
    // Use same OR logic as filteredProducts
    const activeTypes = Object.entries(typeFilters).filter(([, active]) => active).map(([k]) => k)
    const productsAfterTypeFilter = products.filter(p => activeTypes.includes(p.type))
    const uniqueCategories = [...new Set(productsAfterTypeFilter.map(p => p.category))].sort()
    return [
      { id: 'all', label: '🏷️ Все' },
      ...uniqueCategories.map(cat => ({
        id: cat,
        label: `${getCategoryEmoji(cat)} ${cat}`
      }))
    ]
  }, [products, typeFilters])

  // Calculate counts for header
  const totalCount = products.length
  const countGreen = products.filter(p => p.type === 'green').length
  const countRed = products.filter(p => p.type === 'red').length
  const countYellow = products.filter(p => p.type === 'yellow').length

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
        {/* Back button */}
        <button
          onClick={() => setShowLogin(false)}
          className="header-pill header-pill-action mb-4"
        >
          ◀ Назад
        </button>
        <Login
          userId={userId}
          onLoginSuccess={() => {
            setIsAuthenticated(true)
            setShowLogin(false)
          }}
        />
      </div>
    )
  }

  return (
    <div className="min-h-screen p-4 app-container">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-6"
      >
        <h1 className="text-2xl font-bold mb-2">{headerEmoji} {headerTitle}</h1>

        {/* Controls row: Auth + Theme + Admin */}
        <div className="flex items-center justify-center gap-2 mb-3 flex-wrap">
          {isAuthenticated ? (
            <span className="header-pill header-pill-success">{'\u2705'} Авторизован</span>
          ) : (
            <button
              onClick={() => setShowLogin(true)}
              className="header-pill header-pill-action"
            >
              {'\ud83d\udd10'} Войти
            </button>
          )}
          <button
            onClick={() => setTheme(t => t === 'dark' ? 'light' : 'dark')}
            className="header-pill header-pill-action"
            aria-label="Переключить тему"
          >
            {theme === 'dark' ? '\u2600\ufe0f' : '\ud83c\udf19'}
          </button>
          <a
            href="/admin"
            target="_blank"
            rel="noreferrer"
            className="header-pill header-pill-action"
          >
            {'\ud83d\udee0\ufe0f'} Админ
          </a>
        </div>

        {/* Detailed Stats */}
        <div className="flex justify-center gap-4 text-xs mt-2 opacity-80 font-medium flex-wrap">
          <div className="flex items-center gap-1">
            <span className="text-lg">📦</span>
            <span>{totalCount}</span>
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

        {/* Green staleness warning — shown when live page count differs by more than 2 */}
        {greenLiveCount !== null && greenLiveCount > 0 && Math.abs(countGreen - greenLiveCount) > 2 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-3 px-4 py-2 rounded-xl bg-red-500/20 border border-red-500/50 text-red-400 text-center"
          >
            <div className="font-bold text-sm">⚠️ Зелёные ценники могли устареть</div>
            <div className="text-xs opacity-70 mt-0.5">
              На сайте {greenLiveCount} товаров, у нас {countGreen} — данные могли устареть
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
            className="text-xs px-3 py-1.5 rounded-full transition-all bg-blue-500/20 text-blue-400 border border-blue-500/30"
          >
            Все
          </button>
        )}

        {[
          { key: 'green', label: '🟢 Зелёные', activeClass: 'bg-green-500/50 text-green-200 border-2 border-green-400/70' },
          { key: 'red', label: '🔴 Красные', activeClass: 'bg-red-500/50 text-red-200 border-2 border-red-400/70' },
          { key: 'yellow', label: '🟡 Жёлтые', activeClass: 'bg-yellow-500/50 text-yellow-200 border-2 border-yellow-400/70' }
        ].map(({ key, label, activeClass }) => (
          <button
            key={key}
            onClick={() => {
              // Smart toggle logic:
              // 1. If ALL are selected -> Click selects ONLY that one (Radio behavior)
              // 2. If ONLY that one is selected -> Click resets to ALL (Toggle off -> All)
              // 3. Otherwise -> Standard toggle
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
                // If this would turn the last one off, reset to all
                if (!Object.values(next).some(v => v)) {
                  return { green: true, red: true, yellow: true }
                }
                return next
              })
            }}
            className={`text-xs px-3 py-1.5 rounded-full transition-all ${typeFilters[key]
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
        <AnimatePresence mode="popLayout">
          {filteredProducts.map((product, index) => (
            <ProductCard
              key={product.id}
              product={product}
              index={index}
              isFavorite={favorites.has(product.id)}
              onToggleFavorite={handleToggleFavorite}
              onAddToCart={handleAddToCart}
              favoritesLoading={favoritesLoading}
              viewMode={viewMode}
            />
          ))}
        </AnimatePresence>

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
    </div>
  )
}

export default App
