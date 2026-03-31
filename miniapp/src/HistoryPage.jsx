import { useState, useEffect, useCallback, useRef, memo } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { getAuthHeaders } from './api'

const API_BASE = '/api'

// Sale type colors
const TYPE_COLORS = {
  green: { bg: 'rgba(34, 197, 94, 0.15)', border: 'rgba(34, 197, 94, 0.4)', text: '#4ade80', dot: '#22c55e' },
  red: { bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.4)', text: '#f87171', dot: '#ef4444' },
  yellow: { bg: 'rgba(234, 179, 8, 0.15)', border: 'rgba(234, 179, 8, 0.4)', text: '#fbbf24', dot: '#eab308' },
}

// Format relative time in Russian
function timeAgo(dateStr) {
  if (!dateStr) return null
  const diff = Date.now() - new Date(dateStr).getTime()
  const mins = Math.floor(diff / 60000)
  if (mins < 1) return 'только что'
  if (mins < 60) return `${mins} мин назад`
  const hours = Math.floor(mins / 60)
  if (hours < 24) return `${hours} ч назад`
  const days = Math.floor(hours / 24)
  if (days === 1) return 'вчера'
  if (days < 7) return `${days} дн назад`
  return new Date(dateStr).toLocaleDateString('ru-RU', { day: 'numeric', month: 'short' })
}

// History card for the list
const HistoryCard = memo(function HistoryCard({ product, onClick }) {
  const typeColor = TYPE_COLORS[product.last_sale_type] || TYPE_COLORS.green
  const hasSales = product.total_sale_count > 0
  const isGhost = !hasSales && !product.is_currently_on_sale

  return (
    <motion.div
      className={`history-card ${isGhost ? 'history-card-ghost' : ''}`}
      onClick={() => onClick(product)}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      style={hasSales ? { borderLeft: `3px solid ${typeColor.dot}` } : {}}
    >
      {/* Product image */}
      <div className="history-card-img-wrap">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt=""
            className="history-card-img"
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="history-card-img-placeholder">📦</div>
        )}
        {product.is_currently_on_sale && (
          <span className="history-card-live-badge">● LIVE</span>
        )}
      </div>

      {/* Card body */}
      <div className="history-card-body">
        <div className="history-card-name">{product.name}</div>

        {hasSales ? (
          <>
            {/* Stats row */}
            <div className="history-card-stats">
              <span className="history-card-stat">
                🔄 {product.total_sale_count}×
              </span>
              {product.avg_discount_pct > 0 && (
                <span className="history-card-stat">
                  💰 -{Math.round(product.avg_discount_pct)}%
                </span>
              )}
              {product.avg_window_min > 0 && (
                <span className="history-card-stat">
                  ⏱ {Math.round(product.avg_window_min)}м
                </span>
              )}
            </div>

            {/* Last sale + usual time */}
            <div className="history-card-meta">
              {product.last_sale_at && (
                <span style={{ color: typeColor.text }}>
                  {timeAgo(product.last_sale_at)}
                </span>
              )}
              {product.usual_time && (
                <span style={{ opacity: 0.5 }}>
                  обычно в {product.usual_time}
                </span>
              )}
            </div>

            {/* Price */}
            {product.last_known_price > 0 && (
              <div className="history-card-price">
                {product.last_known_price}₽
              </div>
            )}
          </>
        ) : (
          <div className="history-card-no-sales">Ещё не было на скидке</div>
        )}
      </div>
    </motion.div>
  )
})

// Filter chips
const FILTERS = [
  { id: 'all', label: '🔍 Все', color: null },
  { id: 'green', label: '💚 Зелёные', color: '#22c55e' },
  { id: 'red', label: '🔴 Красные', color: '#ef4444' },
  { id: 'yellow', label: '🟡 Жёлтые', color: '#eab308' },
]

const SORTS = [
  { id: 'last_seen', label: 'Недавние' },
  { id: 'most_frequent', label: 'Частые' },
  { id: 'alphabetical', label: 'А-Я' },
]

export default function HistoryPage({ onBack, onOpenDetail }) {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState('last_seen')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [total, setTotal] = useState(0)
  const searchTimeout = useRef(null)
  const listRef = useRef(null)

  const fetchProducts = useCallback(async (pageNum = 1, append = false) => {
    if (pageNum === 1) setLoading(true)
    else setLoadingMore(true)

    try {
      const params = new URLSearchParams({
        page: String(pageNum),
        per_page: '50',
        sort,
      })
      if (search) params.set('search', search)
      if (filter && filter !== 'all') params.set('filter', filter)

      const res = await fetch(`${API_BASE}/history/products?${params}`, {
        headers: getAuthHeaders(),
      })
      const data = await res.json()

      if (append) {
        setProducts(prev => [...prev, ...data.products])
      } else {
        setProducts(data.products || [])
      }
      setTotalPages(data.pages || 0)
      setTotal(data.total || 0)
      setPage(pageNum)
    } catch (err) {
      console.error('History fetch error:', err)
    } finally {
      setLoading(false)
      setLoadingMore(false)
    }
  }, [search, filter, sort])

  // Initial load + refetch on filter/sort/search change
  useEffect(() => {
    fetchProducts(1, false)
  }, [fetchProducts])

  // Debounced search
  const handleSearchChange = (e) => {
    const val = e.target.value
    setSearch(val)
  }

  // Infinite scroll
  const handleScroll = useCallback(() => {
    if (loadingMore || page >= totalPages) return
    const el = listRef.current
    if (!el) return
    // Check if near bottom of page
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 400) {
      fetchProducts(page + 1, true)
    }
  }, [loadingMore, page, totalPages, fetchProducts])

  useEffect(() => {
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [handleScroll])

  return (
    <div className="history-page">
      {/* Header */}
      <div className="history-header">
        <div className="history-header-top">
          <button className="history-back-btn" onClick={onBack}>
            ← Назад
          </button>
          <h1 className="history-title">📊 История скидок</h1>
          <div className="history-total">
            {total > 0 && <span>{total.toLocaleString()} товаров</span>}
          </div>
        </div>

        {/* Search */}
        <div className="history-search-wrap">
          <input
            type="text"
            className="history-search"
            placeholder="Поиск по названию..."
            value={search}
            onChange={handleSearchChange}
          />
          {search && (
            <button className="history-search-clear" onClick={() => setSearch('')}>
              ✕
            </button>
          )}
        </div>

        {/* Filter chips */}
        <div className="history-filters">
          <div className="history-filter-chips">
            {FILTERS.map(f => (
              <button
                key={f.id}
                className={`history-chip ${filter === f.id ? 'active' : ''}`}
                onClick={() => setFilter(f.id)}
                style={filter === f.id && f.color ? {
                  background: f.color + '33',
                  borderColor: f.color + '66',
                  color: f.color
                } : {}}
              >
                {f.label}
              </button>
            ))}
          </div>

          {/* Sort */}
          <div className="history-sort">
            {SORTS.map(s => (
              <button
                key={s.id}
                className={`history-sort-btn ${sort === s.id ? 'active' : ''}`}
                onClick={() => setSort(s.id)}
              >
                {s.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Product list */}
      <div className="history-list" ref={listRef}>
        {loading ? (
          <div className="history-loading">
            {[...Array(8)].map((_, i) => (
              <div key={i} className="history-skeleton" />
            ))}
          </div>
        ) : products.length === 0 ? (
          <div className="history-empty">
            <div style={{ fontSize: 48, marginBottom: 12 }}>🔍</div>
            <div>Ничего не найдено</div>
            {search && (
              <button
                className="history-chip active"
                onClick={() => setSearch('')}
                style={{ marginTop: 12 }}
              >
                Сбросить поиск
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="history-grid">
              {products.map((p, i) => (
                <HistoryCard
                  key={p.id}
                  product={p}
                  onClick={() => onOpenDetail(p.id)}
                />
              ))}
            </div>

            {/* Load more indicator */}
            {loadingMore && (
              <div className="history-loading-more">
                Загрузка...
              </div>
            )}

            {page >= totalPages && products.length > 0 && (
              <div className="history-end">
                Показано {products.length} из {total}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
