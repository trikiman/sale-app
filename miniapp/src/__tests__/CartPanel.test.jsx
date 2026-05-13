// v1.26 Phase 83 Plan 83-03 (TEST-02): pins CartPanel row rendering.
//
// Regression targets:
// - v1.23 UX-CART-01: dedicated always-visible 🗑 trash button per row
//   (aria-label="Удалить из корзины"). Phase 84 refactor must not
//   accidentally hide or rename the button.
// - v1.22 pattern: "🗑 Очистить" header action when items.length > 0
// - out-of-stock cart-alert-red + low-stock cart-alert-yellow banners

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, waitFor } from '@testing-library/react'
import CartPanel from '../CartPanel'

const mockCartResponse = (items = [], overrides = {}) => ({
  ok: true,
  json: async () => ({
    items,
    items_count: items.length,
    total_price: items.reduce((sum, it) => sum + (it.price || 0) * (it.quantity || 0), 0),
    source_unavailable: false,
    ...overrides,
  }),
})

const aCartItem = (overrides = {}) => ({
  id: 33215,
  name: 'Milk 1L',
  price: 102,
  old_price: 170,
  quantity: 2,
  unit: 'шт',
  step: 1,
  koef: 1,
  max_q: 10,
  can_buy: true,
  image: '',
  ...overrides,
})

describe('CartPanel snapshot', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('returns null when isOpen=false (not mounted)', () => {
    const { container } = render(
      <CartPanel isOpen={false} onClose={() => {}} userId="guest_abc" />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders row with trash button when cart has items (v1.23 UX-CART-01)', async () => {
    fetch.mockResolvedValueOnce(mockCartResponse([aCartItem()]))

    const { container, findByLabelText } = render(
      <CartPanel isOpen={true} onClose={() => {}} userId="guest_abc" />
    )

    // v1.23 UX-CART-01: always-visible remove-row trash button
    const trashButton = await findByLabelText('Удалить из корзины')
    expect(trashButton).toBeInTheDocument()
    expect(trashButton).toHaveTextContent('🗑')

    // Quantity controls still render
    await waitFor(() => {
      expect(container.querySelector('.cart-qty-controls')).toBeInTheDocument()
    })

    expect(container.querySelector('.cart-item')).toMatchSnapshot()
  })

  it('renders header "🗑 Очистить" button when cart has items', async () => {
    fetch.mockResolvedValueOnce(mockCartResponse([aCartItem()]))

    const { findByTitle } = render(
      <CartPanel isOpen={true} onClose={() => {}} userId="guest_abc" />
    )

    const clearButton = await findByTitle('Очистить всю корзину')
    expect(clearButton).toBeInTheDocument()
    expect(clearButton).toHaveClass('cart-clear-btn')
  })

  it('renders "Корзина пуста" when cart is empty', async () => {
    fetch.mockResolvedValueOnce(mockCartResponse([]))

    const { findByText } = render(
      <CartPanel isOpen={true} onClose={() => {}} userId="guest_abc" />
    )

    const empty = await findByText('Корзина пуста')
    expect(empty).toBeInTheDocument()
  })

  it('renders out-of-stock alert when items have can_buy=false', async () => {
    fetch.mockResolvedValueOnce(
      mockCartResponse([aCartItem({ can_buy: false })])
    )

    const { findByText } = render(
      <CartPanel isOpen={true} onClose={() => {}} userId="guest_abc" />
    )

    // At least one item out of stock → red alert banner
    const alert = await findByText(/закончил/)
    expect(alert).toBeInTheDocument()
    expect(alert).toHaveClass('cart-alert')
    expect(alert).toHaveClass('cart-alert-red')
  })

  it('renders low-stock alert when items have max_q <= 3', async () => {
    fetch.mockResolvedValueOnce(
      mockCartResponse([aCartItem({ max_q: 2 })])
    )

    const { findByText } = render(
      <CartPanel isOpen={true} onClose={() => {}} userId="guest_abc" />
    )

    const alert = await findByText(/заканчива/)
    expect(alert).toBeInTheDocument()
    expect(alert).toHaveClass('cart-alert-yellow')
  })
})
