# Phase 19: Rendering & Load Speed - Context

**Gathered:** 2026-04-01
**Status:** Ready for planning

<domain>
## Phase Boundary

Optimize rendering performance and tablet/mobile UX for the existing product grid, API responses, and image loading. **Desktop experience must remain completely unchanged** — all optimizations target tablets and mobile devices via CSS media queries or JS device detection.

</domain>

<decisions>
## Implementation Decisions

### Backdrop-filter Strategy (PERF-12)
- **D-01:** Remove `backdrop-filter: blur()` on cards and non-critical elements for tablets/mobile only. Desktop keeps all blur effects.
- **D-02:** Use CSS media queries (`max-width` or `pointer: coarse`) to conditionally disable backdrop-filter — no JS needed for this.

### Product Detail on Tablets (PERF-11)
- **D-03:** On tablets, product detail opens as a full-page view instead of the overlay drawer. Desktop keeps the existing drawer behavior.
- **D-04:** Use a width-based media query or `navigator.maxTouchPoints` to detect tablet — keep implementation simple.

### Image Sizing (PERF-09)
- **D-05:** Investigate if VkusVill CDN URLs support resize params. If yes, request smaller images on mobile. If not, rely on CSS `max-width` and existing `loading="lazy"`.
- **D-06:** Agent's discretion on implementation — user doesn't need to weigh in.

### Device Detection & Reduced Animations (PERF-05, PERF-10)
- **D-07:** Use `prefers-reduced-motion` media query to disable/simplify CSS animations for users who request it.
- **D-08:** iPad gets mobile-optimized layout (2-col grid) via CSS media query — no JS detection needed.
- **D-09:** Agent's discretion on the threshold for "low-power device" — reasonable defaults are fine.

### API Compression (PERF-08)
- **D-10:** Add GZip middleware to FastAPI backend. This is invisible to users — just faster data transfer.

### Agent's Discretion
- Image sizing approach (D-05, D-06)
- Low-power device threshold for reduced animations (D-09)
- Specific CSS breakpoints for tablet detection
- All implementation details — user trusts agent's judgment

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

No external specs — requirements fully captured in decisions above.

### Requirements
- `.planning/REQUIREMENTS.md` — PERF-02, 04, 05, 08, 09, 10, 11, 12

### Codebase
- `miniapp/src/App.jsx` — 59KB monolith, ProductCard with memo(), pagination (CARDS_PER_PAGE=24), IntersectionObserver infinite scroll
- `miniapp/src/index.css` — 59KB, 9 backdrop-filter instances, 60+ transitions, CSS animations (replaced Framer Motion)
- `miniapp/src/ProductDetail.jsx` — 9KB, overlay drawer component
- `backend/main.py` — FastAPI server, only CORS middleware (no gzip)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `ProductCard` — already `memo()`'d with custom comparator, well-optimized
- CSS animation classes (`.anim-fade`, `.anim-slide-down`, etc.) — already replaced Framer Motion
- `IntersectionObserver` for infinite scroll — can be extended for lazy image loading
- `lazy()` + `Suspense` — already used for HistoryPage/HistoryDetail code splitting

### Established Patterns
- CSS-in-`index.css` — no CSS modules, all global styles
- `data-theme` attribute on `<html>` for dark/light theme switching
- VkusVill CDN images loaded directly with `referrerPolicy="no-referrer"`

### Integration Points
- `backend/main.py` — add GZipMiddleware from `starlette.middleware.gzip`
- `miniapp/src/index.css` — add `@media` queries for tablet/reduced-motion
- `miniapp/src/App.jsx` — conditional full-page detail for tablets
- `miniapp/src/ProductDetail.jsx` — full-page mode variant

</code_context>

<specifics>
## Specific Ideas

**User constraint:** "This all will not touch PC website" — desktop must see zero visual changes. All optimizations are tablet/mobile-only via media queries or device detection.

**User trust:** User deferred all technical decisions to agent. Keep changes invisible on desktop, focus on making iPad/tablet smoother.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 19-rendering-load-speed*
*Context gathered: 2026-04-01*
