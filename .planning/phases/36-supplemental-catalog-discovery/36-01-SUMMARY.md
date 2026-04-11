---
phase: 36-supplemental-catalog-discovery
plan: 01
subsystem: catalog-discovery
tags: [catalog, scraper, source-manifest, per-source-state]
requires:
  - phase: 36
    provides: Corrected source-by-source discovery model from discuss/plan
provides:
  - Catalog-root source manifest
  - Per-source temp discovery files
  - Source-state validation with expected/raw/unique counts
affects: [phase-37, discovery-data, admin-observability]
tech-stack:
  added: []
  patterns: [Catalog root source manifest, per-source JSON files, source-state validation]
key-files:
  created: [scrape_catalog_discovery.py]
  modified: []
key-decisions:
  - "Collection is tracked per source using that source's live count rather than one global sum"
  - "Successful runs rewrite source files to the freshly validated unique set; incomplete runs preserve accumulated progress"
patterns-established:
  - "Separate validity state from stored discovery progress"
  - "Treat duplicate IDs inside a source as non-blocking when raw collected cards still match the source total"
requirements-completed: [DATA-04]
completed: 2026-04-04
---

# Phase 36 Plan 01: Source Inventory And Per-Source Collection Summary

**A source-based discovery pipeline now scrapes VkusVill catalog sources into separate temp files and validates completion per source**

## Accomplishments

- Added `scrape_catalog_discovery.py` to discover sources from the live catalog root and collect them source-by-source
- Added `data/catalog_sources.json` and `data/catalog_discovery_state.json` as the Phase 36 source manifest and source-state contracts
- Added per-source temp files under `data/catalog_discovery_sources/`
- Implemented per-source validity using `expected_count`, `raw_collected_count`, `collected_count`, and `complete`
- Ran a full live discovery sweep across 46 sources and validated 45 stable/non-personalized sources to completion

## Notes

- The `set-vashi-skidki` source behaves as a personalized source with inconsistent live totals across browser-authenticated and unauthenticated scraper views, so it was treated as a non-blocking exception for stable-source completion.
- Duplicate product IDs can appear inside a single source while the source card total is still fully collected; the collector now records that difference without blocking source completion.

## Files Created/Modified

- `scrape_catalog_discovery.py` — source manifest discovery, per-source scraping, state persistence, and resume logic
- `data/catalog_sources.json` — live source manifest
- `data/catalog_discovery_state.json` — source-state validation contract
- `data/catalog_discovery_sources/*.json` — per-source temp artifacts

## Key Result

- Stable sources completed: `45`
- Personalized/non-blocking source with inconsistent totals: `1`
- Global unique discovered product IDs across source files: `10137`

## Task Commits

1. **Initial source-based collector** — `fdf5fc6` (`feat(36): add source-based catalog discovery`)
2. **Live-sweep stability fixes** — `27a8d73` (`fix(36): stabilize live catalog discovery sweep`)

---
*Phase: 36-supplemental-catalog-discovery*
*Completed: 2026-04-04*
