import { useState, useEffect, useCallback, useRef, memo } from 'react'
import { motion } from 'framer-motion'
import { getAuthHeaders } from './api'

const API_BASE = '/api'

const TYPE_COLORS = {
  green: { bg: 'rgba(34, 197, 94, 0.08)', border: 'rgba(34, 197, 94, 0.25)', text: '#4ade80', dot: '#22c55e', badge: 'rgba(34, 197, 94, 0.9)' },
  red: { bg: 'rgba(239, 68, 68, 0.08)', border: 'rgba(239, 68, 68, 0.25)', text: '#f87171', dot: '#ef4444', badge: 'rgba(239, 68, 68, 0.9)' },
  yellow: { bg: 'rgba(234, 179, 8, 0.08)', border: 'rgba(234, 179, 8, 0.25)', text: '#fbbf24', dot: '#eab308', badge: 'rgba(234, 179, 8, 0.9)' },
}

const DAY_LABELS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']

// 7-day mini timeline bar
function MiniTimeline({ dayPattern, saleType }) {
  const color = TYPE_COLORS[saleType] || TYPE_COLORS.green
  return (
    <div className="hcard-timeline">
      <div className="hcard-timeline-label">Последние 7 дней</div>
      <div className="hcard-timeline-row">
        {DAY_LABELS.map((day, i) => {
          const prob = dayPattern ? (dayPattern[String(i)] || 0) : 0
          const hasData = prob > 0
          return (
            <div key={i} className="hcard-timeline-col">
              <div className="hcard-timeline-day">{day}</div>
              <div
                className={`hcard-timeline-bar ${hasData ? '' : 'empty'}`}
                style={hasData ? { background: color.dot, opacity: 0.3 + prob * 0.7 } : {}}
              />
            </div>
          )
        })}
      </div>
    </div>
  )
}

// Confidence dots
function ConfidenceDots({ level }) {
  const colors = level === 'high' ? ['#22c55e', '#22c55e', '#22c55e'] :
    level === 'medium' ? ['#eab308', '#eab308', 'rgba(255,255,255,0.15)'] :
      ['#ef4444', 'rgba(255,255,255,0.15)', 'rgba(255,255,255,0.15)']
  return (
    <span className="hcard-dots">
      {colors.map((c, i) => <span key={i} className="hcard-dot" style={{ background: c }} />)}
    </span>
  )
}

// History card — vertical layout matching mockup
const HistoryCard = memo(function HistoryCard({ product, onClick, isFavorite, onToggleFavorite }) {
  const type = product.last_sale_type || 'green'
  const tc = TYPE_COLORS[type] || TYPE_COLORS.green
  const hasSales = product.total_sale_count > 0
  const isGhost = !hasSales && !product.is_currently_on_sale

  const handleFavClick = (e) => {
    e.stopPropagation()
    if (onToggleFavorite) onToggleFavorite(product)
  }

  return (
    <motion.div
      className={`hcard ${isGhost ? 'hcard-ghost' : ''}`}
      onClick={() => onClick(product)}
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -3, boxShadow: '0 8px 28px rgba(0,0,0,0.25)' }}
      style={hasSales ? {
        background: tc.bg,
        borderColor: tc.border,
      } : {}}
    >
      {/* Image section */}
      <div className="hcard-image-wrap">
        {product.image_url ? (
          <img
            src={product.image_url}
            alt=""
            className="hcard-img"
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <div className="hcard-img-placeholder">📦</div>
        )}

        {/* Type badge — top left */}
        {hasSales && product.avg_discount_pct > 0 && (
          <span className="hcard-type-badge" style={{ background: tc.badge }}>
            {type === 'green' ? 'Green' : type === 'red' ? 'Red' : 'Yellow'} {Math.round(product.avg_discount_pct)}%
          </span>
        )}

        {/* Favorite heart — top right */}
        <button
          className={`hcard-fav-btn ${isFavorite ? 'active' : ''}`}
          onClick={handleFavClick}
          aria-label={isFavorite ? 'Remove from favorites' : 'Add to favorites'}
        >
          {isFavorite ? '❤️' : '🤍'}
        </button>

        {/* Live indicator */}
        {product.is_currently_on_sale && (
          <span className="hcard-live-dot" style={isFavorite ? { top: 36 } : {}}>●</span>
        )}
      </div>

      {/* Info section */}
      <div className="hcard-body">
        <div className="hcard-name">{product.name}</div>

        {hasSales ? (
          <>
            {/* Price row */}
            <div className="hcard-price-row">
              <span className="hcard-price" style={{ color: tc.text }}>
                {product.last_known_price > 0 ? `${product.last_known_price} ₽` : ''}
              </span>
              {product.last_old_price > 0 && (
                <span className="hcard-old-price">{product.last_old_price} ₽</span>
              )}
            </div>

            {/* Stats */}
            <div className="hcard-stats">
              <span>🔥 {product.total_sale_count}×</span>
              {product.avg_window_min > 0 && (
                <span>⏱ {Math.round(product.avg_window_min)}м</span>
              )}
            </div>

            {/* 7-day mini timeline */}
            <MiniTimeline dayPattern={product.day_pattern} saleType={type} />

            {/* Prediction */}
            {product.usual_time && (
              <div className="hcard-prediction">
                <span>🔮 обычно ~{product.usual_time}</span>
                <ConfidenceDots level={product.confidence || 'low'} />
              </div>
            )}
          </>
        ) : (
          <div className="hcard-no-data">
            <span style={{ opacity: 0.4 }}>📊 Нет данных</span>
          </div>
        )}
      </div>
    </motion.div>
  )
}, (prev, next) =>
  prev.product === next.product &&
  prev.isFavorite === next.isFavorite
)

// Filter chips — full set from mockup
const FILTERS = [
  { id: 'all', label: '🔍 Все', color: null },
  { id: 'green', label: '🟢 Green', color: '#22c55e' },
  { id: 'red', label: '🔴 Red', color: '#ef4444' },
  { id: 'yellow', label: '🟡 Yellow', color: '#eab308' },
  { id: 'favorites', label: '⭐ Избранное', color: '#f97316' },
  { id: 'predicted_soon', label: '🔮 Скоро', color: '#818cf8' },
]

const SORTS = [
  { id: 'last_seen', label: 'Недавние' },
  { id: 'most_frequent', label: 'Частые' },
  { id: 'alphabetical', label: 'А-Я' },
]

export default function HistoryPage({ onBack, onOpenDetail, favorites = new Set(), onToggleFavorite, userId }) {
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadingMore, setLoadingMore] = useState(false)
  const [searchInput, setSearchInput] = useState('')
  const [search, setSearch] = useState('')
  const [filter, setFilter] = useState('all')
  const [sort, setSort] = useState('last_seen')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [total, setTotal] = useState(0)
  const searchTimeout = useRef(null)
  const listRef = useRef(null)

  // For client-side favorites filtering
  const isClientFilter = filter === 'favorites'

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
      // Only send server-side filters (not favorites — that's client-side)
      if (filter && filter !== 'all' && filter !== 'favorites') {
        params.set('filter', filter)
      }

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

  useEffect(() => {
    fetchProducts(1, false)
  }, [fetchProducts])

  // Debounced search
  const handleSearchChange = (e) => {
    const val = e.target.value
    setSearchInput(val)
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
    searchTimeout.current = setTimeout(() => setSearch(val), 300)
  }

  const clearSearch = () => {
    setSearchInput('')
    setSearch('')
    if (searchTimeout.current) clearTimeout(searchTimeout.current)
  }

  // Infinite scroll
  const handleScroll = useCallback(() => {
    if (loadingMore || page >= totalPages) return
    if (window.innerHeight + window.scrollY >= document.body.offsetHeight - 400) {
      fetchProducts(page + 1, true)
    }
  }, [loadingMore, page, totalPages, fetchProducts])

  useEffect(() => {
    window.addEventListener('scroll', handleScroll, { passive: true })
    return () => window.removeEventListener('scroll', handleScroll)
  }, [handleScroll])

  // Apply client-side favorites filter
  const displayProducts = isClientFilter
    ? products.filter(p => favorites.has(p.id))
    : products

  return (
    <div className="history-page">
      {/* Header */}
      <div className="history-header">
        <div className="history-header-top">
          <button className="history-back-btn" onClick={onBack}>← Назад</button>
          <h1 className="history-title">📊 Sale History</h1>
          <div className="history-total">
            {total > 0 && <span>{total.toLocaleString()} товаров</span>}
          </div>
        </div>

        {/* Search */}
        <div className="history-search-wrap">
          <span className="history-search-icon">🔍</span>
          <input
            type="text"
            className="history-search"
            placeholder="Поиск по товарам и категориям..."
            value={searchInput}
            onChange={handleSearchChange}
          />
          {searchInput && (
            <button className="history-search-clear" onClick={clearSearch}>✕</button>
          )}
        </div>

        {/* Filters + sort */}
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
                {f.id === 'favorites' && favorites.size > 0 && (
                  <span className="history-chip-count">{favorites.size}</span>
                )}
              </button>
            ))}
          </div>
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

      {/* Product grid */}
      <div className="history-list" ref={listRef}>
        {loading ? (
          <div className="hcard-grid">
            {[...Array(6)].map((_, i) => (
              <div key={i} className="hcard-skeleton" />
            ))}
          </div>
        ) : displayProducts.length === 0 ? (
          <div className="history-empty">
            <div style={{ fontSize: 48, marginBottom: 12 }}>
              {filter === 'favorites' ? '⭐' : '🔍'}
            </div>
            <div>
              {filter === 'favorites'
                ? 'Нет избранных товаров'
                : 'Ничего не найдено'}
            </div>
            {(searchInput || filter !== 'all') && (
              <button
                className="history-chip active"
                onClick={() => { clearSearch(); setFilter('all') }}
                style={{ marginTop: 12 }}
              >
                Сбросить фильтры
              </button>
            )}
          </div>
        ) : (
          <>
            <div className="hcard-grid">
              {displayProducts.map(p => (
                <HistoryCard
                  key={p.id}
                  product={p}
                  onClick={() => onOpenDetail(p.id)}
                  isFavorite={favorites.has(p.id)}
                  onToggleFavorite={onToggleFavorite}
                />
              ))}
            </div>

            {loadingMore && (
              <div className="history-loading-more">Загрузка...</div>
            )}

            {page >= totalPages && displayProducts.length > 0 && (
              <div className="history-end">
                Показано {displayProducts.length} из {total}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  )
}
