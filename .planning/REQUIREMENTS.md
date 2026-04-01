# Requirements: v1.3 Performance & Optimization

## Goals
Eliminate lag on mobile/tablet devices without regressing desktop experience.

## Requirements

### Load Performance
- [ ] **PERF-01**: Page shows content within 2 seconds on mobile (no blank screen)
- [ ] **PERF-02**: Product grid is interactive within 3 seconds on iPad/mobile
- [ ] **PERF-03**: Only visible cards render in the DOM (virtualized or paginated)

### Animation Performance
- [ ] **PERF-04**: No jank/stutter when scrolling through product grid on iPad
- [ ] **PERF-05**: Animations are device-aware (reduced on low-power devices)

### Bundle Optimization
- [ ] **PERF-06**: Main JS bundle under 100KB gzipped (currently 116KB)
- [ ] **PERF-07**: Framer Motion usage optimized or replaced for card grid

### API Optimization
- [ ] **PERF-08**: API response compressed with gzip
- [ ] **PERF-09**: Product images use appropriate sizing (not full-res on mobile)

## Out of Scope
- Server-side rendering (SSR) — overkill for family app
- Service worker / offline mode — always-online use case
- CDN for API — single EC2 is fine for 5 users

## Traceability

| Req | Phase | Status |
|-----|-------|--------|
| PERF-01 | 19 | Pending |
| PERF-02 | 19 | Pending |
| PERF-03 | 19 | Pending |
| PERF-04 | 20 | Pending |
| PERF-05 | 20 | Pending |
| PERF-06 | 20 | Pending |
| PERF-07 | 20 | Pending |
| PERF-08 | 19 | Pending |
| PERF-09 | 19 | Pending |
