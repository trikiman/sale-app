import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import './index.css'

const CATEGORIES = [
  { id: 'all', label: '🏷️ Все', emoji: '🏷️' },
  { id: 'fruits', label: '🍎 Фрукты', emoji: '🍎' },
  { id: 'vegetables', label: '🥬 Овощи', emoji: '🥬' },
  { id: 'salads', label: '🥗 Салаты', emoji: '🥗' },
  { id: 'seafood', label: '🐟 Морепродукты', emoji: '🐟' },
  { id: 'meat', label: '🥩 Мясо', emoji: '🥩' },
  { id: 'dairy', label: '🥛 Молочка', emoji: '🥛' },
  { id: 'other', label: '📦 Другое', emoji: '📦' },
]

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

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      transition={{ duration: 0.3, delay: index * 0.05 }}
      className="glass-card p-3 flex gap-3"
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
        <h3 className="font-medium text-sm leading-tight line-clamp-2 mb-1">
          {product.name}
        </h3>
        <div className="flex items-center gap-2">
          <span className="text-lg font-bold text-[var(--tg-theme-button-color)]">
            {product.currentPrice}₽
          </span>
          <span className="text-xs opacity-60 line-through">
            {product.oldPrice}₽
          </span>
          <span className="discount-badge">
            -40%
          </span>
        </div>
        <p className="text-xs opacity-60 mt-1">
          📦 {product.stock} {product.unit}
        </p>
      </div>
    </motion.div>
  )
}

function CategoryFilter({ selected, onSelect }) {
  return (
    <div className="flex gap-2 overflow-x-auto pb-2 px-4 -mx-4 scrollbar-hide">
      {CATEGORIES.map((cat) => (
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

  useEffect(() => {
    // Load products from data.json
    fetch('./data.json')
      .then(res => {
        if (!res.ok) throw new Error('Failed to load data')
        return res.json()
      })
      .then(data => {
        if (Array.isArray(data) && data.length > 0) {
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

  const filteredProducts = selectedCategory === 'all'
    ? products
    : products.filter(p => p.category === selectedCategory)

  // Total count is ALL products, not filtered
  const productCount = products.length

  return (
    <div className="min-h-screen p-4">
      {/* Header */}
      <motion.div
        initial={{ opacity: 0, y: -20 }}
        animate={{ opacity: 1, y: 0 }}
        className="text-center mb-6"
      >
        <h1 className="text-2xl font-bold mb-1">🟢 Зелёные ценники</h1>
        <p className="text-sm opacity-60">
          {productCount} товаров со скидкой -40%
        </p>
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
        Обновлено: {new Date().toLocaleTimeString('ru-RU', { hour: '2-digit', minute: '2-digit' })}
      </motion.div>
    </div>
  )
}

export default App
