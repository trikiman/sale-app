// v1.26 Phase 83 Plan 83-03 (TEST-02): pins the "empty state vs staleAll
// with preserved products" UX decision. Per v1.24 UX-STALE-02, when the
// pool collapses and sources go stale, the client preserves the last
// known product list and shows the prominent banner — NOT the empty-list
// message "В этой категории пока нет товаров".
//
// v1.26 UX-EMPTY-01 (Phase 85) introduces emptyReason field on
// /api/products for the fresh-deploy edge case. This test pins the
// CURRENT rendering logic so Phase 85's changes stay additive.
//
// This is a component-composition test — it renders StaleBanner + a
// minimal consumer that mirrors App.jsx's decision logic. Full App.jsx
// integration is tested in Phase 84 snapshot coverage.

import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import StaleBanner from '../StaleBanner'

// Mirrors the state-pattern decision App.jsx makes — extracted here so
// Phase 84 refactor can't silently break the "preserved products" vs
// "empty state" distinction.
function ProductAreaPreview({ products, dataStale, staleAll, staleColorLabels = [] }) {
  return (
    <div data-testid="area">
      <StaleBanner
        dataStale={dataStale}
        staleAll={staleAll}
        staleColorLabels={staleColorLabels}
      />
      {products.length === 0 ? (
        <div className="product-empty-state" data-testid="empty">
          В этой категории пока нет товаров
        </div>
      ) : (
        <div data-testid="products" className="product-grid">
          {products.map((p) => (
            <div key={p.id} data-product-id={p.id}>{p.name}</div>
          ))}
        </div>
      )}
    </div>
  )
}

const sampleProducts = [
  { id: 1, name: 'A' },
  { id: 2, name: 'B' },
]

describe('empty-state vs staleAll rendering', () => {
  it('renders products + no banner when data is fresh and list is populated', () => {
    const { queryByTestId, queryByText } = render(
      <ProductAreaPreview
        products={sampleProducts}
        dataStale={false}
        staleAll={null}
      />
    )
    expect(queryByTestId('products')).toBeInTheDocument()
    expect(queryByTestId('empty')).not.toBeInTheDocument()
    // No banner markup
    expect(queryByText('Источники устарели', { exact: false })).not.toBeInTheDocument()
    expect(queryByText('Данные устарели')).not.toBeInTheDocument()
  })

  it('renders empty-state + no banner when fresh but list is filtered to zero', () => {
    const { queryByTestId, queryByText } = render(
      <ProductAreaPreview products={[]} dataStale={false} staleAll={null} />
    )
    expect(queryByTestId('empty')).toBeInTheDocument()
    expect(queryByText('Данные устарели')).not.toBeInTheDocument()
  })

  it('renders staleAll banner + preserved products (v1.24 UX-STALE-02 pool-outage case)', () => {
    const { queryByTestId, container } = render(
      <ProductAreaPreview
        products={sampleProducts}
        dataStale={true}
        staleAll={{ estimatedRecoveryS: 240, ageMinutesMax: 15 }}
        staleColorLabels={['🟢 15 мин', '🔴 14 мин', '🟡 12 мин']}
      />
    )
    // Preserved products remain visible
    expect(queryByTestId('products')).toBeInTheDocument()
    expect(queryByTestId('empty')).not.toBeInTheDocument()
    // Prominent banner rendered
    expect(container.querySelector('.stale-banner-prominent')).toBeInTheDocument()
  })

  it('renders staleAll banner + empty-state when pool is dead AND no preserved products (fresh deploy)', () => {
    // This is the v1.25 QA-08 edge case + v1.26 UX-EMPTY-01 Phase 85
    // target. Current behavior: banner shows, empty-state shows under it.
    // Phase 85 will make the empty-state copy more precise, but the
    // banner-above-empty composition is locked here.
    const { queryByTestId, container } = render(
      <ProductAreaPreview
        products={[]}
        dataStale={true}
        staleAll={{ estimatedRecoveryS: 180 }}
        staleColorLabels={['🟢 9 мин', '🔴 9 мин', '🟡 9 мин']}
      />
    )
    expect(container.querySelector('.stale-banner-prominent')).toBeInTheDocument()
    expect(queryByTestId('empty')).toBeInTheDocument()
    expect(queryByTestId('products')).not.toBeInTheDocument()
  })
})
