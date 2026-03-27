import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

// Auth endpoints: Vercel proxy (30s timeout) — verify returns in ~16s now (v2)
const AUTH_BASE = ''

const Spinner = () => <span className="login-spinner" />

// BUG-B fix: Pydantic 422 errors return detail as an array of objects,
// not a string. Rendering an array/object as React child → error #31 → blank screen.
function extractErrorMsg(data, fallback = 'Ошибка') {
  const d = data?.detail
  if (!d) return fallback
  if (typeof d === 'string') return d
  if (Array.isArray(d)) return d.map(e => e?.msg || JSON.stringify(e)).join('; ')
  if (typeof d === 'object') return d.msg || JSON.stringify(d)
  return String(d)
}

export default function Login({ userId, onLoginSuccess }) {
  const [step, setStep] = useState('phone')
  const [phone, setPhone] = useState(() => localStorage.getItem('vv_last_phone') || '')
  const [code, setCode] = useState('')
  const [pin, setPin] = useState('')
  const [newPin, setNewPin] = useState('')
  const [confirmPin, setConfirmPin] = useState('')
  const [setPinStep, setSetPinStep] = useState(1) // 1: new, 2: confirm
  const [forceSms, setForceSms] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showInfo, setShowInfo] = useState(false)
  const [verifiedPhone, setVerifiedPhone] = useState('')
  const [statusText, setStatusText] = useState('')


  // Refs for auto-submit
  const codeSubmitRef = useRef(null)
  const pinSubmitRef = useRef(null)

  // ── Phone Step ──
  const handlePhoneSubmit = async (e) => {
    e.preventDefault()
    const cleanPhone = phone.replace(/\D/g, '')
    if (!cleanPhone || cleanPhone.length < 10) return
    setLoading(true); setError(null); setStatusText('Отправляем запрос...')
    try {
      // Step 1: Start login job (returns instantly)
      const res = await fetch(`${AUTH_BASE}/api/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: String(userId), phone: cleanPhone, force_sms: forceSms })
      })
      const ct = res.headers.get('content-type') || ''
      let data
      if (ct.includes('application/json')) {
        data = await res.json()
      } else {
        throw new Error('Сервер не отвечает. Попробуйте ещё раз.')
      }
      if (!res.ok || !data.success) {
        setError(extractErrorMsg(data, 'Не удалось начать вход'))
        setLoading(false)
        return
      }

      // Fast path: already has cookies + PIN
      if (data.need_pin) {
        localStorage.setItem('vv_last_phone', cleanPhone)
        setStep('pin')
        setLoading(false)
        return
      }

      // Step 2: Poll for status
      const jobId = data.job_id
      if (!jobId) {
        setError('Сервер не вернул job_id')
        setLoading(false)
        return
      }

      localStorage.setItem('vv_last_phone', cleanPhone)
      setStatusText('Запускаем браузер...')

      // Poll every 3s for up to 3 minutes
      for (let i = 0; i < 60; i++) {
        await new Promise(r => setTimeout(r, 3000))
        try {
          const pollRes = await fetch(`${AUTH_BASE}/api/auth/login/status/${jobId}`)
          if (!pollRes.ok) {
            if (pollRes.status === 404) {
              setError('Сессия не найдена. Попробуйте ещё раз.')
              setLoading(false)
              return
            }
            continue
          }
          const pollData = await pollRes.json()
          setStatusText(pollData.message || 'Обработка...')

          if (pollData.status === 'done') {
            const result = pollData.result || {}
            setStep(result.need_pin ? 'pin' : 'code')
            setLoading(false)
            return
          }
          if (pollData.status === 'error') {
            setError(pollData.message || 'Ошибка входа')
            setLoading(false)
            return
          }
          // else: still in progress, keep polling
        } catch {
          // Network error on poll — keep trying
        }
      }
      // Timeout after 3 minutes of polling
      setError('Превышено время ожидания (3 мин). Попробуйте ещё раз.')
    } catch (e) {
      setError(e.message || 'Нет связи с сервером')
    }
    finally { setLoading(false); setStatusText('') }
  }



  // ── PIN Step ──
  const doPinSubmit = async (pinValue) => {
    if (!pinValue || pinValue.length !== 4) return
    setLoading(true); setError(null)
    try {
      const res = await fetch(`${AUTH_BASE}/api/auth/verify-pin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, phone, pin: pinValue })
      })
      const data = await res.json()
      if (res.ok && data.success) onLoginSuccess(phone)
      else { setError(extractErrorMsg(data, 'Неверный PIN')); setPin('') }
    } catch (e) { setError(e.message || 'Нет связи с сервером') }
    finally { setLoading(false) }
  }

  const handlePinChange = (val) => {
    const clean = val.replace(/\D/g, '').slice(0, 4)
    setPin(clean)
    setError(null)
    if (clean.length === 4) setTimeout(() => doPinSubmit(clean), 150)
  }

  // ── SMS Code Step (async polling — bypasses Vercel 30s timeout) ──
  const doCodeSubmit = async (codeValue) => {
    if (!codeValue || codeValue.length < 4) return
    setLoading(true); setError(null); setStatusText('Отправляем код...')
    try {
      // Step 1: Start verify job (returns instantly with job_id)
      const res = await fetch(`${AUTH_BASE}/api/auth/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, code: codeValue })
      })
      const ct = res.headers.get('content-type') || ''
      let data
      if (ct.includes('application/json')) {
        data = await res.json()
      } else {
        throw new Error('Сервер не отвечает. Попробуйте ещё раз.')
      }
      if (!res.ok || !data.success) {
        setError(extractErrorMsg(data, 'Не удалось проверить код'))
        setLoading(false); setStatusText('')
        return
      }

      const jobId = data.job_id
      if (!jobId) {
        // Legacy direct response (backward compat if backend not updated)
        if (data.need_set_pin && data.phone) {
          setVerifiedPhone(data.phone)
          setStep('set_pin')
        } else {
          onLoginSuccess(phone)
        }
        setLoading(false); setStatusText('')
        return
      }

      // Step 2: Poll for status every 3s for up to 2 minutes
      setStatusText('Проверяем код...')
      for (let i = 0; i < 40; i++) {
        await new Promise(r => setTimeout(r, 3000))
        try {
          const pollRes = await fetch(`${AUTH_BASE}/api/auth/verify/status/${jobId}`)
          if (!pollRes.ok) {
            if (pollRes.status === 404) {
              setError('Сессия не найдена. Попробуйте ещё раз.')
              setLoading(false); setStatusText('')
              return
            }
            continue
          }
          const pollData = await pollRes.json()
          setStatusText(pollData.message || 'Обработка...')

          if (pollData.status === 'done') {
            const result = pollData.result || {}
            if (result.success) {
              if (result.need_set_pin && result.phone) {
                setVerifiedPhone(result.phone)
                setStep('set_pin')
              } else {
                onLoginSuccess(phone)
              }
            } else {
              setError(result.message || 'Неверный код')
              setCode('')
            }
            setLoading(false); setStatusText('')
            return
          }
          if (pollData.status === 'error') {
            setError(pollData.message || 'Ошибка проверки кода')
            setLoading(false); setStatusText('')
            return
          }
          // else: still in progress, keep polling
        } catch {
          // Network error on poll — keep trying
        }
      }
      // Timeout after 2 minutes of polling
      setError('Превышено время ожидания (2 мин). Попробуйте ещё раз.')
    } catch (e) {
      setError(e.message || 'Нет связи с сервером')
    }
    finally { setLoading(false); setStatusText('') }
  }

  const handleCodeChange = (val) => {
    const clean = val.replace(/\D/g, '').slice(0, 6)
    setCode(clean)
    setError(null)
    if (clean.length === 6) setTimeout(() => doCodeSubmit(clean), 150)
  }

  // ── Set PIN Step (with confirm) ──
  const doSetPinSubmit = async (pin1, pin2) => {
    if (pin1.length !== 4 || pin2.length !== 4) return
    if (pin1 !== pin2) { setError('PIN не совпадают. Попробуйте ещё раз.'); setConfirmPin(''); setSetPinStep(1); setNewPin(''); return }
    setLoading(true); setError(null)
    try {
      const res = await fetch(`${AUTH_BASE}/api/auth/set-pin`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, phone: verifiedPhone, pin: pin1 })
      })
      const data = await res.json()
      if (res.ok && data.success) onLoginSuccess(verifiedPhone)
      else setError(extractErrorMsg(data, 'Не удалось установить PIN'))
    } catch (e) { setError(e.message || 'Нет связи с сервером') }
    finally { setLoading(false) }
  }

  const handleSetPin = async (e) => {
    e.preventDefault()
    doSetPinSubmit(newPin, confirmPin)
  }

  const handleNewPinChange = (val) => {
    const clean = val.replace(/\D/g, '').slice(0, 4)
    setNewPin(clean)
    setError(null)
    if (clean.length === 4) setTimeout(() => setSetPinStep(2), 150)
  }

  const handleConfirmPinChange = (val) => {
    const clean = val.replace(/\D/g, '').slice(0, 4)
    setConfirmPin(clean)
    setError(null)
    if (clean.length === 4) setTimeout(() => doSetPinSubmit(newPin, clean), 150)
  }

  const renderStep = () => {
    switch (step) {
      case 'phone':
        return (
          <motion.form key="phone" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} onSubmit={handlePhoneSubmit} className="login-form">
            <input type="tel" placeholder="+7 900 123 45 67" value={phone} onChange={(e) => setPhone(e.target.value.replace(/[^\d+\s()-]/g, ''))} className="login-input" disabled={loading} autoFocus />
            <div className="login-option-row">
              <label className="login-toggle">
                <input type="checkbox" checked={forceSms} onChange={(e) => setForceSms(e.target.checked)} disabled={loading} />
                <span className="login-toggle-track"><span className="login-toggle-thumb" /></span>
                <span className="login-toggle-text">Новый вход</span>
              </label>
              <button type="button" className="login-info-btn" onClick={() => setShowInfo(!showInfo)} aria-label="Подробнее">ⓘ</button>
            </div>
            {showInfo && <div className="login-info-tooltip">Включите, если хотите войти заново через SMS. Старые данные будут удалены и создан новый PIN.</div>}
            <button type="submit" disabled={loading || phone.replace(/\D/g, '').length < 10} className="login-btn">
            {loading ? <><Spinner /> {statusText || 'Получаем код…'}</> : 'Получить код'}
            </button>
            {loading && <div className="login-loading-hint">{statusText || 'Разгадываем капчу и отправляем SMS...'}</div>}
          </motion.form>
        )



      case 'pin':
        return (
          <motion.form key="pin" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} onSubmit={(e) => { e.preventDefault(); doPinSubmit(pin) }} className="login-form">
            <div className="login-hint">Введите PIN для {phone}</div>
            <input type="password" inputMode="numeric" placeholder="● ● ● ●" value={pin} onChange={(e) => handlePinChange(e.target.value)} maxLength={4} className="login-input login-input-code" disabled={loading} autoFocus />
            <button type="submit" disabled={loading || pin.length !== 4} className="login-btn">
              {loading ? <><Spinner /> Проверяем…</> : 'Войти'}
            </button>
            <button type="button" onClick={() => { setForceSms(true); setStep('phone'); setPin(''); setError(null) }} className="login-back-btn" disabled={loading}>
              Войти через SMS
            </button>
          </motion.form>
        )

      case 'code':
        return (
          <motion.form key="code" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} onSubmit={(e) => { e.preventDefault(); doCodeSubmit(code) }} className="login-form">
            <div className="login-hint">Код отправлен на {phone}</div>
            <input type="text" inputMode="numeric" placeholder="Код из SMS" value={code} onChange={(e) => handleCodeChange(e.target.value)} maxLength={6} className="login-input login-input-code" disabled={loading} autoFocus />
            <button type="submit" disabled={loading || code.length < 4} className="login-btn">
              {loading ? <><Spinner /> {statusText || 'Проверяем…'}</> : 'Подтвердить'}
            </button>
            {loading && <div className="login-loading-hint">{statusText || 'Проверяем код...'}</div>}
            <button type="button" onClick={() => { setStep('phone'); setCode(''); setForceSms(false); setError(null) }} className="login-back-btn" disabled={loading}>Изменить номер</button>
          </motion.form>
        )

      case 'set_pin':
        return (
          <motion.form key={`setpin-${setPinStep}`} initial={{ opacity: 0, x: setPinStep === 1 ? -20 : 20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: setPinStep === 1 ? 20 : -20 }} onSubmit={handleSetPin} className="login-form">
            <div className="login-hint">{setPinStep === 1 ? 'Придумайте 4-значный PIN' : 'Повторите PIN'}</div>
            <div className="login-pin-info">
              🔐 PIN нужен чтобы входить без SMS в следующий раз. Без него вам придётся каждый раз запрашивать код.
            </div>

            {setPinStep === 1 ? (
              <input type="password" inputMode="numeric" placeholder="Новый PIN" value={newPin} onChange={(e) => handleNewPinChange(e.target.value)} maxLength={4} className="login-input login-input-code" disabled={loading} autoFocus />
            ) : (
              <input type="password" inputMode="numeric" placeholder="Повторите PIN" value={confirmPin} onChange={(e) => handleConfirmPinChange(e.target.value)} maxLength={4} className="login-input login-input-code" disabled={loading} autoFocus />
            )}

            {setPinStep === 2 && (
              <button type="submit" disabled={loading || confirmPin.length !== 4} className="login-btn">
                {loading ? <><Spinner /> Сохраняем…</> : 'Установить PIN'}
              </button>
            )}
            {setPinStep === 2 && (
              <button type="button" onClick={() => { setSetPinStep(1); setConfirmPin(''); setNewPin(''); setError(null) }} className="login-back-btn" disabled={loading}>
                Назад
              </button>
            )}
          </motion.form>
        )
    }
  }

  return (
    <div className="login-wrapper">
      <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="login-card">
        <div className="login-icon">🛒</div>
        <h2 className="login-title">Вход во ВкусВилл</h2>
        <p className="login-subtitle">
          {step === 'set_pin' ? 'PIN позволит входить без SMS в следующий раз' : 'Авторизуйтесь, чтобы добавлять товары со скидками прямо в корзину ВкусВилл.'}
        </p>
        {error && <div className="login-error">{error}</div>}
        <AnimatePresence mode="wait">{renderStep()}</AnimatePresence>
      </motion.div>

    </div>
  )
}
