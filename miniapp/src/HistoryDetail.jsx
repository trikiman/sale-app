import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { getAuthHeaders } from './api'

const API_BASE = '/api'

const DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const TYPE_COLORS = {
  green: '#4ade80',
  red: '#ef4444',
  yellow: '#facc15',
}
const TYPE_BG = {
  green: 'rgba(74, 222, 128, .2)',
  red: 'rgba(239, 68, 68, .2)',
  yellow: 'rgba(250, 204, 21, .2)',
}

// ─── Confidence gauge SVG ────────────────────────────────
function ConfidenceGauge({ pct, label }) {
  const r = 40
  const circ = 2 * Math.PI * r
  const offset = circ - (pct / 100) * circ
  const color = pct >= 70 ? '#4ade80' : pct >= 40 ? '#facc15' : '#ef4444'

  return (
    <div className="hd-gauge">
      <svg width="100" height="100" viewBox="0 0 100 100">
        <circle cx="50" cy="50" r={r} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="8" />
        <circle
          cx="50" cy="50" r={r} fill="none"
          stroke={color} strokeWidth="8"
          strokeDasharray={circ} strokeDashoffset={offset}
          strokeLinecap="round"
          transform="rotate(-90 50 50)"
          style={{ transition: 'stroke-dashoffset 0.8s ease' }}
        />
        <text x="50" y="46" textAnchor="middle" fill="currentColor" fontSize="18" fontWeight="700">
          {pct}%
        </text>
        <text x="50" y="62" textAnchor="middle" fill="currentColor" fontSize="9" opacity="0.5">
          {label}
        </text>
      </svg>
    </div>
  )
}

// ─── Day-of-week pattern bars ────────────────────────────
function DayPattern({ pattern }) {
  if (!pattern) return null
  return (
    <div className="hd-day-pattern">
      <div className="hd-section-title">📅 Паттерн по дням недели</div>
      <div className="hd-day-bars">
        {DAY_NAMES.map((name, i) => {
          const prob = pattern[String(i)] || 0
          const pct = Math.round(prob * 100)
          return (
            <div key={i} className="hd-day-bar-wrap">
              <div className="hd-day-bar-bg">
                <motion.div
                  className="hd-day-bar-fill"
                  initial={{ height: 0 }}
                  animate={{ height: `${Math.max(pct, 2)}%` }}
                  transition={{ delay: i * 0.05, duration: 0.4 }}
                  style={{ background: pct > 50 ? '#4ade80' : pct > 20 ? '#facc15' : 'rgba(255,255,255,0.15)' }}
                />
              </div>
              <div className="hd-day-label">{name}</div>
              <div className="hd-day-pct">{pct}%</div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Calendar heatmap (monthly grid) ─────────────────────
function CalendarHeatmap({ calendar, sessions }) {
  if (!calendar || calendar.length === 0) return null

  // Build a month view from calendar data
  // calendar = [{date: "2026-03-16", sale_type: "green", time: "16:15", duration_min: 7, price: 289}, ...]
  const saleByDate = {}
  calendar.forEach(entry => {
    const d = entry.date
    if (!saleByDate[d]) saleByDate[d] = []
    saleByDate[d].push(entry)
  })

  // Get current month or use the most recent sale date's month
  const latestDate = calendar.length > 0 ? new Date(calendar[0].date) : new Date()
  const year = latestDate.getFullYear()
  const month = latestDate.getMonth()
  const monthNames = ['Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь',
    'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь']

  // Build grid: first day of month, days in month
  const firstDay = (new Date(year, month, 1).getDay() + 6) % 7 // Mon=0
  const daysInMonth = new Date(year, month + 1, 0).getDate()

  const cells = []
  // Empty cells for offset
  for (let i = 0; i < firstDay; i++) cells.push(null)
  // Day cells
  for (let d = 1; d <= daysInMonth; d++) {
    const dateStr = `${year}-${String(month + 1).padStart(2, '0')}-${String(d).padStart(2, '0')}`
    const sales = saleByDate[dateStr]
    cells.push({ day: d, dateStr, sales: sales || null })
  }

  return (
    <div className="hd-calendar">
      <div className="hd-section-title">📅 Календарь скидок — {monthNames[month]} {year}</div>
      <div className="hd-cal-header">
        {DAY_NAMES.map(d => <span key={d}>{d}</span>)}
      </div>
      <div className="hd-cal-grid">
        {cells.map((cell, i) => {
          if (!cell) return <div key={i} className="hd-cal-cell hd-cal-empty" />
          const type = cell.sales?.[0]?.sale_type
          const time = cell.sales?.[0]?.time
          const cls = type ? `hd-cal-cell hd-cal-${type}` : 'hd-cal-cell hd-cal-none'
          return (
            <div key={i} className={cls} title={cell.sales ? `${cell.dateStr}: ${type} в ${time}` : ''}>
              <span className="hd-cal-day">{cell.day}</span>
              {time && <span className="hd-cal-time">{time}</span>}
            </div>
          )
        })}
      </div>
      <div className="hd-cal-legend">
        <span><i style={{ background: TYPE_COLORS.green }} /> Green</span>
        <span><i style={{ background: TYPE_COLORS.red }} /> Red</span>
        <span><i style={{ background: TYPE_COLORS.yellow }} /> Yellow</span>
        <span><i style={{ background: 'rgba(255,255,255,0.06)' }} /> Нет скидки</span>
      </div>
    </div>
  )
}

// ─── Hour distribution chart ─────────────────────────────
function HourChart({ distribution }) {
  if (!distribution || Object.keys(distribution).length === 0) return null
  const maxVal = Math.max(...Object.values(distribution), 1)

  return (
    <div className="hd-hour-chart">
      <div className="hd-section-title">📈 Частота по времени суток</div>
      <div className="hd-hour-bars">
        {Array.from({ length: 24 }, (_, h) => {
          const count = distribution[String(h)] || 0
          const pct = (count / maxVal) * 100
          return (
            <div key={h} className="hd-hour-bar-wrap" title={`${h}:00 — ${count} раз`}>
              <div className="hd-hour-bar-bg">
                <motion.div
                  className="hd-hour-bar-fill"
                  initial={{ height: 0 }}
                  animate={{ height: `${Math.max(pct, count > 0 ? 8 : 0)}%` }}
                  transition={{ delay: h * 0.02, duration: 0.3 }}
                />
              </div>
              {h % 3 === 0 && <div className="hd-hour-label">{h}</div>}
            </div>
          )
        })}
      </div>
    </div>
  )
}

// ─── Sale history log ────────────────────────────────────
function SaleLog({ sessions }) {
  if (!sessions || sessions.length === 0) return null
  return (
    <div className="hd-sale-log">
      <div className="hd-section-title">📜 Последние появления ({sessions.length} записей)</div>
      <div className="hd-log-list">
        {sessions.map((s, i) => (
          <div key={i} className={`hd-log-item ${s.is_active ? 'hd-log-active' : ''}`}>
            <span className="hd-log-dot" style={{ background: TYPE_COLORS[s.type] || '#666' }} />
            <div className="hd-log-date">{s.date}</div>
            <div className="hd-log-time">{s.time}</div>
            <span
              className="hd-log-type"
              style={{ background: (TYPE_COLORS[s.type] || '#666') + '33', color: TYPE_COLORS[s.type] || '#999' }}
            >
              -{s.discount}%
            </span>
            <div className="hd-log-window">{s.window}</div>
            <div className="hd-log-price">{s.price}₽</div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ─── Main detail page ────────────────────────────────────
export default function HistoryDetail({ productId, onBack }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    setLoading(true)
    setError(null)
    fetch(`${API_BASE}/history/product/${productId}`, {
      headers: getAuthHeaders(),
    })
      .then(res => res.json())
      .then(d => {
        setData(d)
        setLoading(false)
      })
      .catch(err => {
        console.error('History detail error:', err)
        setError('Не удалось загрузить данные')
        setLoading(false)
      })
  }, [productId])

  if (loading) {
    return (
      <div className="hd-page">
        <div className="hd-header">
          <button className="history-back-btn" onClick={onBack}>← Назад</button>
          <h2 className="hd-title">Загрузка...</h2>
        </div>
        <div className="hd-loading">
          {[...Array(4)].map((_, i) => <div key={i} className="hcard-skeleton" style={{ height: 120 }} />)}
        </div>
      </div>
    )
  }

  if (error || !data) {
    return (
      <div className="hd-page">
        <div className="hd-header">
          <button className="history-back-btn" onClick={onBack}>← Назад</button>
        </div>
        <div className="history-empty">
          <div style={{ fontSize: 48 }}>😕</div>
          <div>{error || 'Данные не найдены'}</div>
        </div>
      </div>
    )
  }

  const { product, prediction, sessions } = data
  const calendar = prediction?.calendar || []
  const typeColor = TYPE_COLORS[product?.last_sale_type] || TYPE_COLORS.green
  const typeName = product?.last_sale_type === 'green' ? 'Green' :
    product?.last_sale_type === 'red' ? 'Red' : 'Yellow'

  return (
    <div className="hd-page">
      {/* Top bar */}
      <div className="hd-topbar">
        <button className="history-back-btn" onClick={onBack}>← Назад к списку</button>
      </div>

      {/* Hero — product info */}
      <div className="hd-hero">
        {product?.image_url ? (
          <img src={product.image_url} alt="" className="hd-hero-img" referrerPolicy="no-referrer" />
        ) : (
          <div className="hd-hero-emoji">📦</div>
        )}
        <div className="hd-hero-info">
          <div className="hd-hero-name">{product?.name || 'Товар'}</div>
          <div className="hd-hero-cat">{product?.category || ''}</div>
          <div className="hd-hero-prices">
            {product?.last_known_price > 0 && (
              <span className="hd-hero-price" style={{ color: typeColor }}>
                {product.last_known_price} ₽
              </span>
            )}
            {product?.last_old_price > 0 && (
              <span className="hd-hero-old">{product.last_old_price} ₽</span>
            )}
            {prediction?.max_discount > 0 && (
              <span className="hd-hero-pct" style={{ background: typeColor + '22', color: typeColor }}>
                -{prediction.max_discount}%
              </span>
            )}
          </div>
        </div>
        <div className="hd-hero-right">
          {product?.last_sale_type && (
            <span className="hd-type-pill" style={{ background: typeColor + '22', color: typeColor }}>
              {typeName} {prediction?.max_discount || ''}%
            </span>
          )}
        </div>
      </div>

      {/* ─── 3-column layout ─── */}
      <div className="hd-main-3col">
        {/* LEFT: Stats + Prediction + Day Pattern */}
        <div className="hd-col">
          <div className="hd-section-title">📊 Статистика</div>
          <div className="hd-stats-grid">
            <div className="hd-stat-box">
              <div className="hd-stat-value">{prediction?.total_appearances || 0}</div>
              <div className="hd-stat-label">раз в скидке</div>
            </div>
            <div className="hd-stat-box">
              <div className="hd-stat-value">{prediction?.usual_time || '—'}</div>
              <div className="hd-stat-label">обычное время</div>
            </div>
            <div className="hd-stat-box">
              <div className="hd-stat-value">{prediction?.avg_window_min || 0}м</div>
              <div className="hd-stat-label">окно ловли</div>
            </div>
            <div className="hd-stat-box">
              <div className="hd-stat-value">-{prediction?.max_discount || 0}%</div>
              <div className="hd-stat-label">макс. скидка</div>
            </div>
          </div>

          {/* Prediction */}
          {prediction?.confidence !== 'none' && (
            <div className="hd-prediction">
              <div className="hd-section-title">🔮 Прогноз</div>
              <div className="hd-prediction-body">
                <ConfidenceGauge
                  pct={prediction.confidence_pct || 0}
                  label={prediction.confidence === 'high' ? 'Высокая' :
                    prediction.confidence === 'medium' ? 'Средняя' : 'Низкая'}
                />
                {prediction.predicted_at && (
                  <div className="hd-prediction-text">
                    <div className="hd-prediction-next">Следующая скидка:</div>
                    <div className="hd-prediction-date">
                      {new Date(prediction.predicted_at).toLocaleDateString('ru-RU', {
                        weekday: 'short', day: 'numeric', month: 'short'
                      })}
                    </div>
                    <div className="hd-prediction-time">
                      в {prediction.usual_time || '??:??'}
                    </div>
                  </div>
                )}
              </div>

              {prediction.wait_advice && (
                <div className="hd-wait-advice">
                  ⚠️ {prediction.wait_advice}
                </div>
              )}
            </div>
          )}

          <DayPattern pattern={prediction?.day_pattern} />
        </div>

        {/* CENTER: Calendar + Hour chart */}
        <div className="hd-col hd-col-center">
          <CalendarHeatmap calendar={calendar} sessions={sessions} />
          <HourChart distribution={prediction?.hour_distribution} />
        </div>

        {/* RIGHT: Sale log */}
        <div className="hd-col">
          <SaleLog sessions={sessions} />
        </div>
      </div>
    </div>
  )
}
