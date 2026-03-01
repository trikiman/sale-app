import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function Login({ userId, onLoginSuccess }) {
  const [step, setStep] = useState('phone') // 'phone' or 'code'
  const [phone, setPhone] = useState('')
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const handlePhoneSubmit = async (e) => {
    e.preventDefault()
    if (!phone) return

    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_id: userId,
          phone: phone
        })
      })

      const data = await res.json()

      if (res.ok && data.success) {
        setStep('code')
      } else {
        setError(data.detail || 'Не удалось отправить SMS. Проверьте номер и попробуйте ещё раз')
      }
    } catch (err) {
      setError('Нет связи с сервером. Попробуйте ещё раз')
    } finally {
      setLoading(false)
    }
  }

  const handleCodeSubmit = async (e) => {
    e.preventDefault()
    if (!code || code.length < 4) {
      setError('Код должен быть не менее 4 цифр')
      return
    }

    setLoading(true)
    setError(null)

    try {
      const res = await fetch('/api/auth/verify', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({
          user_id: userId,
          code: code
        })
      })

      const data = await res.json()

      if (res.ok && data.success) {
        onLoginSuccess()
      } else {
        setError(data.detail || 'Неверный код')
      }
    } catch (err) {
      setError('Нет связи с сервером. Попробуйте ещё раз')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex flex-col items-center justify-center min-h-[60vh] p-4 text-center">
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="login-card p-6 rounded-2xl max-w-sm w-full"
      >
        <div className="text-4xl mb-4">🛒</div>
        <h2 className="text-xl font-bold mb-2">Вход во ВкусВилл</h2>
        <p className="text-sm opacity-70 mb-6">
          Авторизуйтесь, чтобы добавлять товары со скидками прямо в корзину ВкусВилл.
        </p>

        {error && (
          <div className="mb-4 p-3 bg-red-500/20 text-red-400 text-sm rounded-xl border border-red-500/30">
            {error}
          </div>
        )}

        <AnimatePresence mode="wait">
          {step === 'phone' ? (
            <motion.form
              key="phone-form"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              onSubmit={handlePhoneSubmit}
              className="space-y-4"
            >
              <div>
                <input
                  type="tel"
                  placeholder="+7 900 123 45 67"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  className="login-input"
                  disabled={loading}
                  autoFocus
                />
              </div>
              <button
                type="submit"
                disabled={loading || !phone}
                className="login-btn"
              >
                {loading ? 'Отправляем…' : 'Получить код'}
              </button>
            </motion.form>
          ) : (
            <motion.form
              key="code-form"
              initial={{ opacity: 0, x: -20 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: 20 }}
              onSubmit={handleCodeSubmit}
              className="space-y-4"
            >
              <div className="text-sm opacity-80 mb-2">
                Код отправлен на {phone}
              </div>
              <div>
                <input
                  type="text"
                  inputMode="numeric"
                  placeholder="Код из SMS"
                  value={code}
                  onChange={(e) => setCode(e.target.value)}
                  maxLength={6}
                  className="login-input text-center text-xl tracking-widest"
                  disabled={loading}
                  autoFocus
                />
              </div>
              <button
                type="submit"
                disabled={loading || code.length < 4}
                className="login-btn"
              >
                {loading ? 'Проверяем…' : 'Войти'}
              </button>
              <button
                type="button"
                onClick={() => setStep('phone')}
                className="w-full py-2 text-sm opacity-60 hover:opacity-100 transition-opacity"
                disabled={loading}
              >
                Изменить номер
              </button>
            </motion.form>
          )}
        </AnimatePresence>
      </motion.div>
    </div>
  )
}
