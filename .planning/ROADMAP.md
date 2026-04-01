# Roadmap: VkusVill Sale Monitor

**Created:** 2026-03-30
**Current Milestone:** v1.5 History Search & Polish

## Milestones

- ✅ **v1.0 Bug Fix & Stability** — Phases 1-9 (shipped 2026-03-31)
- ✅ **v1.1 Testing & QA** — Phases 10-12, 71 tests (shipped 2026-03-31)
- ✅ **v1.2 Price History** — Phases 13-18 (shipped 2026-04-01)
- ✅ **v1.3 Performance & Optimization** — Phases 19-20 (shipped 2026-04-01)
- ✅ **v1.4 Proxy Centralization** — Phases 21-23 (shipped 2026-04-01)
- 🚧 **v1.5 History Search & Polish** — Phases 24-26 (in progress)

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

<details>
<summary>✅ v1.4 Proxy Centralization (Phases 21-23) — SHIPPED 2026-04-01</summary>

See: `.planning/milestones/v1.4-ROADMAP.md`

</details>

### Phase 24: History Search — Exact Name Fix

**Goal:** Fix search to handle special characters (non-breaking spaces, Unicode quotes) so copy-pasted product names from VkusVill work.

**Requirements:** SRCH-01

**Success criteria:**
1. Copying exact product name from VkusVill.ru and pasting into search returns the product
2. Non-breaking spaces (U+00A0) treated as regular spaces in search
3. All quote variants (`"` `"` `«` `»`) treated equivalently
4. Search works for all products (including those with 0 sale count)

---

### Phase 25: History Search — Fuzzy/Typo-Tolerant

**Goal:** Add fuzzy search so misspellings like "цезерь" still find "Цезарь" products.

**Requirements:** SRCH-02

**Success criteria:**
1. Misspelled Cyrillic queries return relevant results (e.g. "цезерь" → "Цезарь")
2. Search performance stays under 500ms for 16K product catalog
3. Single-character typos always find the correct product
4. Partial word matching works (e.g. "цезар" finds "Цезарь")

---

### Phase 26: History Cards — Product Image Population

**Goal:** Populate missing product images for catalog products so search results show real photos instead of 📦 placeholders.

**Requirements:** SRCH-03

**Success criteria:**
1. Products found via search show actual product images, not 📦 placeholder
2. Image URLs are cached in product_catalog for subsequent loads
3. No scraping required — use VkusVill CDN URL pattern if possible
4. Graceful fallback to 📦 if image cannot be resolved

## Progress

| Phase | Milestone | Status | Completed |
|-------|-----------|--------|-----------|
| 1-9 | v1.0 | ✅ Complete | 2026-03-31 |
| 10-12 | v1.1 | ✅ Complete | 2026-03-31 |
| 13-18 | v1.2 | ✅ Complete | 2026-04-01 |
| 19-20 | v1.3 | ✅ Complete | 2026-04-01 |
| 21 | v1.4 | ✅ Complete | 2026-04-01 |
| 22 | v1.4 | ✅ Complete | 2026-04-01 |
| 23 | v1.4 | ✅ Complete | 2026-04-01 |
| 24 | v1.5 | ✅ Complete | 2026-04-01 |
| 25 | v1.5 | ✅ Complete | 2026-04-01 |
| 26 | v1.5 | ✅ Complete | 2026-04-01 |
