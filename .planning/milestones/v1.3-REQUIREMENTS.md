# Requirements: v1.3 Performance & Optimization

## Goals
Eliminate lag on mobile/tablet devices without regressing desktop experience.

## Requirements

### Load Performance
- [x] **PERF-01**: Page shows content within 2 seconds on mobile (no blank screen)
- [x] **PERF-02**: Product grid is interactive within 3 seconds on iPad/mobile
- [x] **PERF-03**: Only visible cards render in the DOM (virtualized or paginated)

### Animation Performance
- [x] **PERF-04**: No jank/stutter when scrolling through product grid on iPad
- [x] **PERF-05**: Animations are device-aware (reduced on low-power devices)

### Bundle Optimization
- [x] **PERF-06**: Main JS bundle under 100KB gzipped (achieved: 77KB)
- [x] **PERF-07**: Framer Motion replaced with CSS animations (0 bytes)

### API Optimization
- [x] **PERF-08**: API response compressed with gzip
- [x] **PERF-09**: Product images use appropriate sizing (not full-res on mobile)

### iPad/Tablet UX (added from user feedback 2026-04-01)
- [x] **PERF-10**: iPad detected and given mobile-optimized layout (2-col grid, no backdrop-filter)
- [x] **PERF-11**: Product detail opens as full page, not overlay drawer (less janky on tablets)
- [x] **PERF-12**: backdrop-filter: blur() removed or disabled on cards (GPU bottleneck)

## Out of Scope
- Server-side rendering (SSR) — overkill for family app
- Service worker / offline mode — always-online use case
- CDN for API — single EC2 is fine for 5 users

## Traceability

| Req | Phase | Status |
|-----|-------|--------|
| PERF-01 | pre-phase | ✅ Done (async script + skeleton) |
| PERF-02 | 19 | ✅ Done (decoding=async, containment, 2-col grid) |
| PERF-03 | pre-phase | ✅ Done (24-card pagination) |
| PERF-04 | 19 | ✅ Done (backdrop-filter removed, CSS containment) |
| PERF-05 | 19 | ✅ Done (prefers-reduced-motion media query) |
| PERF-06 | pre-phase | ✅ Done (77KB gzip) |
| PERF-07 | pre-phase | ✅ Done (FM removed) |
| PERF-08 | 19 | ✅ Done (GZipMiddleware, min 500 bytes) |
| PERF-09 | 19 | ✅ Done (CSS containment, decoding=async) |
| PERF-10 | 19 | ✅ Done (pointer:coarse media query, 2-col grid) |
| PERF-11 | 19 | ✅ Done (full-page detail on touch devices) |
| PERF-12 | 19 | ✅ Done (8 selectors, backdrop-filter:none on coarse) |
