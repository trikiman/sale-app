import { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

export default function ProductDetail({ product, onClose, onAddToCart, cartState }) {
  const [details, setDetails] = useState(null)
  const [loading, setLoading] = useState(true)
  const [imgIndex, setImgIndex] = useState(0)

  useEffect(() => {
    if (!product) return
    setLoading(true)
    setDetails(null)
    setImgIndex(0)
    fetch(`/api/product/${product.id}/details`)
      .then(r => r.json())
      .then(d => setDetails(d))
      .catch(() => setDetails({ _error: true }))
      .finally(() => setLoading(false))
  }, [product?.id])

  if (!product) return null

  const discount = product.oldPrice && product.currentPrice
    && parseInt(product.oldPrice) > 0 && parseInt(product.currentPrice) > 0
    && parseInt(product.oldPrice) > parseInt(product.currentPrice)
    ? Math.round((1 - parseInt(product.currentPrice) / parseInt(product.oldPrice)) * 100)
    : 0

  const images = details?.images?.length ? details.images : (product.image ? [product.image] : [])
  const weight = details?.weight || product.weight || ''

  return (
    <AnimatePresence>
      <motion.div
        className="detail-backdrop"
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        onClick={onClose}
      />
      <motion.div
        className="detail-drawer"
        initial={{ y: '100%' }}
        animate={{ y: 0 }}
        exit={{ y: '100%' }}
        transition={{ type: 'spring', damping: 32, stiffness: 300 }}
      >
        {/* Handle + close */}
        <div className="detail-handle-row">
          <div className="detail-handle" />
          <button className="detail-close" onClick={onClose}>✕</button>
        </div>

        <div className="detail-scroll">
          {/* Image gallery */}
          {images.length > 0 && (
            <div className="detail-gallery">
              <img
                src={images[imgIndex]}
                alt={product.name}
                className="detail-main-img"
                onError={e => { e.target.style.display = 'none' }}
              />
              {images.length > 1 && (
                <div className="detail-thumbs">
                  {images.map((img, i) => (
                    <button
                      key={i}
                      className={`detail-thumb ${i === imgIndex ? 'active' : ''}`}
                      onClick={() => setImgIndex(i)}
                    >
                      <img src={img} alt="" onError={e => { e.target.parentElement.style.display = 'none' }} />
                    </button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Header */}
          <div className="detail-header">
            <div className="detail-type-badge" data-type={product.type}>
              {product.type === 'green' ? '🟢 Зелёная' : product.type === 'red' ? '🔴 Скоро исчезнет' : '🟡 Скидка'}
            </div>
            <h2 className="detail-name">{product.name}</h2>

            <div className="detail-price-row">
              <span className="detail-price">{product.currentPrice}₽</span>
              {product.oldPrice && parseInt(product.oldPrice) > 0 && (
                <span className="detail-old-price">{product.oldPrice}₽</span>
              )}
              {discount > 0 && <span className="detail-discount-badge">-{discount}%</span>}
              {weight && <span className="detail-weight">{weight}</span>}
            </div>

            {product.stock > 0 && (
              <div className="detail-stock">📦 В наличии: {product.stock} {product.unit}</div>
            )}
          </div>

          {/* Add to cart */}
          <button
            className={`detail-cart-btn ${cartState === 'success' ? 'success' : cartState === 'error' ? 'error' : ''}`}
            onClick={() => onAddToCart(product)}
            disabled={cartState === 'loading'}
          >
            {cartState === 'loading' ? '⏳ Добавляем…'
              : cartState === 'success' ? '✅ Добавлено'
                : cartState === 'error' ? '❌ Ошибка'
                  : '🛒 В корзину'}
          </button>

          {/* Details */}
          {loading ? (
            <div className="detail-loading" style={{ textAlign: 'center', padding: '24px 0' }}>
              <div className="cart-btn-spinner" style={{ width: 24, height: 24, margin: '0 auto 8px' }} />
              Загружаем детали…
            </div>
          ) : (
            <div className="detail-sections">
              {details?.description && (
                <div className="detail-section">
                  <h3 className="detail-section-title">Описание</h3>
                  <p className="detail-section-body">{details.description}</p>
                </div>
              )}
              {details?.nutrition && (
                <div className="detail-section">
                  <h3 className="detail-section-title">Питательная ценность</h3>
                  <p className="detail-section-body">{details.nutrition}</p>
                </div>
              )}
              {details?.composition && (
                <div className="detail-section">
                  <h3 className="detail-section-title">Состав</h3>
                  <p className="detail-section-body">{details.composition}</p>
                </div>
              )}
              {details?.shelf_life && (
                <div className="detail-section">
                  <h3 className="detail-section-title">Годен</h3>
                  <p className="detail-section-body">{details.shelf_life}</p>
                </div>
              )}
              {details?.storage && (
                <div className="detail-section">
                  <h3 className="detail-section-title">Хранение</h3>
                  <p className="detail-section-body">{details.storage}</p>
                </div>
              )}
            </div>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  )
}
