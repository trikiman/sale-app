// v1.26 Phase 83 Plan 83-03: extracted from App.jsx so Phase 84
// inline-style refactor has a direct file to touch + snapshot tests to
// regression-guard. Logic is byte-identical to the pre-extraction inline
// definition; only the module boundary is new.

import { useState, memo } from 'react'
import CartQuantityControl from './CartQuantityControl'
import { getCardMetaBadges, normalizeUnit } from './productMeta'
import { getCartStep } from './cartStep'
import { getCategoryEmoji, proxyImg, TYPE_CONFIG } from './cardConstants'

const ProductCard = memo(function ProductCard({ product, index: _index, isFavorite, onToggleFavorite, favoritesLoading, onAddToCart, onSetCartQuantity, viewMode: _viewMode, cartState, cartItem, isCartBusy, onOpenDetail, isStale }) {
  const [imageLoaded, setImageLoaded] = useState(false)
  const [imageError, setImageError] = useState(false)
  const metaBadges = getCardMetaBadges(product)

  // Calculate real discount percentage
  const oldPriceVal = parseFloat(product.oldPrice)
  const currentPriceVal = parseFloat(product.currentPrice)
  const hasDiscount = oldPriceVal > currentPriceVal && oldPriceVal > 0
  const discount = hasDiscount
    ? Math.round(((oldPriceVal - currentPriceVal) / oldPriceVal) * 100)
    : 0

  const config = TYPE_CONFIG[product.type] || TYPE_CONFIG._default
  const normalizedUnit = normalizeUnit(cartItem?.unit || product.unit)
  const showQuantityControl = cartState !== 'loading'
    && cartState !== 'pending'
    && cartState !== 'error'
    && Number(cartItem?.quantity || 0) > 0
  const step = getCartStep(normalizedUnit, cartItem)

  return (
    <div
      className={`card-vertical ${config.tint}`}
    >
      {/* Hero Image — clickable to open detail */}
      <div className="card-image-wrap" onClick={() => onOpenDetail(product)} style={{ cursor: 'pointer' }}>
        {!imageLoaded && !imageError && product.image && <div className="absolute inset-0 skeleton" />}

        {product.image && !imageError ? (
          <img
            src={proxyImg(product.image)}
            alt={product.name}
            referrerPolicy="no-referrer"
            loading="lazy"
            decoding="async"
            className={`card-hero-img ${imageLoaded ? 'loaded' : ''}`}
            onLoad={() => setImageLoaded(true)}
            onError={() => setImageError(true)}
          />
        ) : (
          <div className="card-hero-fallback">
            <span className="text-4xl">{getCategoryEmoji(product.category)}</span>
          </div>
        )}

        {/* Discount badge on image */}
        {hasDiscount && (
          <span className="card-discount">-{discount}%</span>
        )}

        {/* Favorite button on image */}
        <button
          className={`card-fav-btn tap-scale-xs ${isFavorite ? 'active' : ''} ${favoritesLoading ? 'loading' : ''}`}
          onClick={(e) => {
            e.stopPropagation()
            if (!favoritesLoading) onToggleFavorite(product)
          }}
          disabled={favoritesLoading}
        >
          {favoritesLoading ? (
            <div className="w-5 h-5 border-2 border-white/50 border-t-transparent rounded-full animate-spin" />
          ) : (
            isFavorite ? '❤️' : '🤍'
          )}
        </button>

        {/* Type badge on image */}
        <span className={`card-type-badge ${config.bg} ${config.text}`}>
          {config.label}
        </span>

        {/* v1.24 UX-STALE-01: per-card stale badge when the source for
            this card's type has gone stale. Visible alongside the favorite
            heart; aria-label surfaces the reason for screen readers. */}
        {isStale && (
          <span
            className="card-stale-badge"
            title="Источник устарел — показаны последние известные цены"
            aria-label="Данные устарели"
          >
            ⏳
          </span>
        )}
      </div>

      {/* Card Body */}
      <div className="card-body">
        <h3 className="card-title">{product.name}</h3>

        <div className="card-price-row">
          <div className="card-prices">
            <span className="card-price" style={{ color: config.priceColor }}>{product.currentPrice}₽</span>
            {hasDiscount && (
              <span className="card-old-price">{product.oldPrice}₽</span>
            )}
          </div>
          {showQuantityControl ? (
            <CartQuantityControl
              compact
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
              className={`cart-btn tap-scale-sm ${cartState === 'success' ? 'cart-btn-success' : ''} ${cartState === 'error' || cartState === 'retry' ? 'cart-btn-error' : ''} ${cartState === 'pending' ? 'cart-btn-pending' : ''}`}
              onClick={(e) => {
                e.stopPropagation()
                if (cartState !== 'loading' && cartState !== 'pending') onAddToCart(product)
              }}
              aria-label="Добавить в корзину"
              disabled={cartState === 'loading' || cartState === 'pending'}
            >
              {cartState === 'loading' ? (
                <span className="cart-btn-spinner" />
              ) : cartState === 'pending' ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.4">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6l4 2" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M12 21a9 9 0 100-18 9 9 0 000 18z" />
                </svg>
              ) : cartState === 'success' ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                </svg>
              ) : cartState === 'retry' ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2.5">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M1 4v6h6" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.51 15a9 9 0 105.64-11.36L1 10" />
                </svg>
              ) : cartState === 'error' ? (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="3">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              ) : (
                <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth="2">
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3 3h2l.4 2M7 13h10l4-8H5.4M7 13L5.4 5M7 13l-2.293 2.293c-.63.63-.184 1.707.707 1.707H17m0 0a2 2 0 100 4 2 2 0 000-4zm-8 2a2 2 0 100 4 2 2 0 000-4z" />
                </svg>
              )}
            </button>
          )}
        </div>

        <div className="card-meta-row">
          {metaBadges.map((badge) => (
            <span
              key={`${badge.kind}-${badge.text}`}
              className={badge.kind === 'stock' ? 'card-stock' : badge.kind === 'stock-zero' ? 'card-stock-zero' : 'card-weight'}
            >
              {badge.text}
            </span>
          ))}
        </div>
      </div>
    </div>
  )
}, (prev, next) => {
  // Custom comparator: skip re-render if nothing card-relevant changed
  return prev.product === next.product
    && prev.isFavorite === next.isFavorite
    && prev.cartState === next.cartState
    && prev.cartItem === next.cartItem
    && prev.isCartBusy === next.isCartBusy
    && prev.favoritesLoading === next.favoritesLoading
    && prev.viewMode === next.viewMode
    && prev.isStale === next.isStale
})

export default ProductCard
