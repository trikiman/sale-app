import { useState, useEffect, useCallback, useRef, useMemo, memo } from 'react'

import { getAuthHeaders } from './api'

const API_BASE = '/api'

// Category emoji map (shared with App.jsx)
const CATEGORY_EMOJI = {
  'Хлеб, хлебные изделия': '🥖', 'Хлеб и выпечка': '🥖',
  'Молоко, молочные продукты': '🥛', 'Молочные продукты': '🥛',
  'Овощи, фрукты, ягоды, зелень': '🥬', 'Овощи и фрукты': '🥬',
  'Мясо, птица': '🥩', 'Рыба, икра и морепродукты': '🐟',
  'Готовая еда': '🍱', 'Сладости и десерты': '🍰',
  'Напитки': '🥤', 'Сыры': '🧀',
  'Замороженные продукты': '🧊', 'Масло, соусы, специи': '🫒',
  'Консервация': '🥫', 'Снеки и орехи': '🥜',
  'Особое питание': '🌿', 'Чай и кофе': '☕',
  'Товары для дома и кухни': '🏠', 'Товары для детей': '👶',
  'Кафе': '☕', 'Новинки': '✨',
}
const getCategoryEmoji = (c) => CATEGORY_EMOJI[c] || '📦'

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
    <div
      className={`hcard ${isGhost ? 'hcard-ghost' : ''} anim-fade`}
      onClick={() => onClick(product)}
      style={{ cursor: 'pointer', transition: 'transform 0.2s, box-shadow 0.2s', ...(hasSales ? { background: tc.bg, borderColor: tc.border } : {}) }}
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
    </div>
  )
}, (prev, next) =>
  prev.product === next.product &&
  prev.isFavorite === next.isFavorite
)

// Filter chips — type filters are multi-selectable, special filters are exclusive
const TYPE_FILTERS = ['green', 'red', 'yellow']
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
  // Multi-select: Set of active type filters; empty = all. Special filters stored separately.
  const [activeTypes, setActiveTypes] = useState(new Set())
  const [specialFilter, setSpecialFilter] = useState(null) // 'favorites' | 'predicted_soon' | null
  const [sort, setSort] = useState('last_seen')
  const [page, setPage] = useState(1)
  const [totalPages, setTotalPages] = useState(0)
  const [total, setTotal] = useState(0)
  const searchTimeout = useRef(null)
  const listRef = useRef(null)

  // v1.7: Group/subgroup drill-down
  const [allGroups, setAllGroups] = useState([]) // from /api/groups
  const [selectedGroup, setSelectedGroup] = useState(null)
  const [selectedSubgroup, setSelectedSubgroup] = useState(null)

  // Derived filter state for API
  const filterParam = specialFilter === 'predicted_soon'
    ? 'predicted_soon'
    : activeTypes.size > 0
      ? [...activeTypes].join(',')
      : null

  // For client-side favorites filtering
  const isClientFilter = specialFilter === 'favorites'
  const groupsScope = search ? 'all' : 'history'

  // Handle chip clicks: type filters toggle, special filters are exclusive
  const handleFilterClick = (id) => {
    if (id === 'all') {
      setActiveTypes(new Set())
      setSpecialFilter(null)
    } else if (TYPE_FILTERS.includes(id)) {
      setSpecialFilter(null)
      setActiveTypes(prev => {
        const next = new Set(prev)
        if (next.has(id)) {
          next.delete(id)
        } else {
          next.add(id)
        }
        return next
      })
    } else {
      // Special filters (favorites, predicted_soon) — exclusive
      setActiveTypes(new Set())
      setSpecialFilter(prev => prev === id ? null : id)
    }
  }

  // Check if a chip is active
  const isChipActive = (id) => {
    if (id === 'all') return activeTypes.size === 0 && !specialFilter
    if (TYPE_FILTERS.includes(id)) return activeTypes.has(id)
    return specialFilter === id
  }

  // Check if any filter is active (for reset button)
  const hasActiveFilter = activeTypes.size > 0 || specialFilter !== null

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
      // Send server-side filter (not favorites — that's client-side)
      if (filterParam) {
        params.set('filter', filterParam)
      }
      // v1.7: group/subgroup server-side filter
      if (selectedGroup) params.set('group', selectedGroup)
      if (selectedSubgroup) params.set('subgroup', selectedSubgroup)

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
  }, [search, filterParam, sort, selectedGroup, selectedSubgroup])

  useEffect(() => {
    fetchProducts(1, false)
  }, [fetchProducts])

  // Keep group chips aligned with the current history dataset.
  // When searching we expose the full catalog; otherwise show only groups with history.
  useEffect(() => {
    fetch(`${API_BASE}/groups?scope=${groupsScope}`)
      .then(r => r.json())
      .then(data => setAllGroups(data.groups || []))
      .catch(() => {})
  }, [groupsScope])

  useEffect(() => {
    if (!selectedGroup) return
    const groupExists = allGroups.some(g => g.name === selectedGroup)
    if (!groupExists) {
      setSelectedGroup(null)
      setSelectedSubgroup(null)
      return
    }
    if (!selectedSubgroup) return
    const group = allGroups.find(g => g.name === selectedGroup)
    const subgroupExists = group?.subgroups?.some(sg => sg.name === selectedSubgroup)
    if (!subgroupExists) {
      setSelectedSubgroup(null)
    }
  }, [allGroups, selectedGroup, selectedSubgroup])

  // v1.7: Build group chips from allGroups
  const groupChips = useMemo(() => {
    if (!allGroups.length) return []
    return [
      { id: null, label: '🏷️ Все' },
      ...allGroups.map(g => ({ id: g.name, label: `${getCategoryEmoji(g.name)} ${g.name}` }))
    ]
  }, [allGroups])

  // v1.7: Build subgroup chips for selected group
  const subgroupChips = useMemo(() => {
    if (!selectedGroup) return []
    const g = allGroups.find(g => g.name === selectedGroup)
    if (!g || !g.subgroups || g.subgroups.length < 2) return []
    return [
      { id: null, label: 'Все' },
      ...g.subgroups.map(sg => ({ id: sg.name, label: `${sg.name} (${sg.count})` }))
    ]
  }, [selectedGroup, allGroups])

  // Debounced search — auto-clear type filters so search isn't silently restricted
  const handleSearchChange = (e) => {
    const val = e.target.value
    setSearchInput(val)
    // Clear type filters when searching — users expect search to find across all types
    if (val && (activeTypes.size > 0 || specialFilter)) {
      setActiveTypes(new Set())
      setSpecialFilter(null)
    }
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
            {FILTERS.map(f => {
              const active = isChipActive(f.id)
              return (
                <button
                  key={f.id}
                  className={`history-chip ${active ? 'active' : ''}`}
                  onClick={() => handleFilterClick(f.id)}
                  style={active && f.color ? {
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
              )
            })}
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

        {/* v1.7: Group/Subgroup chips */}
        {groupChips.length > 0 && (
          <div className="history-group-chips">
            <div className="history-filter-chips">
              {groupChips.map(g => (
                <button
                  key={g.id ?? 'all'}
                  className={`history-chip ${selectedGroup === g.id ? 'active' : ''}`}
                  onClick={() => {
                    setSelectedGroup(g.id)
                    setSelectedSubgroup(null)
                  }}
                >
                  {g.label}
                </button>
              ))}
            </div>
            {subgroupChips.length > 0 && (
              <div className="history-filter-chips subgroup-row">
                {subgroupChips.map(sg => (
                  <button
                    key={sg.id ?? 'all-sg'}
                    className={`history-chip history-chip-sub ${selectedSubgroup === sg.id ? 'active' : ''}`}
                    onClick={() => setSelectedSubgroup(sg.id)}
                  >
                    {sg.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
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
              {specialFilter === 'favorites' ? '⭐' : '🔍'}
            </div>
            <div>
              {specialFilter === 'favorites'
                ? 'Нет избранных товаров'
                : 'Ничего не найдено'}
            </div>
            {(searchInput || hasActiveFilter) && (
              <button
                className="history-chip active"
                onClick={() => { clearSearch(); setActiveTypes(new Set()); setSpecialFilter(null) }}
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
