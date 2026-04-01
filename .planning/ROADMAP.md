# Roadmap: VkusVill Sale Monitor

**Created:** 2026-03-30
**Current Milestone:** v1.4 Proxy Centralization

## Milestones

- ✅ **v1.0 Bug Fix & Stability** — Phases 1-9 (shipped 2026-03-31)
- ✅ **v1.1 Testing & QA** — Phases 10-12, 71 tests (shipped 2026-03-31)
- ✅ **v1.2 Price History** — Phases 13-18 (shipped 2026-04-01)
- ✅ **v1.3 Performance & Optimization** — Phases 19-20 (shipped 2026-04-01)
- ◆ **v1.4 Proxy Centralization** — Phases 21-23

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

<details>
<summary>✅ v1.3 Performance & Optimization (Phases 19-20) — SHIPPED 2026-04-01</summary>

See: `.planning/milestones/v1.3-ROADMAP.md`

</details>

### Phase 21: Backend Proxy Unification

**Goal:** Make ProxyManager the single gateway for all backend VkusVill HTTP requests.

**Requirements:** IMG-01, DETAIL-01, INFRA-01

**Success criteria:**
1. `/api/img` uses ProxyManager rotation (no more `SOCKS_PROXY` env var)
2. Product detail fetch uses ProxyManager as primary path (direct → proxy fallback preserved)
3. ProxyManager is imported and used consistently across all backend VkusVill-facing code
4. Existing functionality works unchanged (images load, details load)

---

### Phase 22: Frontend Image Routing

**Goal:** Route detail gallery images through backend proxy instead of direct browser load.

**Requirements:** IMG-02

**Success criteria:**
1. `ProductDetail.jsx` routes all `img.vkusvill.ru` images through `/api/img` proxy
2. Gallery thumbnails and main image both proxy correctly
3. Fallback behavior preserved (if proxy fails, image hides gracefully)
4. No visible performance regression for users

---

### Phase 23: Cart & Login Proxy Integration

**Goal:** Integrate ProxyManager into Cart API and Login flow.

**Requirements:** CART-04, LOGIN-01

**Success criteria:**
1. Cart API (`vkusvill_api.py`) uses ProxyManager for all VkusVill API calls
2. Login flow passes ProxyManager proxy to Chrome `--proxy-server`
3. Cart add/remove operations work through proxy rotation
4. Login SMS flow works through proxy (test with caution — 4 SMS/day limit)

## Progress

| Phase | Milestone | Status | Completed |
|-------|-----------|--------|-----------|
| 1-9 | v1.0 | ✅ Complete | 2026-03-31 |
| 10-12 | v1.1 | ✅ Complete | 2026-03-31 |
| 13-18 | v1.2 | ✅ Complete | 2026-04-01 |
| 19-20 | v1.3 | ✅ Complete | 2026-04-01 |
| 21 | v1.4 | ○ Pending | — |
| 22 | v1.4 | ○ Pending | — |
| 23 | v1.4 | ○ Pending | — |
