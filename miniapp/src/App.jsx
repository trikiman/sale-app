import { useState, useEffect, useMemo } from 'react'
// eslint-disable-next-line no-unused-vars
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
  'Другое': '📦',
}

function getCategoryEmoji(category) {
  return CATEGORY_EMOJIS[category] || '📦'
}

function getStockColor(stock, unit) {
  const value = parseFloat(stock)
  if (unit === 'кг') {
    if (value <= 1) return 'stock-red'
    if (value <= 3) return 'stock-orange'
    if (value <= 5) return 'stock-yellow'
    return 'stock-green'
  } else {
    if (value <= 1) return 'stock-red'
    if (value <= 3) return 'stock-orange'
    if (value <= 5) return 'stock-yellow'
    return 'stock-green'
  }
}

function ProductCard({ product, index, isFavorite, onToggleFavorite }) {
  const [imageLoaded, setImageLoaded] = useState(false)
  const stockColor = getStockColor(product.stock, product.unit)

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
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className={`glass-card p-3 flex gap-3 ${config.bg} border-l-2 ${config.text} border-current relative group`}
    >
      {/* Favorite Button */}
      <button
        onClick={(e) => {
          e.stopPropagation()
          onToggleFavorite(product)
        }}
        className={`absolute top-2 right-2 z-10 p-2 rounded-full backdrop-blur-sm transition-all ${
          isFavorite ? 'bg-red-500/20 text-red-500 scale-110' : 'bg-black/20 text-white/50 hover:bg-black/40'
        }`}
      >
        {isFavorite ? '❤️' : '🤍'}
      </button>

      {/* Image */}
      <div className="relative w-20 h-20 flex-shrink-0 rounded-xl overflow-hidden bg-gray-100 dark:bg-gray-800">
        {!imageLoaded && product.image && <div className="absolute inset-0 skeleton" />}

        {product.image ? (
          <img
            src={product.image}
            alt={product.name}
            className={`w-full h-full object-cover transition-opacity duration-300 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
            onLoad={() => setImageLoaded(true)}
            onError={(e) => {
              e.target.style.display = 'none';
              e.target.parentElement.classList.add('flex', 'items-center', 'justify-center');
              e.target.parentElement.innerHTML = `<span class="text-3xl">${getCategoryEmoji(product.category)}</span>`;
            }}
          />
        ) : (
          <div className="w-full h-full flex items-center justify-center">
            <span className="text-3xl">{getCategoryEmoji(product.category)}</span>
          </div>
        )}

        {/* Stock badge */}
        <div className={`absolute top-1 left-1 w-3 h-3 rounded-full ${stockColor}`} />
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
          📦 {product.stock} {product.unit}
        </p>
      </div>
    </motion.div>
  )
}

function CategoryFilter({ selected, onSelect, categories }) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2 px-4 -mx-4 scrollbar-hide">
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
  )
}

function App() {
  const [products, setProducts] = useState([])
  const [selectedCategory, setSelectedCategory] = useState('all')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [updatedAt, setUpdatedAt] = useState(null)
  const [favorites, setFavorites] = useState(new Set())
  const [userId] = useState(() => {
    // Get user ID from Telegram if available
    return window.Telegram?.WebApp?.initDataUnsafe?.user?.id || 1
  })
  const [typeFilters, setTypeFilters] = useState({
    green: true,
    red: true,
    yellow: true
  })

  useEffect(() => {
    // Load favorites
    fetch(`/api/favorites/${userId}`)
      .then(res => res.json())
      .then(data => {
        if (data.favorites) {
          setFavorites(new Set(data.favorites.map(f => f.product_id)))
        }
      })
      .catch(err => console.error('Failed to load favorites:', err))
  }, [userId])

  const handleToggleFavorite = async (product) => {
    const isFav = favorites.has(product.id)
    const newFavorites = new Set(favorites)

    // Optimistic update
    if (isFav) {
      newFavorites.delete(product.id)
    } else {
      newFavorites.add(product.id)
    }
    setFavorites(newFavorites)

    try {
      if (isFav) {
        // Remove
        await fetch(`/api/favorites/${userId}/${product.id}`, {
          method: 'DELETE'
        })
      } else {
        // Add
        await fetch(`/api/favorites/${userId}`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          },
          body: JSON.stringify({
            product_id: product.id,
            product_name: product.name
          })
        })
      }
    } catch (err) {
      console.error('Failed to toggle favorite:', err)
      // Revert on error
      if (isFav) {
        newFavorites.add(product.id)
      } else {
        newFavorites.delete(product.id)
      }
      setFavorites(newFavorites)
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

  // Apply both category and type filters
  const filteredProducts = products.filter(p => {
    const categoryMatch = selectedCategory === 'all' || p.category === selectedCategory
    const typeMatch = typeFilters[p.type] !== false
    return categoryMatch && typeMatch
  })

  // Build dynamic categories from products (after type filtering)
  const categories = useMemo(() => {
    const productsAfterTypeFilter = products.filter(p => typeFilters[p.type] !== false)
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
      headerTitle = 'Красная книга'
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
    <div className="min-h-screen p-4">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-6"
      >
        <h1 className="text-2xl font-bold mb-1">{headerEmoji} {headerTitle}</h1>

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
      </motion.div>

      {/* Type Filter Toggles */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
        className="flex gap-2 mb-3 justify-center"
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
          { key: 'green', label: '🟢 Зелёные', color: 'green' },
          { key: 'red', label: '🔴 Красная', color: 'red' },
          { key: 'yellow', label: '🟡 Жёлтые', color: 'yellow' }
        ].map(({ key, label, color }) => (
          <button
            key={key}
            onClick={() => {
              // Smart toggle:
              // If user clicks a filter, and it was the ONLY one active, turn everything ON (reset)
              // If user clicks a filter and others are active, toggle it
              // If user clicks a filter that was OFF, turn it ON

              // Actually simple toggle is best, but let's prevent ALL from being off
              setTypeFilters(prev => {
                const next = { ...prev, [key]: !prev[key] }
                // If all would be off, turn just this one on (radio behavior effectively)
                if (!Object.values(next).some(v => v)) {
                   return { green: false, red: false, yellow: false, [key]: true }
                }
                return next
              })
            }}
            className={`text-xs px-3 py-1.5 rounded-full transition-all ${typeFilters[key]
              ? `bg-${color}-500/30 text-${color}-300 border border-${color}-400/50`
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

      {/* Footer */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.5 }}
        className="text-center mt-8 pb-4 text-xs opacity-40"
      >
        Обновлено: {updatedAt ? new Date(updatedAt).toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' }) : '---'}
      </motion.div>
    </div>
  )
}

export default App
