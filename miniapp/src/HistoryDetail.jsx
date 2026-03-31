import { useState, useEffect } from 'react'
import { motion } from 'framer-motion'
import { getAuthHeaders } from './api'

const API_BASE = '/api'

const DAY_NAMES = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
const TYPE_COLORS = {
  green: '#22c55e',
  red: '#ef4444',
  yellow: '#eab308',
}

// Confidence gauge SVG
function ConfidenceGauge({ pct, label }) {
  const r = 40
  const circ = 2 * Math.PI * r
  const offset = circ - (pct / 100) * circ
  const color = pct >= 70 ? '#22c55e' : pct >= 40 ? '#eab308' : '#ef4444'

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

// Day-of-week pattern bars
function DayPattern({ pattern }) {
  if (!pattern) return null
  return (
    <div className="hd-day-pattern">
      <div className="hd-section-title">📅 Дни недели</div>
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
                  style={{ background: pct > 50 ? '#22c55e' : pct > 20 ? '#eab308' : 'rgba(255,255,255,0.15)' }}
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

// Hour distribution chart
function HourChart({ distribution }) {
  if (!distribution || Object.keys(distribution).length === 0) return null
  const maxVal = Math.max(...Object.values(distribution), 1)

  return (
    <div className="hd-hour-chart">
      <div className="hd-section-title">🕐 Время суток</div>
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

// Sale history log
function SaleLog({ sessions }) {
  if (!sessions || sessions.length === 0) return null
  return (
    <div className="hd-sale-log">
      <div className="hd-section-title">📋 История появлений</div>
      <div className="hd-log-list">
        {sessions.map((s, i) => (
          <div key={i} className={`hd-log-item ${s.is_active ? 'hd-log-active' : ''}`}>
            <div className="hd-log-date">{s.date}</div>
            <div className="hd-log-time">{s.time}</div>
            <span
              className="hd-log-type"
              style={{ background: (TYPE_COLORS[s.type] || '#666') + '33', color: TYPE_COLORS[s.type] || '#999' }}
            >
              {s.type === 'green' ? '💚' : s.type === 'red' ? '🔴' : '🟡'} -{s.discount}%
            </span>
            <div className="hd-log-window">{s.window}</div>
            <div className="hd-log-price">{s.price}₽</div>
          </div>
        ))}
      </div>
    </div>
  )
}

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
          {[...Array(4)].map((_, i) => <div key={i} className="history-skeleton" style={{ height: 120 }} />)}
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

  return (
    <div className="hd-page">
      {/* Header */}
      <div className="hd-header">
        <button className="history-back-btn" onClick={onBack}>← Назад</button>
        <h2 className="hd-title">{product?.name || 'Товар'}</h2>
      </div>

      {/* Product info row */}
      <div className="hd-product-row">
        {product?.image_url && (
          <img
            src={product.image_url}
            alt=""
            className="hd-product-img"
            referrerPolicy="no-referrer"
          />
        )}
        <div className="hd-product-info">
          <div className="hd-product-category">{product?.category || ''}</div>
          {product?.last_known_price > 0 && (
            <div className="hd-product-price">{product.last_known_price}₽</div>
          )}
          {product?.total_sale_count > 0 && (
            <div className="hd-product-stat">
              Был на скидке {product.total_sale_count} раз
            </div>
          )}
        </div>
      </div>

      {/* 3-column layout */}
      <div className="hd-grid">
        {/* Left column: Stats + Prediction */}
        <div className="hd-col">
          {/* Stats boxes */}
          <div className="hd-stats-grid">
            <div className="hd-stat-box">
              <div className="hd-stat-value">{prediction?.total_appearances || 0}</div>
              <div className="hd-stat-label">Появлений</div>
            </div>
            <div className="hd-stat-box">
              <div className="hd-stat-value">{prediction?.usual_time || '—'}</div>
              <div className="hd-stat-label">Обычное время</div>
            </div>
            <div className="hd-stat-box">
              <div className="hd-stat-value">{prediction?.avg_window_min || 0}м</div>
              <div className="hd-stat-label">Ср. окно</div>
            </div>
            <div className="hd-stat-box">
              <div className="hd-stat-value">-{prediction?.max_discount || 0}%</div>
              <div className="hd-stat-label">Макс. скидка</div>
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
                    <div className="hd-prediction-next">
                      Следующая скидка:
                    </div>
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

              {/* Wait advice */}
              {prediction.wait_advice && (
                <div className="hd-wait-advice">
                  ⚠️ {prediction.wait_advice}
                </div>
              )}
            </div>
          )}

          {/* Day pattern */}
          <DayPattern pattern={prediction?.day_pattern} />
        </div>

        {/* Right column: Hour chart + Sale log */}
        <div className="hd-col">
          <HourChart distribution={prediction?.hour_distribution} />
          <SaleLog sessions={sessions} />
        </div>
      </div>
    </div>
  )
}
