// v1.16 BUG-01..BUG-04: Bug report form for authenticated MiniApp users.
// Auto-attaches runtime metadata (route, viewport, UA, app version, telegram_id, timestamp)
// and the recent console-log buffer at submit time.

import { useState, useRef, useEffect } from 'react'
import { getAuthHeaders } from './api.js'
import { getConsoleBuffer } from './consoleBuffer.js'

// App version is injected by Vite at build time via VITE_APP_VERSION env or git commit
const APP_VERSION = import.meta.env.VITE_APP_VERSION || 'dev'

const CATEGORIES = [
  { value: 'cart', label: 'Корзина' },
  { value: 'login', label: 'Вход / Авторизация' },
  { value: 'scrape', label: 'Цены / Каталог' },
  { value: 'ui', label: 'Интерфейс' },
  { value: 'other', label: 'Другое' },
]

const TEXT_MIN = 10
const TEXT_MAX = 2000
const PHOTO_MAX_BYTES = 5 * 1024 * 1024

export default function BugReportPanel({ userId, isOpen, onClose }) {
  const [text, setText] = useState('')
  const [category, setCategory] = useState('ui')
  const [photo, setPhoto] = useState(null)
  const [photoPreview, setPhotoPreview] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [success, setSuccess] = useState(false)
  const fileInputRef = useRef(null)

  // Reset state when panel opens
  useEffect(() => {
    if (isOpen) {
      setText('')
      setCategory('ui')
      setPhoto(null)
      setPhotoPreview(null)
      setError(null)
      setSuccess(false)
    }
  }, [isOpen])

  // Cleanup blob URL on unmount / new file
  useEffect(() => {
    return () => {
      if (photoPreview) URL.revokeObjectURL(photoPreview)
    }
  }, [photoPreview])

  const handlePhotoChange = (e) => {
    const file = e.target.files?.[0]
    if (!file) {
      setPhoto(null)
      setPhotoPreview(null)
      return
    }
    if (!file.type.startsWith('image/')) {
      setError('Файл должен быть изображением')
      e.target.value = ''
      return
    }
    if (file.size > PHOTO_MAX_BYTES) {
      setError(`Файл слишком большой (макс ${PHOTO_MAX_BYTES / 1024 / 1024}MB)`)
      e.target.value = ''
      return
    }
    setError(null)
    setPhoto(file)
    if (photoPreview) URL.revokeObjectURL(photoPreview)
    setPhotoPreview(URL.createObjectURL(file))
  }

  const removePhoto = () => {
    setPhoto(null)
    if (photoPreview) URL.revokeObjectURL(photoPreview)
    setPhotoPreview(null)
    if (fileInputRef.current) fileInputRef.current.value = ''
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError(null)

    const trimmed = text.trim()
    if (trimmed.length < TEXT_MIN) {
      setError(`Опишите подробнее (минимум ${TEXT_MIN} символов)`)
      return
    }
    if (trimmed.length > TEXT_MAX) {
      setError(`Слишком длинный текст (макс ${TEXT_MAX})`)
      return
    }

    setSubmitting(true)
    try {
      const formData = new FormData()
      formData.append('text', trimmed)
      formData.append('category', category)
      formData.append('telegram_id', String(userId))
      formData.append('route', window.location.pathname + window.location.search)
      formData.append('viewport', `${window.innerWidth}x${window.innerHeight}`)
      formData.append('user_agent', navigator.userAgent)
      formData.append('app_version', APP_VERSION)
      formData.append('console_logs', JSON.stringify(getConsoleBuffer()))
      if (photo) {
        formData.append('photo', photo, photo.name)
      }

      const res = await fetch('/api/bug-reports', {
        method: 'POST',
        headers: {
          // FormData sets Content-Type automatically with boundary
          ...getAuthHeaders(userId),
        },
        body: formData,
      })

      if (!res.ok) {
        let detail = 'Ошибка отправки'
        try {
          const err = await res.json()
          detail = err.detail || detail
        } catch {
          /* ignore */
        }
        throw new Error(detail)
      }

      setSuccess(true)
      // Auto-close after 2s
      setTimeout(() => {
        if (onClose) onClose()
      }, 2000)
    } catch (e) {
      setError(e.message || 'Не удалось отправить отчёт')
    } finally {
      setSubmitting(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="bug-report-overlay" onClick={onClose}>
      <div className="bug-report-panel" onClick={(e) => e.stopPropagation()}>
        <div className="bug-report-header">
          <h2>Сообщить об ошибке</h2>
          <button
            className="bug-report-close"
            onClick={onClose}
            aria-label="Закрыть"
            type="button"
          >
            ✕
          </button>
        </div>

        {success ? (
          <div className="bug-report-success">
            <div className="bug-report-success-icon">✅</div>
            <p>Спасибо! Отчёт отправлен.</p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="bug-report-form">
            <label className="bug-report-field">
              <span className="bug-report-label">Категория</span>
              <select
                value={category}
                onChange={(e) => setCategory(e.target.value)}
                disabled={submitting}
                className="bug-report-select"
              >
                {CATEGORIES.map((c) => (
                  <option key={c.value} value={c.value}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>

            <label className="bug-report-field">
              <span className="bug-report-label">
                Опишите проблему
                <span className="bug-report-counter">
                  {text.length}/{TEXT_MAX}
                </span>
              </span>
              <textarea
                value={text}
                onChange={(e) => setText(e.target.value)}
                disabled={submitting}
                placeholder="Что случилось? Как воспроизвести? Что вы ожидали увидеть?"
                rows={6}
                maxLength={TEXT_MAX}
                className="bug-report-textarea"
              />
            </label>

            <label className="bug-report-field">
              <span className="bug-report-label">
                Скриншот (необязательно, до {PHOTO_MAX_BYTES / 1024 / 1024}MB)
              </span>
              {photoPreview ? (
                <div className="bug-report-photo-preview">
                  <img src={photoPreview} alt="preview" />
                  <button
                    type="button"
                    onClick={removePhoto}
                    disabled={submitting}
                    className="bug-report-photo-remove"
                  >
                    Удалить
                  </button>
                </div>
              ) : (
                <input
                  ref={fileInputRef}
                  type="file"
                  accept="image/*"
                  onChange={handlePhotoChange}
                  disabled={submitting}
                  className="bug-report-file-input"
                />
              )}
            </label>

            {error && <div className="bug-report-error">{error}</div>}

            <div className="bug-report-actions">
              <button
                type="button"
                onClick={onClose}
                disabled={submitting}
                className="bug-report-btn-secondary"
              >
                Отмена
              </button>
              <button
                type="submit"
                disabled={submitting || text.trim().length < TEXT_MIN}
                className="bug-report-btn-primary"
              >
                {submitting ? 'Отправка…' : 'Отправить'}
              </button>
            </div>

            <div className="bug-report-meta-info">
              К отчёту прилагается: версия приложения, последние ошибки JS, текущая страница, тип устройства.
            </div>
          </form>
        )}
      </div>
    </div>
  )
}
