import { useState, useRef, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

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
  const [captchaImage, setCaptchaImage] = useState(null)
  const [captchaAnswer, setCaptchaAnswer] = useState('')
  const [captchaZoom, setCaptchaZoom] = useState(false)

  // Refs for auto-submit
  const codeSubmitRef = useRef(null)
  const pinSubmitRef = useRef(null)

  // ── Phone Step ──
  const handlePhoneSubmit = async (e) => {
    e.preventDefault()
    // Strip to pure digits for the API (prevents Pydantic 422 on non-string/format issues)
    const cleanPhone = phone.replace(/\D/g, '')
    if (!cleanPhone || cleanPhone.length < 10) return
    setLoading(true); setError(null)
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: String(userId), phone: cleanPhone, force_sms: forceSms })
      })
      const data = await res.json()
      if (res.ok && data.success) {
        localStorage.setItem('vv_last_phone', cleanPhone)
        if (data.need_captcha) {
          setCaptchaImage(data.captcha_image)
          setCaptchaAnswer('')
          setStep('captcha')
        } else {
          setStep(data.need_pin ? 'pin' : 'code')
        }
      } else {
        setError(extractErrorMsg(data, 'Не удалось отправить SMS'))
      }
    } catch (e) { setError(e.message || 'Нет связи с сервером') }
    finally { setLoading(false) }
  }

  // ── Captcha Step ──
  const handleCaptchaSubmit = async (e) => {
    e.preventDefault()
    if (!captchaAnswer.trim()) return
    setLoading(true); setError(null)
    try {
      const res = await fetch('/api/auth/captcha', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: String(userId), captcha_answer: captchaAnswer.trim() })
      })
      const data = await res.json()
      if (res.ok && data.success) {
        if (data.need_captcha) {
          // Wrong captcha — new image returned
          setCaptchaImage(data.captcha_image)
          setCaptchaAnswer('')
          setError(data.message || 'Неверная капча')
        } else {
          // Captcha solved — SMS sent
          setCaptchaImage(null)
          setCaptchaAnswer('')
          setStep('code')
        }
      } else {
        setError(extractErrorMsg(data, 'Ошибка капчи'))
      }
    } catch (e) { setError(e.message || 'Нет связи с сервером') }
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
          onLoginSuccess(phone)
        }
      } else { setError(extractErrorMsg(data, 'Неверный код')); setCode('') }
    } catch (e) { setError(e.message || 'Нет связи с сервером') }
    finally { setLoading(false) }
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
      const res = await fetch('/api/auth/set-pin', {
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
              {loading ? <><Spinner /> Проверяем…</> : 'Получить код'}
            </button>
          </motion.form>
        )

      case 'captcha':
        return (
          <motion.form key="captcha" initial={{ opacity: 0, x: -20 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 20 }} onSubmit={handleCaptchaSubmit} className="login-form">
            <div className="login-hint">Решите капчу для продолжения</div>
            {captchaImage && (
              <div className="login-captcha-wrapper">
                <img src={captchaImage} alt="Капча" className="login-captcha-img" onClick={() => setCaptchaZoom(true)} />
                <div className="login-captcha-zoom-hint" onClick={() => setCaptchaZoom(true)}>🔍 Нажмите чтобы увеличить</div>
              </div>
            )}
            <input type="text" placeholder="Введите текст с картинки" value={captchaAnswer} onChange={(e) => { setCaptchaAnswer(e.target.value); setError(null) }} className="login-input" disabled={loading} autoFocus autoComplete="off" />
            <button type="submit" disabled={loading || !captchaAnswer.trim()} className="login-btn">
              {loading ? <><Spinner /> Проверяем…</> : 'Отправить'}
            </button>
            <button type="button" onClick={() => { setStep('phone'); setCaptchaImage(null); setCaptchaAnswer(''); setError(null) }} className="login-back-btn" disabled={loading}>Изменить номер</button>
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
      {captchaZoom && captchaImage && (
        <div className="captcha-zoom-overlay" onClick={() => setCaptchaZoom(false)}>
          <img src={captchaImage} alt="Капча увеличенная" className="captcha-zoom-img" />
          <div className="captcha-zoom-close">✕ Нажмите чтобы закрыть</div>
        </div>
      )}
    </div>
  )
}
