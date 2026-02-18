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

function getCategoryEmoji(category) {
  // Simple partial match for categories not in the exact map
  if (CATEGORY_EMOJIS[category]) return CATEGORY_EMOJIS[category]
  if (category.includes('Сладости')) return CATEGORY_EMOJIS['Сладости']
  if (category.includes('Хлеб')) return CATEGORY_EMOJIS['Хлеб']
  return '📦'
}

function ProductCard({ product, index, isFavorite, onToggleFavorite, favoritesLoading }) {
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
    green: { bg: 'bg-green-500/20', text: 'text-green-400', label: '🟢 Зелёная' },
    red: { bg: 'bg-red-500/20', text: 'text-red-400', label: '🔴 Красная' },
    yellow: { bg: 'bg-yellow-500/20', text: 'text-yellow-400', label: '🟡 Жёлтая' }
  }
  const config = typeConfig[product.type] || typeConfig.green

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3, delay: Math.min(index * 0.05, 0.5) }}
      className={`glass-card p-3 flex gap-3 ${config.bg} border-l-2 ${config.text} border-current relative group`}
    >
      {/* Favorite Button */}
      <motion.button
        whileTap={{ scale: 0.8 }}
        onClick={(e) => {
          e.stopPropagation()
          if (!favoritesLoading) onToggleFavorite(product)
        }}
        disabled={favoritesLoading}
        className={`absolute top-2 right-2 z-10 p-2 rounded-full backdrop-blur-sm transition-all flex items-center justify-center ${isFavorite ? 'bg-red-500/20 text-red-500 scale-110' : 'bg-black/40 text-white hover:bg-black/60'
          } ${favoritesLoading ? 'opacity-70 cursor-wait' : ''}`}
      >
        {favoritesLoading ? (
          <div className="w-5 h-5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
        ) : (
          isFavorite ? '❤️' : '🤍'
        )}
      </motion.button>

      {/* Image */}
      <div className="relative w-20 h-20 flex-shrink-0 rounded-xl overflow-hidden bg-gray-100 dark:bg-gray-800">
        {!imageLoaded && !imageError && product.image && <div className="absolute inset-0 skeleton" />}

        {product.image && !imageError ? (
          <img
            src={product.image}
            alt={product.name}
            className={`w-full h-full object-cover transition-opacity duration-300 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
            onLoad={() => setImageLoaded(true)}
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center bg-gray-200/50">
            <span className="text-3xl">{getCategoryEmoji(product.category)}</span>
          </div>
        )}

        {/* Stock badge removed to avoid confusion with type colors (Bug #7) */}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1 pr-8">
          <h3 className="font-medium text-sm leading-tight line-clamp-2 flex-1">
            {product.name}
          </h3>
        </div>
        <div className="flex items-center gap-2 mb-1">
          <span className={`text-xs px-2 py-0.5 rounded-full ${config.bg} ${config.text} whitespace-nowrap`}>
            {config.label.split(' ')[0]}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-[var(--tg-theme-button-color)]">
            {product.currentPrice}₽
          </span>
          {hasDiscount && (
            <>
              <span className="text-xs opacity-60 line-through">
                {product.oldPrice}₽
              </span>
              <span className="discount-badge">
                -{discount}%
              </span>
            </>
          )}
        </div>
        <p className="text-xs opacity-60 mt-1">
          {product.stock !== 99 && (
            <>📦 {product.stock} {product.unit}</>
          )}
        </p>
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
  const [scraperRunning, setScraperRunning] = useState(false)
  const [scraperDone, setScraperDone] = useState(false)

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
        } else if (Array.isArray(data) && data.length > 0) {
          setProducts(data)
        } else {
          setError('No products found')
        }
      })
      .catch(err => {
        console.error('API Error:', err)
        // Fallback to static file if API fails
        fetch('./data.json')
          .then(res => res.json())
          .then(data => {
            if (data.products) {
              setProducts(data.products)
              setUpdatedAt(data.updatedAt)
              if (data.greenLiveCount !== undefined) setGreenLiveCount(data.greenLiveCount)
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

  // Apply both category and type filters (memoized for performance)
  const filteredProducts = useMemo(() => {
    const activeTypes = Object.entries(typeFilters)
      .filter(([, active]) => active)
      .map(([k]) => k)

    return products.filter(p => {
      const categoryMatch = selectedCategory === 'all' || p.category === selectedCategory
      const typeMatch = activeTypes.includes(p.type)
      return categoryMatch && typeMatch
    })
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

  return (
    <div className="min-h-screen p-4 max-w-lg mx-auto">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-6"
      >
        <h1 className="text-2xl font-bold mb-1">{headerEmoji} {headerTitle}</h1>

        {/* Updated At */}
        <div className="text-center text-xs opacity-60 mb-2">
          Обновлено: {updatedAt ? new Date(updatedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : '---'}
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

        {/* Green staleness warning — shown when live page count differs by more than 2 */}
        {greenLiveCount !== null && greenLiveCount > 0 && Math.abs(countGreen - greenLiveCount) > 2 && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            className="mt-3 px-4 py-2 rounded-xl bg-red-500/20 border border-red-500/50 text-red-400 text-center"
          >
            <div className="font-bold text-sm">⚠️ ЗЕЛЁНЫЕ ЦЕННИКИ УСТАРЕЛИ</div>
            <div className="text-xs opacity-70 mt-0.5">
              На сайте {greenLiveCount} товаров, у нас {countGreen} — данные могли устареть
            </div>
            {scraperDone ? (
              <div className="mt-2 text-xs text-green-400 font-medium">
                ✅ Скрапер запущен — обновите страницу через ~2 мин
              </div>
            ) : (
              <motion.button
                whileTap={{ scale: 0.95 }}
                disabled={scraperRunning}
                onClick={() => {
                  const adminToken = localStorage.getItem('vv_admin_token') ||
                    prompt('Введите admin token для запуска скрапера:')
                  if (!adminToken) return
                  localStorage.setItem('vv_admin_token', adminToken)
                  setScraperRunning(true)
                  fetch('/api/admin/run/green', {
                    method: 'POST',
                    headers: { 'X-Admin-Token': adminToken }
                  })
                    .then(r => {
                      if (r.status === 403) {
                        localStorage.removeItem('vv_admin_token')
                        alert('Неверный токен')
                        setScraperRunning(false)
                        return
                      }
                      return r.json()
                    })
                    .then(data => {
                      if (data) {
                        setScraperRunning(false)
                        setScraperDone(true)
                      }
                    })
                    .catch(() => setScraperRunning(false))
                }}
                className={`mt-2 px-4 py-1.5 rounded-lg text-xs font-bold border transition-all ${
                  scraperRunning
                    ? 'bg-red-500/10 border-red-500/30 opacity-60 cursor-wait'
                    : 'bg-red-500/30 border-red-500/50 hover:bg-red-500/40 cursor-pointer'
                }`}
              >
                {scraperRunning ? '⏳ Запускается...' : '🔄 Обновить зелёные'}
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
        className="flex gap-2 mb-3 justify-center relative z-20"
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
          { key: 'green', label: '🟢 Зелёные', activeClass: 'bg-green-500/30 text-green-300 border border-green-400/50' },
          { key: 'red', label: '🔴 Красные', activeClass: 'bg-red-500/30 text-red-300 border border-red-400/50' },
          { key: 'yellow', label: '🟡 Жёлтые', activeClass: 'bg-yellow-500/30 text-yellow-300 border border-yellow-400/50' }
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
          Загрузка...
        </div>
      )}

      {/* Error state */}
      {error && (
        <div className="text-center py-8 text-red-400">
          Ошибка: {error}
        </div>
      )}

      {/* Product List */}
      <div className="space-y-3">
        <AnimatePresence mode="popLayout">
          {filteredProducts.map((product, index) => (
            <ProductCard
              key={product.id}
              product={product}
              index={index}
              isFavorite={favorites.has(product.id)}
              onToggleFavorite={handleToggleFavorite}
              favoritesLoading={favoritesLoading}
            />
          ))}
        </AnimatePresence>

        {filteredProducts.length === 0 && !loading && !error && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            className="text-center py-8 opacity-60"
          >
            Нет товаров в этой категории
          </motion.div>
        )}
      </div>

      {/* Footer removed as moved to header */}
    </div>
  )
}

export default App
