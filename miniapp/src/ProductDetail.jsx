import { useState, useEffect } from 'react'
import CartQuantityControl from './CartQuantityControl'
import { isWeightedUnit, normalizeUnit } from './productMeta'

// Route all VkusVill images through backend proxy.
// Backend handles smart CDN routing (cdn1-img → direct, img → proxy rotation).
function proxyImg(url) {
  if (!url) return url
  if (url.includes('vkusvill.ru')) {
    return `/api/img?url=${encodeURIComponent(url)}`
  }
  return url
}

export default function ProductDetail({ product, onClose, onAddToCart, onSetCartQuantity, cartState, cartItem, isCartBusy }) {
  const [details, setDetails] = useState(null)
  const [loading, setLoading] = useState(true)
  const [imgIndex, setImgIndex] = useState(0)

  useEffect(() => {
    if (!product) return
    setLoading(true)
    setDetails(null)
    setImgIndex(0)
    const controller = new AbortController()
    const timeout = setTimeout(() => controller.abort(), 8000)
    fetch(`/api/product/${product.id}/details`, { signal: controller.signal })
      .then(r => r.json())
      .then(d => setDetails(d))
      .catch(() => setDetails({ _error: true }))
      .finally(() => { clearTimeout(timeout); setLoading(false) })
    return () => { clearTimeout(timeout); controller.abort() }
  }, [product?.id])

  if (!product) return null

  const discount = product.oldPrice && product.currentPrice
    && parseInt(product.oldPrice) > 0 && parseInt(product.currentPrice) > 0
    && parseInt(product.oldPrice) > parseInt(product.currentPrice)
    ? Math.round((1 - parseInt(product.currentPrice) / parseInt(product.oldPrice)) * 100)
    : 0

  const images = details?.images?.length ? details.images : (product.image ? [product.image] : [])
  const weight = details?.weight || product.weight || ''
  const normalizedUnit = normalizeUnit(cartItem?.unit || product.unit)
  const step = Number(cartItem?.step || cartItem?.koef || (isWeightedUnit(normalizedUnit) ? 0.01 : 1))
  const showQuantityControl = cartState !== 'loading'
    && cartState !== 'pending'
    && cartState !== 'success'
    && cartState !== 'error'
    && cartState !== 'retry'
    && Number(cartItem?.quantity || 0) > 0

  return (
    <>
      <div
        className="detail-backdrop anim-fade"
        onClick={onClose}
      />
      <div
        className="detail-drawer cart-panel-enter"
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
                src={proxyImg(images[imgIndex])}
                alt={product.name}
                className="detail-main-img"
                referrerPolicy="no-referrer"
                onError={e => {
                  if (!e.target.dataset.fallbackAttempted && product.image && e.target.src !== product.image) {
                    e.target.dataset.fallbackAttempted = 'true';
                    e.target.src = product.image;
                  } else {
                    e.target.style.display = 'none';
                  }
                }}
              />
              {images.length > 1 && (
                <div className="detail-thumbs">
                  {images.map((img, i) => (
                    <button
                      key={i}
                      className={`detail-thumb ${i === imgIndex ? 'active' : ''}`}
                      onClick={() => setImgIndex(i)}
                    >
                      <img src={proxyImg(img)} alt={`${product?.name || 'Product'} image`} referrerPolicy="no-referrer" onError={e => { e.target.parentElement.style.display = 'none' }} />
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
          {showQuantityControl ? (
            <CartQuantityControl
              quantity={cartItem.quantity}
              unit={normalizedUnit}
              disabled={isCartBusy}
              canIncrement={!(Number(cartItem?.max_q || 0) > 0 && Number(cartItem.quantity || 0) >= Number(cartItem.max_q))}
              onDecrement={() => onSetCartQuantity(product, Math.max(0, Number(cartItem.quantity || 0) - step))}
              onIncrement={() => onSetCartQuantity(product, Number(cartItem.quantity || 0) + step)}
              onCommitQuantity={(nextQuantity) => onSetCartQuantity(product, nextQuantity)}
            />
          ) : (
            <button
              className={`detail-cart-btn ${cartState === 'success' ? 'success' : cartState === 'error' || cartState === 'retry' ? 'error' : cartState === 'pending' ? 'pending' : ''}`}
              onClick={() => onAddToCart(product)}
              disabled={cartState === 'loading' || cartState === 'pending'}
            >
              {cartState === 'loading' ? '⏳ Добавляем…'
                : cartState === 'pending' ? '🕓 Проверяем…'
                : cartState === 'success' ? '✅ Добавлено'
                  : cartState === 'retry' ? '🔄 Повторить'
                    : cartState === 'error' ? '❌ Ошибка'
                      : '🛒 В корзину'}
            </button>
          )}

          {/* Details */}
          {loading ? (
            <div className="detail-loading" style={{ textAlign: 'center', padding: '24px 0' }}>
              <div className="cart-btn-spinner" style={{ width: 24, height: 24, margin: '0 auto 8px' }} />
              Загружаем детали…
            </div>
          ) : details?._error ? (
            <div style={{ textAlign: 'center', padding: '16px 0' }}>
              <p style={{ opacity: 0.6, fontSize: '13px', margin: '0 0 12px' }}>
                📋 Подробная информация временно недоступна
              </p>
              {product.url && (
                <a
                  href={product.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  style={{
                    display: 'inline-flex', alignItems: 'center', gap: '6px',
                    padding: '10px 20px', borderRadius: '12px',
                    background: 'rgba(0,180,90,0.12)', color: '#00b45a',
                    fontWeight: 600, fontSize: '14px', textDecoration: 'none',
                  }}
                >
                  🔗 Открыть на VkusVill
                </a>
              )}
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
              {/* If no detail sections are available, show info message */}
              {details?.source_unavailable && !details?.description && !details?.composition && (
                <div className="detail-section" style={{ textAlign: 'center', opacity: 0.7 }}>
                  <p style={{ fontSize: '13px', margin: '8px 0' }}>
                    📋 Подробная информация временно недоступна
                  </p>
                </div>
              )}
              {/* VkusVill link */}
              {product.url && (
                <div className="detail-section" style={{ textAlign: 'center' }}>
                  <a
                    href={product.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="detail-vkusvill-link"
                    style={{
                      display: 'inline-flex', alignItems: 'center', gap: '6px',
                      padding: '10px 20px', borderRadius: '12px',
                      background: 'rgba(0,180,90,0.12)', color: '#00b45a',
                      fontWeight: 600, fontSize: '14px', textDecoration: 'none',
                      transition: 'background 0.2s',
                    }}
                  >
                    🔗 Открыть на VkusVill
                  </a>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}
