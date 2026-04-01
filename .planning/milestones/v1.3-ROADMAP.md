# Roadmap: VkusVill Sale Monitor

**Created:** 2026-03-30
**Current Milestone:** v1.3 Performance & Optimization

## Milestones

- ✅ **v1.0 Bug Fix & Stability** — Phases 1-9 (shipped 2026-03-31)
- ✅ **v1.1 Testing & QA** — Phases 10-12, 71 tests (shipped 2026-03-31)
- ✅ **v1.2 Price History** — Phases 13-18 (shipped 2026-04-01)
- 🚧 **v1.3 Performance & Optimization** — Phases 19-20 (in progress)

## Phases

<details>
<summary>✅ v1.0 Bug Fix & Stability (Phases 1-9) — SHIPPED 2026-03-31</summary>

See: `.planning/milestones/v1.0-ROADMAP.md`

</details>

<details>
<summary>✅ v1.1 Testing & QA (Phases 10-12) — SHIPPED 2026-03-31</summary>

See: `.planning/milestones/v1.1-ROADMAP.md`

</details>

<details>
<summary>✅ v1.2 Price History (Phases 13-18) — SHIPPED 2026-04-01</summary>

See: `.planning/milestones/v1.2-ROADMAP.md`

</details>

### 🚧 v1.3 Performance & Optimization (In Progress)

| # | Phase | Goal | Requirements | Status |
|---|-------|------|--------------|--------|
| 19 | Rendering & Load Speed | Virtualize grid, optimize API, lazy images | PERF-01..03, 08, 09 | Pending |
| 20 | Bundle & Animation | Replace heavy Framer Motion, reduce bundle, device-aware animations | PERF-04..07 | Pending |

---

## Phase Details

### Phase 19: Rendering & Load Speed
**Goal:** Virtualize grid, optimize API responses, lazy-load images, fix iPad/tablet UX
**Requirements:** PERF-02, PERF-04, PERF-05, PERF-08, PERF-09, PERF-10, PERF-11, PERF-12
**UI hint:** yes — performance optimization of existing pages

**Success criteria:**
1. Product grid interactive within 3s on iPad/mobile
2. No jank/stutter scrolling product grid on iPad
3. Animations device-aware (reduced on low-power devices)
4. API responses gzip-compressed
5. Product images use appropriate sizing for device
6. iPad gets mobile-optimized layout (2-col grid, no backdrop-filter)
7. Product detail opens as full page on tablets (not overlay drawer)
8. backdrop-filter: blur() removed or disabled on cards

**Files likely affected:**
- `miniapp/src/App.jsx` — layout logic, device detection
- `miniapp/src/index.css` — backdrop-filter removal, responsive tweaks
- `miniapp/src/ProductDetail.jsx` — full-page mode for tablets
- `backend/main.py` — gzip middleware

---

### Phase 20: Bundle & Animation
**Goal:** Replace heavy Framer Motion with CSS animations, reduce bundle, device-aware animations
**Requirements:** PERF-04, PERF-05, PERF-06, PERF-07
**UI hint:** yes — animation replacement

**Success criteria:**
1. Framer Motion fully replaced with CSS animations
2. Main JS bundle under 100KB gzipped
3. Animations detect device capability and reduce on low-power
4. No visual regression — animations feel smooth

**Files likely affected:**
- `miniapp/src/App.jsx` — animation replacements
- `miniapp/src/index.css` — CSS animations
- `miniapp/package.json` — remove framer-motion dependency

## Progress

| Phase | Milestone | Status | Completed |
|-------|-----------|--------|-----------|
| 1-9 | v1.0 | ✅ Complete | 2026-03-31 |
| 10-12 | v1.1 | ✅ Complete | 2026-03-31 |
| 13-18 | v1.2 | ✅ Complete | 2026-04-01 |
| 19 | v1.3 | 🚧 In Progress | — |
| 20 | v1.3 | ⏳ Pending | — |
