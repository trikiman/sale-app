# Phase 36: Supplemental Catalog Discovery - Research

**Researched:** 2026-04-04
**Domain:** Offline supplemental catalog discovery inside the existing VkusVill JSON-first scrape pipeline
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Supplemental discovery stays offline. Do not add runtime hybrid search or per-user remote search calls in this phase.
- Keep the current `scrape_categories.py` category crawl intact and add a separate supplemental discovery step/script for the missing-product path.
- Reuse the existing HTTP scraper style: low-concurrency requests, proxy-compatible transport, and no browser/login/SMS dependency.
- Drive discovery from a repo-tracked seed query set so refreshes are repeatable.
- Phase 36 writes a separate sidecar discovery artifact keyed by stable `product_id`, not directly into `category_db.json` or `product_catalog`.
- A discovered record is only valid if it includes a stable numeric VkusVill `product_id`.
- Existing downstream consumers should remain unchanged during this phase and continue reading the current catalog artifacts until Phase 37 merges the new discovery data.

### the agent's Discretion
- Exact filename and schema shape for the supplemental discovery artifact
- How seed queries are grouped, normalized, and paginated during a run
- The exact balance between targeted known-gap queries and broader exploratory seed coverage
- The precise HTTP endpoint/response parsing approach, as long as it stays offline and yields stable product IDs

### Deferred Ideas (OUT OF SCOPE)
- Runtime hybrid search fallback during user queries
- Merging discoveries into `category_db.json` / `product_catalog`
- Full parity verification against History search results and metrics dashboards
- Multi-subgroup DB fidelity beyond the existing single-subgroup `product_catalog` field
</user_constraints>

<research_summary>
## Summary

The best fit for Phase 36 is a separate, seed-driven HTTP discovery script that produces a sidecar artifact with stable product identities and discovery metadata. This preserves the current category crawl and keeps all runtime search paths local-first until Phase 37 intentionally merges the new data into the main catalog artifacts.

The current repo already has the right primitives for this approach: low-concurrency `aiohttp` scraping in `scrape_categories.py`, JSON artifact persistence, stable `product_id` extraction helpers, and admin background-run patterns in `backend/main.py`. The main risk is not transport or concurrency; it is identity quality. If discovery accepts rows without durable IDs or writes directly into `category_db.json`, the pipeline becomes noisy and hard to reason about.

**Primary recommendation:** Build `scrape_catalog_discovery.py` as a sidecar discovery job that reads `data/catalog_discovery_queries.json`, writes `data/catalog_discovery.json`, dedupes strictly by `product_id`, and emits summary counts for net-new discoveries without changing existing runtime consumers.
</research_summary>

<standard_stack>
## Standard Stack

The established libraries/tools for this phase inside the current repo:

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `aiohttp` | project-installed | Low-concurrency HTTP fetching for scrapers | Already used successfully in `scrape_categories.py` |
| `beautifulsoup4` | `>=4.12.0` | HTML parsing | Existing parser layer for catalog pages |
| `lxml` | `>=5.0.0` | Fast HTML parser backend | Already used by scraper parsing helpers |
| `ProxyManager` | local project helper | Proxy selection and resiliency | Existing central pattern for VkusVill-facing traffic |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` | stdlib | Artifact persistence | For `catalog_discovery_queries.json` and `catalog_discovery.json` |
| `pytest` | project test framework | Regression coverage | Artifact/schema/dedupe tests |
| `fastapi` | `>=0.109.0` | Optional admin run trigger | If Phase 36 exposes discovery via admin background route |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `aiohttp` + HTML/HTTP parsing | `nodriver` browser automation | Browser path is heavier, slower, and couples discovery to anti-bot/browser state |
| Sidecar discovery artifact | Direct writes to `category_db.json` | Faster short term, but unsafe before merge/conflict rules exist |
| Seed-driven queries | Blind exploratory crawl | Easier to start, but harder to reproduce and verify |

**Installation:**
```bash
pip install -r requirements.txt
```
</standard_stack>

<architecture_patterns>
## Architecture Patterns

### Recommended Project Structure
```text
data/
├── category_db.json
├── catalog_discovery_queries.json
└── catalog_discovery.json

backend/
├── main.py
└── test_catalog_discovery.py

scrape_catalog_discovery.py
```

### Pattern 1: Separate Discovery Sidecar
**What:** Write supplemental discoveries to a dedicated artifact instead of mutating the main catalog immediately.
**When to use:** When discovery quality and merge rules are still evolving.
**Example:**
```python
output = {
    "updated_at": now_iso,
    "seed_count": len(seed_queries),
    "discovered_count": len(products_by_id),
    "new_product_ids": sorted(products_by_id.keys()),
    "products": products_by_id,
}
with open(discovery_path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
```

### Pattern 2: Stable-ID-First Dedupe
**What:** Accept and merge discoveries strictly by VkusVill `product_id`; treat names and hints as secondary metadata.
**When to use:** Any time the same product can appear in multiple seed queries or result pages.
**Example:**
```python
existing = products_by_id.get(product_id, {})
products_by_id[product_id] = {
    "product_id": product_id,
    "name": candidate_name or existing.get("name", ""),
    "url": candidate_url or existing.get("url", ""),
    "image_url": candidate_image or existing.get("image_url", ""),
    "source_queries": sorted(set(existing.get("source_queries", [])) | {query}),
}
```

### Pattern 3: Seed-Driven Offline Refresh
**What:** Keep discovery inputs in a repo-tracked file and run them in batch.
**When to use:** When completeness needs to improve repeatably without runtime coupling.
**Example:**
```python
with open("data/catalog_discovery_queries.json", encoding="utf-8") as f:
    seeds = json.load(f)

queries = seeds["known_gaps"] + seeds["broad_seeds"]
for query in queries:
    await fetch_discovery_results(session, query)
```

### Anti-Patterns to Avoid
- **Name-only identity:** products can share similar names; `product_id` is the durable join key across the repo
- **Direct runtime dependency:** do not make `/api/history/products` or `scrape_merge.py` depend on discovery output in this phase
- **Browser-first discovery:** `nodriver` adds fragility and resource cost where existing low-concurrency HTTP may be enough
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Identity matching | Fuzzy name reconciliation | `product_id` extraction from URLs/results | Names drift; IDs are the stable local join key |
| Triggering discovery | New scheduler subsystem | Existing script + optional admin background-run pattern | Avoid extra orchestration complexity in discovery-only phase |
| Metadata merge policy | Early ad hoc writes into `category_db.json` | Sidecar artifact + explicit Phase 37 merge rules | Merge quality is a separate problem and needs explicit handling |
| Verification | Manual screenshot comparison only | Artifact tests + known-gap seed assertions | Repeatable checks matter for parity work |

**Key insight:** The hard part of this phase is not “how do we call another endpoint,” but “how do we discover more products without poisoning the local catalog before merge rules exist.”
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Accepting Unstable Product Identities
**What goes wrong:** Discovery records cannot be merged safely because the same product appears under inconsistent names or incomplete URLs.
**Why it happens:** Search-like sources often expose snippets before full canonical metadata.
**How to avoid:** Require stable numeric `product_id`; discard entries without it.
**Warning signs:** Discovery artifact contains rows with empty IDs or duplicate names under different pseudo-identifiers.

### Pitfall 2: Query Explosion Without Useful Coverage
**What goes wrong:** Discovery runs get slow and noisy, but still fail to improve the known parity gaps.
**Why it happens:** Broad exploratory queries are added without a maintained seed contract.
**How to avoid:** Separate `known_gaps` from `broad_seeds`, emit per-query stats, and verify target gaps first.
**Warning signs:** Run count increases but `new_product_ids` remains flat or mostly duplicates.

### Pitfall 3: Metadata Clobber Pressure
**What goes wrong:** Supplemental results tempt the implementation to overwrite richer category/group/subgroup data too early.
**Why it happens:** Discovery sources may return weaker metadata than the main category crawl.
**How to avoid:** Keep sidecar discovery isolated until Phase 37 defines merge precedence.
**Warning signs:** Discovery artifact is treated as a replacement rather than a candidate source.

### Pitfall 4: Runtime Coupling by Convenience
**What goes wrong:** The app starts depending on discovery output before it has stable merge semantics or test coverage.
**Why it happens:** Discovery data exists, so it is tempting to wire it straight into APIs.
**How to avoid:** Keep `scrape_merge.py`, `seed_product_catalog()`, and `/api/history/products` unchanged in Phase 36.
**Warning signs:** Discovery output is read by production endpoints or merge jobs before Phase 37 begins.
</common_pitfalls>

<code_examples>
## Code Examples

Verified patterns from the existing repo:

### Proxy-Aware Low-Concurrency Fetching
```python
# Source: scrape_categories.py pattern
sem = asyncio.Semaphore(MAX_CONCURRENT)
async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
    async with sem:
        html = await fetch_page(session, url)
```

### JSON Artifact Persistence
```python
# Source: scrape_categories.py / scrape_merge.py save pattern
with open(path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
```

### Background Admin Trigger Pattern
```python
# Source: backend/main.py admin runner pattern
threading.Thread(target=worker, daemon=True).start()
return {"started": True, "message": "catalog discovery started in background"}
```
</code_examples>

<validation_architecture>
## Validation Architecture

**Recommended validation loop for this phase:**
- Add `backend/test_catalog_discovery.py` for artifact-schema, stable-ID, seed-loading, and dedupe coverage
- Reuse `backend/test_categories.py` patterns for temp JSON files and parser fixtures
- Keep `/api/history/products` coverage in `backend/test_history_search.py` unchanged; discovery is upstream of runtime search in this phase

**Suggested commands:**
- Quick loop: `pytest backend/test_catalog_discovery.py -q`
- Broader loop: `pytest backend/test_catalog_discovery.py backend/test_categories.py -q`
- Full relevant suite: `pytest backend/test_catalog_discovery.py backend/test_categories.py backend/test_history_search.py -q`
</validation_architecture>

<sota_updates>
## State of the Art (2024-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Category-only local catalog crawl | Category crawl plus supplemental offline discovery | This milestone | Improves completeness without runtime search dependency |
| Manual screenshot parity checks | Repo-tracked seed queries + artifact assertions | This phase | Makes parity progress repeatable |
| Immediate DB/catalog mutation | Sidecar artifact before merge | This phase | Lowers data-corruption risk while discovery evolves |

**New patterns to consider:**
- Treat missing-product discovery as a batch ingest concern, not a search-UI concern
- Keep source-query provenance per product so later merge and metrics work can explain why a record exists

**Deprecated/outdated:**
- Assuming `scrape_categories.py` alone is sufficient for catalog completeness
- Using ad hoc screenshots as the only proof that parity improved
</sota_updates>

<open_questions>
## Open Questions

1. **What exact remote source shape is most reliable for discovery?**
   - What we know: existing codebase already handles VkusVill IDs from catalog URLs and prefers HTTP over browser where possible
   - What's unclear: the exact response/HTML shape of the supplemental discovery source the script will parse
   - Recommendation: resolve during execution by starting with one source path and designing the parser around stable ID extraction first

2. **Should Phase 36 expose an admin background trigger immediately or stay CLI-only?**
   - What we know: `backend/main.py` already has a background-run pattern for category scraping
   - What's unclear: whether admin-trigger convenience is worth touching backend orchestration in the same phase
   - Recommendation: include admin triggering only if it stays thin and does not auto-merge or expand runtime coupling
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- `.planning/phases/36-supplemental-catalog-discovery/36-CONTEXT.md` — locked decisions and phase boundary
- `scrape_categories.py` — current HTTP scraper patterns, product ID extraction, and JSON persistence
- `scrape_merge.py` — current enrichment flow from `category_db.json` into runtime sale JSON
- `database/sale_history.py` — `seed_product_catalog()` and `record_sale_appearances()` local catalog contracts
- `backend/main.py` — existing admin background-run pattern and local History search reliance on `product_catalog`
- `backend/test_categories.py` — current scraper/unit testing style
- `backend/test_history_search.py` — current local-catalog parity regression coverage

### Secondary (MEDIUM confidence)
- `.planning/codebase/CONVENTIONS.md` — confirms scraper/backend artifact and logging patterns
- `.planning/codebase/INTEGRATIONS.md` — confirms proxy and data-flow constraints
- `.planning/codebase/TESTING.md` — confirms repo testing conventions and gaps

### Tertiary (LOW confidence - needs validation)
- None — remaining uncertainty is about the exact discovery-source response shape, which Phase 36 execution must validate directly
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: offline HTTP discovery inside existing Python scraper pipeline
- Ecosystem: `aiohttp`, BeautifulSoup/lxml, JSON artifacts, FastAPI background-run pattern
- Patterns: sidecar artifact, seed-driven discovery, stable-ID dedupe, local-first runtime protection
- Pitfalls: unstable IDs, duplicate query noise, metadata clobber, runtime coupling

**Confidence breakdown:**
- Standard stack: HIGH — built from current repo dependencies and working scraper patterns
- Architecture: MEDIUM — local-first design is clear, but exact discovery-source parsing still needs implementation validation
- Pitfalls: HIGH — directly grounded in current pipeline structure and prior milestone boundaries
- Code examples: HIGH — based on current repo patterns rather than speculative new frameworks

**Research date:** 2026-04-04
**Valid until:** 2026-05-04
</metadata>

---

*Phase: 36-supplemental-catalog-discovery*
*Research completed: 2026-04-04*
*Ready for planning: yes*
