import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

const Spinner = () => <span className="login-spinner" />

export default function Login({ userId, onLoginSuccess }) {
  const [step, setStep] = useState('phone')
  const [phone, setPhone] = useState(() => localStorage.getItem('vv_last_phone') || '')
  const [code, setCode] = useState('')
  const [pin, setPin] = useState('')
  const [newPin, setNewPin] = useState('')
  const [confirmPin, setConfirmPin] = useState('')
  const [forceSms, setForceSms] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [showInfo, setShowInfo] = useState(false)
  const [verifiedPhone, setVerifiedPhone] = useState('')

  // Refs for auto-submit
  const codeSubmitRef = useRef(null)
  const pinSubmitRef = useRef(null)

  // ── Phone Step ──
  const handlePhoneSubmit = async (e) => {
    e.preventDefault()
    if (!phone) return
    setLoading(true); setError(null)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, phone, force_sms: forceSms })
      })
      const data = await res.json()
      if (res.ok && data.success) {
        localStorage.setItem('vv_last_phone', phone)
        setStep(data.need_pin ? 'pin' : 'code')
      } else {
        setError(data.detail || 'Не удалось отправить SMS')
      }
    } catch { setError('Нет связи с сервером') }
    finally { setLoading(false) }
  }

  // ── PIN Step ──
  const doPinSubmit = async (pinValue) => {
    if (!pinValue || pinValue.length !== 4) return
    setLoading(true); setError(null)
    try {
      const res = await fetch('/api/auth/verify-pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, phone, pin: pinValue })
      })
      const data = await res.json()
      if (res.ok && data.success) onLoginSuccess()
      else { setError(data.detail || 'Неверный PIN'); setPin('') }
    } catch { setError('Нет связи с сервером') }
    finally { setLoading(false) }
  }

  const handlePinChange = (val) => {
    const clean = val.replace(/\D/g, '').slice(0, 4)
    setPin(clean)
    setError(null)
    if (clean.length === 4) setTimeout(() => doPinSubmit(clean), 150)
  }

  // ── SMS Code Step ──
  const doCodeSubmit = async (codeValue) => {
    if (!codeValue || codeValue.length < 4) return
    setLoading(true); setError(null)
    try {
      const res = await fetch('/api/auth/verify', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, code: codeValue })
      })
      const data = await res.json()
      if (res.ok && data.success) {
        if (data.need_set_pin && data.phone) {
          setVerifiedPhone(data.phone)
          setStep('set_pin')
        } else {
          onLoginSuccess()
        }
      } else { setError(data.detail || 'Неверный код'); setCode('') }
    } catch { setError('Нет связи с сервером') }
    finally { setLoading(false) }
  }

  const handleCodeChange = (val) => {
    const clean = val.replace(/\D/g, '').slice(0, 6)
    setCode(clean)
    setError(null)
    if (clean.length === 6) setTimeout(() => doCodeSubmit(clean), 150)
  }

  // ── Set PIN Step (with confirm) ──
  const handleSetPin = async (e) => {
    e.preventDefault()
    if (newPin.length !== 4) { setError('PIN должен быть 4 цифры'); return }
    if (newPin !== confirmPin) { setError('PIN не совпадают. Попробуйте ещё раз.'); setConfirmPin(''); return }
    setLoading(true); setError(null)
    try {
      const res = await fetch('/api/auth/set-pin', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: userId, phone: verifiedPhone, pin: newPin })
      })
      const data = await res.json()
      if (res.ok && data.success) onLoginSuccess()
      else setError(data.detail || 'Не удалось установить PIN')
    } catch { setError('Нет связи с сервером') }
    finally { setLoading(false) }
  }

  const renderStep = () => {
    switch (step) {
      case 'phone':
        return (
          <motion.form key="phone" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} onSubmit={handlePhoneSubmit} className="login-form">
            <input type="tel" placeholder="+7 900 123 45 67" value={phone} onChange={(e) => setPhone(e.target.value)} className="login-input" disabled={loading} autoFocus />
            <div className="login-option-row">
              <label className="login-toggle">
                <input type="checkbox" checked={forceSms} onChange={(e) => setForceSms(e.target.checked)} disabled={loading} />
                <span className="login-toggle-track"><span className="login-toggle-thumb" /></span>
                <span className="login-toggle-text">Новый вход</span>
              </label>
              <button type="button" className="login-info-btn" onClick={() => setShowInfo(!showInfo)} aria-label="Подробнее">ⓘ</button>
            </div>
            {showInfo && <div className="login-info-tooltip">Включите, если хотите войти заново через SMS. Старые данные будут удалены и создан новый PIN.</div>}
            <button type="submit" disabled={loading || !phone} className="login-btn">
              {loading ? <><Spinner /> Проверяем…</> : 'Получить код'}
            </button>
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
              {loading ? <><Spinner /> Проверяем…</> : 'Подтвердить'}
            </button>
            <button type="button" onClick={() => { setStep('phone'); setCode(''); setError(null) }} className="login-back-btn" disabled={loading}>Изменить номер</button>
          </motion.form>
        )

      case 'set_pin':
        return (
          <motion.form key="setpin" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} onSubmit={handleSetPin} className="login-form">
            <div className="login-hint">Придумайте 4-значный PIN</div>
            <input type="password" inputMode="numeric" placeholder="Новый PIN" value={newPin} onChange={(e) => setNewPin(e.target.value.replace(/\D/g, '').slice(0, 4))} maxLength={4} className="login-input login-input-code" disabled={loading} autoFocus />
            <input type="password" inputMode="numeric" placeholder="Повторите PIN" value={confirmPin} onChange={(e) => setConfirmPin(e.target.value.replace(/\D/g, '').slice(0, 4))} maxLength={4} className="login-input login-input-code" disabled={loading || newPin.length !== 4} />
            <button type="submit" disabled={loading || newPin.length !== 4 || confirmPin.length !== 4} className="login-btn">
              {loading ? <><Spinner /> Сохраняем…</> : 'Установить PIN'}
            </button>
            <button type="button" onClick={() => onLoginSuccess()} className="login-back-btn" disabled={loading}>Пропустить</button>
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
