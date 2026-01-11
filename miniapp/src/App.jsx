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

function ProductCard({ product, index }) {
  const [imageLoaded, setImageLoaded] = useState(false)
  const stockColor = getStockColor(product.stock, product.unit)

  // Calculate real discount percentage
  const discount = Math.round(((parseFloat(product.oldPrice) - parseFloat(product.currentPrice)) / parseFloat(product.oldPrice)) * 100)

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
      className={`glass-card p-3 flex gap-3 ${config.bg} border-l-2 ${config.text} border-current`}
    >
      {/* Image */}
      <div className="relative w-20 h-20 flex-shrink-0 rounded-xl overflow-hidden">
        {!imageLoaded && <div className="absolute inset-0 skeleton" />}
        <img
          src={product.image}
          alt={product.name}
          className={`w-full h-full object-cover transition-opacity duration-300 ${imageLoaded ? 'opacity-100' : 'opacity-0'}`}
          onLoad={() => setImageLoaded(true)}
        />
        {/* Stock badge */}
        <div className={`absolute top-1 right-1 w-3 h-3 rounded-full ${stockColor}`} />
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2 mb-1">
          <h3 className="font-medium text-sm leading-tight line-clamp-2 flex-1">
            {product.name}
          </h3>
          <span className={`text-xs px-2 py-0.5 rounded-full ${config.bg} ${config.text} whitespace-nowrap`}>
            {config.label.split(' ')[0]}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-[var(--tg-theme-button-color)]">
            {product.currentPrice}₽
          </span>
          <span className="text-xs opacity-60 line-through">
            {product.oldPrice}₽
          </span>
          <span className="discount-badge">
            -{discount}%
          </span>
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
  const [typeFilters, setTypeFilters] = useState({
    green: true,
    red: true,
    yellow: true
  })

  useEffect(() => {
    // Load products from data.json
    fetch('./data.json')
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
        setError(err.message)
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
  const productsAfterTypeFilter = products.filter(p => typeFilters[p.type] !== false)
  const uniqueCategories = [...new Set(productsAfterTypeFilter.map(p => p.category))].sort()
  const categories = useMemo(() => [
    { id: 'all', label: '🏷️ Все' },
    ...uniqueCategories.map(cat => ({
      id: cat,
      label: `${getCategoryEmoji(cat)} ${cat}`
    }))
  ], [uniqueCategories.join(',')])

  // Total count is ALL products, not filtered
  const productCount = products.length

  // Dynamic header based on active filters
  const activeTypes = Object.entries(typeFilters).filter(([_, active]) => active).map(([type]) => type)
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
        <p className="text-sm opacity-60">
          {filteredProducts.length} из {productCount} товаров
        </p>
      </motion.div>

      {/* Type Filter Toggles */}
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 0.15 }}
        className="flex gap-2 mb-3 justify-center"
      >
        {[
          { key: 'green', label: '🟢 Зелёные', color: 'green' },
          { key: 'red', label: '🔴 Красная книга', color: 'red' },
          { key: 'yellow', label: '🟡 Жёлтые', color: 'yellow' }
        ].map(({ key, label, color }) => (
          <button
            key={key}
            onClick={() => setTypeFilters(prev => ({ ...prev, [key]: !prev[key] }))}
            className={`text-xs px-3 py-1.5 rounded-full transition-all ${typeFilters[key]
              ? `bg-${color}-500/30 text-${color}-300 border border-${color}-400/50`
              : 'bg-gray-700/30 text-gray-500 border border-gray-600/30'
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
              key={product.name}
              product={product}
              index={index}
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
