# Phase 36: Supplemental Catalog Discovery - Research

**Researched:** 2026-04-04
**Domain:** Source-by-source offline catalog collection from the live VkusVill catalog page
**Confidence:** MEDIUM

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Scrape every catalog tile/source from the VkusVill catalog page in this phase.
- Use each source page's live count only as that source's completion target.
- Do not sum source counts into one global total.
- Store separate temp files per source/category during collection.
- Keep already scraped items between incomplete runs.
- A source is valid only when a fresh run confirms `collected == expected` against the current live count.
- Failures and mismatches must be visible in the admin panel logs.
- Do not merge into `category_db.json` or `product_catalog` in this phase.
- Runtime search stays local-first; no hybrid runtime search.

### the agent's Discretion
- Exact source manifest filename and source-state filename
- Exact per-source file schema
- Exact retry and mismatch log fields
- Exact identity validation method for the preferred `product_id` key

### Deferred Ideas (OUT OF SCOPE)
- Merge all source files into one deduped discovery catalog
- Write discoveries into `category_db.json` or `product_catalog`
- Runtime parity verification on History search
- Hybrid runtime search fallback
</user_constraints>

<research_summary>
## Summary

Phase 36 should behave like a durable collection pipeline, not like a search-driven sampler. The right unit of work is the source/category page, because VkusVill already exposes a live count there. That gives a clear completion contract: a source is complete only when a fresh scrape of that source reaches the current live count shown on that source page.

The existing repo already has most of the mechanics needed: low-concurrency HTTP scraping in `scrape_categories.py`, JSON artifact persistence, page-by-page collection, and background admin-run/logging patterns in `backend/main.py`. The missing layer is source management: discovering all source tiles from the catalog root, scraping each source into its own temp file, preserving incremental progress across failures, and keeping an explicit source-state file that says which sources are complete and why others are not.

**Primary recommendation:** Build a source manifest plus per-source artifacts under `data/catalog_discovery_sources/`, keep a separate `data/catalog_discovery_state.json` for expected/collected/complete/error state, and only mark a source complete after a fresh run confirms the live count on that source page.
</research_summary>

<standard_stack>
## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `aiohttp` | project-installed | Low-concurrency HTTP fetching | Already used successfully in `scrape_categories.py` |
| `beautifulsoup4` | `>=4.12.0` | HTML parsing | Existing repo parser layer |
| `lxml` | `>=5.0.0` | Fast HTML parser backend | Already used by scraper parsing helpers |
| `ProxyManager` | local helper | Proxy rotation / resiliency | Existing central VkusVill traffic helper |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `json` | stdlib | Source manifests, source files, state files | Primary persistence format for this phase |
| `pytest` | project test framework | Artifact and orchestration coverage | For parser/state failure-handling tests |
| `fastapi` | `>=0.109.0` | Admin background-run trigger | For source-run orchestration and logs |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Source-by-source collection | Query-seed search discovery | Weaker completeness contract; search totals are query-specific, not source-complete |
| Separate files per source | One large temp collection file | Simpler merge later, but less robust during failures |
| HTTP collection | `nodriver` browser collection | Heavier and less reliable operationally for repeated source sweeps |

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
├── catalog_sources.json
├── catalog_discovery_state.json
└── catalog_discovery_sources/
   ├── gotovaya-eda.json
   ├── postnoe-i-vegetarianskoe.json
   └── ...

backend/
└── test_catalog_discovery.py

scrape_catalog_discovery.py
```

### Pattern 1: Source Manifest from Catalog Root
**What:** Scrape the catalog root page, enumerate all source tiles, and persist them to a manifest.
**When to use:** At the start of each discovery sweep, so source coverage follows the live site rather than a stale hardcoded list.
**Example:**
```python
manifest = {
    "updated_at": now_iso,
    "sources": [
        {
            "name": "Готовая еда",
            "slug": "gotovaya-eda",
            "url": "https://vkusvill.ru/goods/gotovaya-eda/",
        }
    ],
}
```

### Pattern 2: Per-Source Artifact with Incremental Progress
**What:** Keep one file per source. Preserve already scraped items across incomplete runs, but track completion separately.
**When to use:** Whenever robustness matters more than one-file convenience.
**Example:**
```python
source_file = {
    "source_name": "Готовая еда",
    "source_slug": "gotovaya-eda",
    "source_url": "https://vkusvill.ru/goods/gotovaya-eda/",
    "products": {
        "61483": {"product_id": "61483", "name": "Салат \"Цезарь\" ..."}
    }
}
```

### Pattern 3: Separate State File for Validity
**What:** Keep validity in a dedicated state file, not inferred from artifact existence.
**When to use:** Always, if incomplete runs are allowed to preserve progress.
**Example:**
```python
state["gotovaya-eda"] = {
    "expected_count": 1418,
    "collected_count": 1409,
    "complete": False,
    "last_error": "page 58 timeout",
    "last_success_at": None,
}
```

### Anti-Patterns to Avoid
- **Artifact existence = success:** wrong; a source file may be incomplete
- **Global sum from source counts:** wrong when sources overlap
- **Throwing away partial progress on every mismatch:** operationally expensive
- **Merging into the main local catalog in this phase:** violates the phase boundary
</architecture_patterns>

<dont_hand_roll>
## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Source inventory | Manual hardcoded source list | Catalog-root manifest scrape | The live site already exposes the current source set |
| Success state | Implicit “file exists” logic | Explicit per-source state file | Needed because partial files can survive failed runs |
| Identity choice | Blindly trust one key | Validate preferred `product_id` in tests and execution | The key needs evidence, not assumption |
| Operational visibility | Ad hoc console-only debugging | Existing admin status/log patterns in `backend/main.py` | The repo already has a workable operator surface |

**Key insight:** this phase needs durable collection semantics more than novel scraping logic.
</dont_hand_roll>

<common_pitfalls>
## Common Pitfalls

### Pitfall 1: Treating Overlap as a Counting Error
**What goes wrong:** The implementation tries to force all sources into one summed completeness model.
**Why it happens:** Source counts look additive at first glance.
**How to avoid:** Keep source completeness separate from global dedupe.
**Warning signs:** code adds multiple source counts together or reports one “global expected total”.

### Pitfall 2: Marking a Source Complete from Old Data
**What goes wrong:** A source remains marked valid even though the current live source count changed.
**Why it happens:** Validity is inferred from artifact presence or stale last-run data.
**How to avoid:** Only a fresh run that matches the current source count can set `complete = true`.
**Warning signs:** source file exists, but `last_verified_at` is old or `expected_count` is from a previous run.

### Pitfall 3: Losing Partial Progress on Failure
**What goes wrong:** A timeout late in pagination wipes out a mostly-complete source run.
**Why it happens:** The implementation rewrites source files only from fresh full runs.
**How to avoid:** Persist accumulated source items incrementally, but keep `complete = false` until validation passes.
**Warning signs:** repeated failures restart from zero and never converge.

### Pitfall 4: No Clear Failure Reason
**What goes wrong:** A source is incomplete, but the operator cannot tell whether it was timeout, parser drift, count mismatch, or identity issue.
**Why it happens:** Only raw stdout is kept, with no structured mismatch state.
**How to avoid:** Store `expected_count`, `collected_count`, `last_error`, `last_failed_page`, and retry info in source state and admin logs.
**Warning signs:** admin panel says “failed” with no actionable reason.
</common_pitfalls>

<code_examples>
## Code Examples

### Page-by-Page Collection Pattern
```python
# Source: existing scrape_categories.py pattern
for page_num in range(2, max_pages + 1):
    url = f"{source_url}?PAGEN_1={page_num}"
    async with sem:
        html = await fetch_page(session, url)
    if html is None:
        break
    products = _parse_products(html)
    if not products:
        break
```

### JSON Artifact Persistence Pattern
```python
# Source: existing scraper save pattern
with open(path, "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)
```

### Background Admin Runner Pattern
```python
# Source: backend/main.py categories runner
threading.Thread(target=worker, daemon=True).start()
return {"started": "catalog-discovery", "message": "Catalog discovery started"}
```
</code_examples>

<validation_architecture>
## Validation Architecture

**Recommended validation loop:**
- `backend/test_catalog_discovery.py` should cover:
  - source manifest extraction
  - per-source state transitions
  - incomplete-run persistence
  - fresh-run completion validation
  - preferred `product_id` identity extraction
- reuse temporary JSON-file patterns from `backend/test_categories.py`
- keep `backend/test_history_search.py` unchanged; Phase 36 must not modify runtime search

**Suggested commands:**
- Quick loop: `pytest backend/test_catalog_discovery.py -q`
- Broader loop: `pytest backend/test_catalog_discovery.py backend/test_categories.py -q`
- Full relevant suite: `pytest backend/test_catalog_discovery.py backend/test_categories.py backend/test_history_search.py -q`
</validation_architecture>

<sota_updates>
## State of the Art (2024-2026)

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Single local category crawl | Catalog-root source inventory plus per-source collection | This phase | Broader coverage and explicit per-source completeness |
| Implicit validity from artifact presence | Explicit source-state validation | This phase | Better operational correctness |
| One-pass scrape-or-fail mentality | Incremental source fill with strict completion gate | This phase | Better robustness under timeouts/proxy failures |

**New patterns to consider:**
- Treat each source as an independently verifiable collection job
- Keep progress and validity separate

**Deprecated/outdated:**
- Assuming one crawler output is enough to represent full catalog coverage
- Assuming category overlap makes per-source count tracking useless
</sota_updates>

<open_questions>
## Open Questions

1. **How stable is `product_id` across all source tiles?**
   - What we know: current catalog and search pages expose numeric IDs in product URLs
   - What's unclear: whether every special source tile page preserves that same pattern consistently
   - Recommendation: validate this explicitly during execution and test it

2. **Do all catalog tiles expose a trustworthy numeric count on their source page?**
   - What we know: normal source pages like `Готовая еда` and `Постное и вегетарианское` do
   - What's unclear: whether every source tile behaves the same, especially unusual/service-like tiles
   - Recommendation: treat missing/non-numeric counts as a source-level failure state, not silent success
</open_questions>

<sources>
## Sources

### Primary (HIGH confidence)
- `.planning/phases/36-supplemental-catalog-discovery/36-CONTEXT.md`
- `scrape_categories.py`
- `backend/main.py`
- `backend/test_categories.py`
- `backend/test_history_search.py`
- `scrape_merge.py`
- `database/sale_history.py`

### Secondary (MEDIUM confidence)
- `.planning/codebase/CONVENTIONS.md`
- `.planning/codebase/INTEGRATIONS.md`
- `.planning/codebase/TESTING.md`

### Tertiary (LOW confidence - needs validation)
- Live catalog-tile behavior outside normal product departments
</sources>

<metadata>
## Metadata

**Research scope:**
- Core technology: source-by-source HTTP collection
- Ecosystem: `aiohttp`, JSON artifacts, FastAPI admin-run status
- Patterns: manifest + per-source files + separate source-state validation
- Pitfalls: overlap, stale validity, partial-progress loss, weak failure visibility

**Confidence breakdown:**
- Standard stack: HIGH
- Architecture: HIGH
- Pitfalls: HIGH
- Code examples: HIGH

**Research date:** 2026-04-04
**Valid until:** 2026-05-04
</metadata>

---

*Phase: 36-supplemental-catalog-discovery*
*Research completed: 2026-04-04*
*Ready for planning: yes*
