// v1.26 Phase 83 Plan 83-03 (TEST-02): pins ProductCard DOM structure in
// two states (cart-button and stepper). Primary regression target:
// v1.23 UX-SHIFT-01 min-height: 36px lock on .card-price-row — if
// Phase 84's inline-style refactor accidentally drops that div or
// renames the class, this snapshot trips CI.
//
// Secondary regression targets:
// - v1.24 UX-STALE-01 per-card stale badge (⏳ when isStale prop true)
// - TYPE_CONFIG tint class applied to .card-vertical root
// - cart-button SVGs for each cartState variant

import { describe, it, expect, vi } from 'vitest'
import { render } from '@testing-library/react'
import ProductCard from '../ProductCard'

const makeProduct = (overrides = {}) => ({
  id: 33215,
  name: 'Test Product',
  type: 'green',
  currentPrice: 102,
  oldPrice: 170,
  category: 'Молочка',
  image: '',
  unit: 'шт',
  stock: 2,
  weight: '200 г',
  ...overrides,
})

const defaultProps = () => ({
  product: makeProduct(),
  index: 0,
  isFavorite: false,
  onToggleFavorite: vi.fn(),
  favoritesLoading: false,
  onAddToCart: vi.fn(),
  onSetCartQuantity: vi.fn(),
  viewMode: 'grid',
  cartState: null,
  cartItem: null,
  isCartBusy: false,
  onOpenDetail: vi.fn(),
  isStale: false,
})

describe('ProductCard snapshot', () => {
  it('renders in cart-button state (no cart item)', () => {
    const { container } = render(<ProductCard {...defaultProps()} />)

    // v1.23 UX-SHIFT-01 regression guard: .card-price-row MUST exist.
    // The 36px min-height CSS rule attaches to this class — if Phase 84
    // refactor moves the button out of this container the layout shift
    // returns.
    expect(container.querySelector('.card-price-row')).toBeInTheDocument()

    // .card-vertical root with the green tint class
    expect(container.querySelector('.card-vertical.card-tint-green')).toBeInTheDocument()

    // Cart-button present; no stepper
    expect(container.querySelector('.cart-btn')).toBeInTheDocument()
    expect(container.querySelector('.cart-inline-qty')).not.toBeInTheDocument()

    // Snapshot captures full DOM for Phase 84 regression guard
    expect(container.firstChild).toMatchSnapshot()
  })

  it('renders in stepper state (cartItem with quantity)', () => {
    const props = {
      ...defaultProps(),
      cartItem: { id: 33215, quantity: 2, unit: 'шт', step: 1, koef: 1, max_q: 10 },
      cartState: 'idle',
    }
    const { container } = render(<ProductCard {...props} />)

    // v1.23 UX-SHIFT-01: same container class, different child content
    expect(container.querySelector('.card-price-row')).toBeInTheDocument()

    // Stepper present; no cart-button
    expect(container.querySelector('.cart-inline-qty.compact')).toBeInTheDocument()
    expect(container.querySelector('.cart-btn')).not.toBeInTheDocument()

    expect(container.firstChild).toMatchSnapshot()
  })

  it('renders per-card stale badge when isStale=true (v1.24 UX-STALE-01)', () => {
    const props = { ...defaultProps(), isStale: true }
    const { container, getByTitle } = render(<ProductCard {...props} />)

    const staleBadge = container.querySelector('.card-stale-badge')
    expect(staleBadge).toBeInTheDocument()
    expect(staleBadge).toHaveTextContent('⏳')
    // A11y: aria-label surfaces the reason
    expect(staleBadge).toHaveAttribute('aria-label', 'Данные устарели')
    // Title tooltip present
    expect(getByTitle('Источник устарел — показаны последние известные цены')).toBeInTheDocument()
  })

  it('omits stale badge when isStale=false', () => {
    const { container } = render(<ProductCard {...defaultProps()} />)
    expect(container.querySelector('.card-stale-badge')).not.toBeInTheDocument()
  })

  it('applies card-tint-red class for red product', () => {
    const props = { ...defaultProps(), product: makeProduct({ type: 'red' }) }
    const { container } = render(<ProductCard {...props} />)
    expect(container.querySelector('.card-vertical.card-tint-red')).toBeInTheDocument()
  })

  it('shows discount badge when oldPrice > currentPrice', () => {
    const { container } = render(<ProductCard {...defaultProps()} />)
    const discount = container.querySelector('.card-discount')
    expect(discount).toBeInTheDocument()
    // (170 - 102) / 170 = 0.4 → 40%
    expect(discount).toHaveTextContent('-40%')
  })

  it('hides discount badge when prices match (no discount)', () => {
    const props = {
      ...defaultProps(),
      product: makeProduct({ oldPrice: 0, currentPrice: 100 }),
    }
    const { container } = render(<ProductCard {...props} />)
    expect(container.querySelector('.card-discount')).not.toBeInTheDocument()
  })
})
