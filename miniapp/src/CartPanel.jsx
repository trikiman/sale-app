import { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function CartPanel({ isOpen, onClose, userId }) {
    const [items, setItems] = useState([])
    const [totalPrice, setTotalPrice] = useState(0)
    const [itemsCount, setItemsCount] = useState(0)
    const [loading, setLoading] = useState(false)
    const [error, setError] = useState(null)
    const [busyIds, setBusyIds] = useState(new Set())
    const [clearing, setClearing] = useState(false)
    const cacheRef = useRef(null) // { items, totalPrice, itemsCount, ts }

    const fetchCart = useCallback((showSpinner = true) => {
        if (!userId) return
        if (showSpinner) setLoading(true)
        setError(null)
        fetch(`/api/cart/items/${userId}`)
            .then(res => {
                if (!res.ok) throw new Error(res.status === 401 ? 'Не авторизованы' : 'Ошибка загрузки')
                return res.json()
            })
            .then(data => {
                const newItems = data.items || []
                setItems(newItems)
                setTotalPrice(data.total_price || 0)
                setItemsCount(data.items_count || 0)
                cacheRef.current = {
                    items: newItems,
                    totalPrice: data.total_price || 0,
                    itemsCount: data.items_count || 0,
                    ts: Date.now()
                }
            })
            .catch(e => setError(e.message))
            .finally(() => setLoading(false))
    }, [userId])

    useEffect(() => {
        if (isOpen && userId) {
            // R2-28: Lock body scroll when cart is open
            document.body.classList.add('cart-open')
            // If cache is fresh (<30s), show it and refresh in background
            if (cacheRef.current && (Date.now() - cacheRef.current.ts) < 30000) {
                setItems(cacheRef.current.items)
                setTotalPrice(cacheRef.current.totalPrice)
                setItemsCount(cacheRef.current.itemsCount)
                fetchCart(false) // silent background refresh
            } else {
                fetchCart(true)
            }
        } else {
            document.body.classList.remove('cart-open')
        }
        return () => document.body.classList.remove('cart-open')
    }, [isOpen, userId, fetchCart])

    const markBusy = (id, busy) => {
        setBusyIds(s => {
            const n = new Set(s)
            busy ? n.add(id) : n.delete(id)
            return n
        })
    }

    const handleRemove = async (productId) => {
        markBusy(productId, true)
        try {
            const res = await fetch('/api/cart/remove', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, product_id: productId })
            })
            if (res.ok) fetchCart(false)
        } catch (e) { setError('Ошибка при удалении') }
        markBusy(productId, false)
    }

    const handleQuantity = async (productId, delta) => {
        markBusy(productId, true)
        try {
            const endpoint = delta > 0 ? '/api/cart/add' : '/api/cart/remove'
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId, product_id: productId })
            })
            if (res.ok) fetchCart(false)
        } catch (e) { setError('Ошибка сети') }
        markBusy(productId, false)
    }

    const handleClearAll = async () => {
        if (window.Telegram?.WebApp?.showConfirm) {
            const ok = await new Promise(r => window.Telegram.WebApp.showConfirm('Очистить всю корзину?', r))
            if (!ok) return
        } else if (typeof window.confirm === 'function') {
            try {
                if (!window.confirm('Очистить всю корзину?')) return
            } catch {
                // confirm() blocked (e.g., in Telegram WebApp) — proceed without confirmation
            }
        }
        setClearing(true)
        try {
            await fetch('/api/cart/clear', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_id: userId })
            })
            cacheRef.current = null
            fetchCart(false)
        } catch (e) {
            setError('Ошибка очистки')
        } finally {
            setClearing(false)
        }
    }

    const outOfStock = items.filter(i => !i.can_buy)
    const lowStock = items.filter(i => i.can_buy && i.max_q > 0 && i.max_q <= 3)

    return (
        <AnimatePresence>
            {isOpen && (
                <>
                    <motion.div
                        className="cart-backdrop"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                        onClick={onClose}
                    />
                    <motion.div
                        className="cart-panel"
                        initial={{ y: '100%' }}
                        animate={{ y: 0 }}
                        exit={{ y: '100%' }}
                        transition={{ type: 'spring', damping: 30, stiffness: 300 }}
                    >
                        <div className="cart-panel-header">
                            <div className="cart-panel-handle" />
                            <h3 className="cart-panel-title">
                                🛒 Корзина
                                {itemsCount > 0 && <span className="cart-panel-count">{itemsCount}</span>}
                            </h3>
                            <div className="cart-panel-header-actions">
                                {items.length > 0 && (
                                    <button className="cart-clear-btn" onClick={handleClearAll} disabled={clearing} title="Очистить всю корзину">
                                        {clearing ? '⏳ Очищаем…' : '🗑 Очистить'}
                                    </button>
                                )}
                                <button className="cart-panel-close" onClick={onClose}>✕</button>
                            </div>
                        </div>

                        <div className="cart-panel-body">
                            {loading && items.length === 0 && (
                                <div className="cart-panel-loading">
                                    <span className="cart-btn-spinner" style={{ width: 24, height: 24 }} />
                                    <span>Загружаем…</span>
                                </div>
                            )}

                            {error && <div className="cart-panel-error">{error}</div>}

                            {!loading && !error && items.length === 0 && (
                                <div className="cart-panel-empty">Корзина пуста</div>
                            )}

                            {outOfStock.length > 0 && (
                                <div className="cart-alert cart-alert-red">
                                    🔴 {outOfStock.length} {outOfStock.length === 1 ? 'товар закончился' : 'товаров закончились'}!
                                </div>
                            )}

                            {lowStock.length > 0 && (
                                <div className="cart-alert cart-alert-yellow">
                                    🟡 {lowStock.length} {lowStock.length === 1 ? 'товар заканчивается' : 'товаров заканчиваются'} — поторопитесь!
                                </div>
                            )}

                            {items.length > 0 && (
                                <div className="cart-items-list">
                                    {items.map((item, i) => {
                                        const isBusy = busyIds.has(item.id)
                                        const atMax = item.max_q > 0 && item.quantity >= item.max_q
                                        return (
                                            <div key={item.id || i} className={`cart-item ${!item.can_buy ? 'cart-item-oos' : ''}`}>
                                                {item.image && (
                                                    <img
                                                        src={item.image.startsWith('http') || item.image.startsWith('//') ? item.image : `https://vkusvill.ru${item.image}`}
                                                        alt={item.name || 'Товар'}
                                                        className="cart-item-img"
                                                        onError={e => { e.target.style.display = 'none' }}
                                                    />
                                                )}
                                                <div className="cart-item-info">
                                                    <span className="cart-item-name">
                                                        {!item.can_buy && '❌ '}
                                                        {item.can_buy && item.max_q > 0 && item.max_q <= 3 && '⚠️ '}
                                                        {item.name}
                                                    </span>
                                                    <span className="cart-item-price-row">
                                                        <span className="cart-item-current-price">{item.price}₽</span>
                                                        {item.old_price > 0 && item.old_price !== item.price && (
                                                            <span className="cart-item-old-price">{item.old_price}₽</span>
                                                        )}
                                                    </span>
                                                    <span className="cart-item-meta">
                                                        📦 {item.quantity} шт
                                                        {item.can_buy && item.max_q > 0 && item.max_q <= 3 && (
                                                            <span className="cart-item-low"> · осталось {item.max_q}</span>
                                                        )}
                                                        {atMax && <span className="cart-item-low"> · макс</span>}
                                                    </span>
                                                </div>
                                                <div className="cart-qty-controls">
                                                    <button
                                                        className="cart-qty-btn"
                                                        onClick={() => item.quantity <= 1 ? handleRemove(item.id) : handleQuantity(item.id, -1)}
                                                        disabled={isBusy}
                                                    >
                                                        {item.quantity <= 1 ? <span className="cart-qty-trash">🗑</span> : '−'}
                                                    </button>
                                                    <span className="cart-qty-value">{isBusy ? '…' : item.quantity}</span>
                                                    <button
                                                        className="cart-qty-btn"
                                                        onClick={() => handleQuantity(item.id, 1)}
                                                        disabled={isBusy || !item.can_buy || atMax}
                                                    >
                                                        +
                                                    </button>
                                                </div>
                                            </div>
                                        )
                                    })}
                                </div>
                            )}
                        </div>

                        {items.length > 0 && (
                            <div className="cart-panel-footer">
                                <span>Итого: <strong>{totalPrice}₽</strong></span>
                                <a href="https://vkusvill.ru/cart/" target="_blank" rel="noopener noreferrer" className="cart-panel-checkout"
                                    title="Откроется сайт ВкусВилл — убедитесь, что вы авторизованы">
                                    Оформить →
                                </a>
                            </div>
                        )}
                    </motion.div>
                </>
            )}
        </AnimatePresence>
    )
}
