// v1.26 Phase 83 Plan 83-03 (TEST-02): pins the two stale-banner
// variants + empty-fresh case.
//
// Regression targets:
// - v1.22 UX-COPY-01: thin yellow line reads "Источники устарели"
//   (not "Данные устарели — conflicts with header Обновлено: HH:MM)
// - v1.24 UX-STALE-02: prominent bordered card shown only when all 3
//   sources stale, with ⏳ icon + estimatedRecoveryS-derived hint
// - State Patterns > Stale compliance: role="status", aria-live="polite"

import { describe, it, expect } from 'vitest'
import { render } from '@testing-library/react'
import StaleBanner from '../StaleBanner'

describe('StaleBanner snapshot', () => {
  it('renders nothing when data is fresh', () => {
    const { container } = render(
      <StaleBanner dataStale={false} staleAll={null} staleColorLabels={[]} />
    )
    expect(container.firstChild).toBeNull()
  })

  it('renders thin yellow banner when dataStale && !staleAll (partial staleness)', () => {
    const { container } = render(
      <StaleBanner
        dataStale={true}
        staleAll={null}
        staleColorLabels={['🟢 7 мин', '🔴 9 мин']}
      />
    )
    const banner = container.firstChild
    expect(banner).toBeInTheDocument()
    // v1.22 UX-COPY-01: copy rescoped from "Данные устарели" to
    // "Источники устарели" (plural, with per-color ages inline).
    expect(banner).toHaveTextContent('Источники устарели')
    expect(banner).toHaveTextContent('🟢 7 мин')
    expect(banner).toHaveTextContent('🔴 9 мин')
    // Style guide v2 thin-line pattern: anim-scale + yellow variant
    expect(banner).toHaveClass('anim-scale')
    expect(banner.className).toMatch(/bg-yellow-500/)

    expect(banner).toMatchSnapshot()
  })

  it('renders prominent bordered card when staleAll is set (pool-outage case)', () => {
    const { container } = render(
      <StaleBanner
        dataStale={true}
        staleAll={{ ageMinutesMax: 12, oldestColor: 'green', estimatedRecoveryS: 180 }}
        staleColorLabels={['🟢 12 мин', '🔴 11 мин', '🟡 10 мин']}
      />
    )
    const banner = container.firstChild
    expect(banner).toBeInTheDocument()
    expect(banner).toHaveClass('stale-banner-prominent')
    // A11y contract per style guide v2 State Patterns > Stale
    expect(banner).toHaveAttribute('role', 'status')
    expect(banner).toHaveAttribute('aria-live', 'polite')

    // v1.24 UX-STALE-02 copy
    expect(banner).toHaveTextContent('Данные устарели')
    expect(banner).toHaveTextContent('⏳')
    // Recovery hint: estimatedRecoveryS=180 -> ~3 мин
    expect(banner).toHaveTextContent('через ~3 мин')
    // Per-source ages inline
    expect(banner).toHaveTextContent('🟢 12 мин')

    expect(banner).toMatchSnapshot()
  })

  it('falls back to 3-minute recovery hint when estimatedRecoveryS is missing', () => {
    const { container } = render(
      <StaleBanner
        dataStale={true}
        staleAll={{ ageMinutesMax: 5 }}
        staleColorLabels={[]}
      />
    )
    // Default is 180s -> Math.round(180/60)=3
    expect(container.firstChild).toHaveTextContent('через ~3 мин')
  })

  it('falls back to bare "Источники" label when staleColorLabels is empty', () => {
    const { container } = render(
      <StaleBanner
        dataStale={true}
        staleAll={{ estimatedRecoveryS: 300 }}
        staleColorLabels={[]}
      />
    )
    // No ":" separator when labels list is empty
    const sourcesSpan = container.querySelector('.stale-banner-prominent-sources')
    expect(sourcesSpan).toHaveTextContent('Источники')
    expect(sourcesSpan.textContent.trim()).toBe('Источники')
  })

  it('staleAll takes precedence over dataStale (prominent wins over thin line)', () => {
    const { container } = render(
      <StaleBanner
        dataStale={true}
        staleAll={{ estimatedRecoveryS: 240 }}
        staleColorLabels={['🟢 15 мин']}
      />
    )
    expect(container.querySelector('.stale-banner-prominent')).toBeInTheDocument()
    // Thin-line yellow variant should NOT render concurrently
    expect(container.querySelector('.bg-yellow-500\\/20')).not.toBeInTheDocument()
  })
})
