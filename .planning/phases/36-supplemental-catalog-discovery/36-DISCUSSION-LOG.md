# Phase 36: Supplemental Catalog Discovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-04
**Phase:** 36-supplemental-catalog-discovery
**Areas discussed:** Discovery path, Discovery inputs, Discovery output contract, Pipeline compatibility
**Mode:** Auto (`--auto` semantics applied by the agent using recommended defaults)

---

## Discovery Path

| Option | Description | Selected |
|--------|-------------|----------|
| Separate offline discovery step | Add a dedicated supplemental discovery script/job that runs outside the user request path and keeps `scrape_categories.py` intact | ✓ |
| Expand runtime History search | Query remote VkusVill search when users search in History | |
| Stretch the current category crawler | Keep everything inside `scrape_categories.py` even if it mixes category crawl and supplemental discovery concerns | |

**User's choice:** Auto-selected the recommended default: separate offline discovery step.
**Notes:** This matches the milestone decision to expand the local catalog first and keeps hybrid/runtime search out of scope for v1.9.

---

## Discovery Inputs

| Option | Description | Selected |
|--------|-------------|----------|
| Repo-tracked seed query set | Keep a repeatable list of known-gap queries and discovery seeds in the repo so runs are reproducible and reviewable | ✓ |
| Manual ad hoc queries | Discover missing products only when someone notices a gap and types a query by hand | |
| Blind broad crawl | Try to brute-force discovery without a maintained seed set or parity targets | |

**User's choice:** Auto-selected the recommended default: repo-tracked seed query set.
**Notes:** The pending todo about missing catalog products was folded into scope as the starting acceptance target, including the `цезарь` example.

---

## Discovery Output Contract

| Option | Description | Selected |
|--------|-------------|----------|
| Sidecar discovery artifact | Write a separate artifact keyed by stable `product_id`, to be merged into the main catalog in Phase 37 | ✓ |
| Direct write into `category_db.json` | Mutate the main category artifact during discovery | |
| Direct write into `product_catalog` | Skip the existing artifact pipeline and push discoveries straight into SQLite | |

**User's choice:** Auto-selected the recommended default: sidecar discovery artifact.
**Notes:** This keeps Phase 36 scoped to discovery and avoids risky partial writes into the existing local catalog before merge rules are defined.

---

## Pipeline Compatibility

| Option | Description | Selected |
|--------|-------------|----------|
| HTTP-only low-concurrency discovery | Reuse existing aiohttp/proxy patterns, require stable `product_id`, and keep runtime consumers unchanged until Phase 37 | ✓ |
| Browser-based discovery | Use `nodriver` / logged-in browser automation for supplemental discovery | |
| Immediate downstream rewiring | Make `scrape_merge.py` or History API read the new discovery output right away in Phase 36 | |

**User's choice:** Auto-selected the recommended default: HTTP-only low-concurrency discovery.
**Notes:** This aligns with existing scraper constraints, avoids SMS/login coupling, and preserves the local-catalog runtime contract until the merge phase.

---

## Agent's Discretion

- Exact artifact filename and JSON schema for the discovery snapshot
- Query batching/pagination heuristics
- The exact remote source parsing approach, as long as it yields stable product IDs without moving discovery into runtime

## Deferred Ideas

- Runtime hybrid search fallback for live parity
- Merge/backfill rules for `category_db.json` and `product_catalog`
- Full parity verification and metrics surfacing
