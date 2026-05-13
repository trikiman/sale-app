// v1.26 Phase 83 Plan 83-03: extracted from App.jsx to enable snapshot
// tests pinning the two banner variants per style guide v2
// "State Patterns > Stale" rules + Phase 84 refactor target.
//
// Contract:
// - staleAll truthy -> prominent bordered card with per-source ages +
//   estimatedRecoveryS (v1.24 UX-STALE-02 pool-outage case)
// - dataStale && !staleAll -> thin yellow line with per-color ages
//   (v1.22 UX-COPY-01 "Источники устарели" rescope)
// - neither -> null (nothing rendered)
//
// Snapshot tests: miniapp/src/__tests__/StaleBanner.test.jsx

export default function StaleBanner({ dataStale, staleAll, staleColorLabels = [] }) {
  if (staleAll) {
    const recoveryMinutes = Math.round((staleAll.estimatedRecoveryS || 180) / 60)
    return (
      <div
        className="stale-banner-prominent anim-scale"
        role="status"
        aria-live="polite"
      >
        <span className="stale-banner-prominent-icon">⏳</span>
        <div className="stale-banner-prominent-body">
          <strong className="stale-banner-prominent-title">Данные устарели</strong>
          <span className="stale-banner-prominent-sources">
            Источники{staleColorLabels.length ? `: ${staleColorLabels.join(', ')}` : ''}
          </span>
          <span className="stale-banner-prominent-hint">
            Показаны последние известные цены. Обновление через ~{recoveryMinutes} мин.
          </span>
        </div>
      </div>
    )
  }

  if (dataStale) {
    return (
      <div
        className="mt-2 px-4 py-2 rounded-xl bg-yellow-500/20 border border-yellow-500/50 text-yellow-300 text-center text-xs anim-scale"
      >
        ⚠️ Источники устарели{staleColorLabels.length ? `: ${staleColorLabels.join(', ')}` : ''} — товары и цены могут не совпадать с сайтом
      </div>
    )
  }

  return null
}
