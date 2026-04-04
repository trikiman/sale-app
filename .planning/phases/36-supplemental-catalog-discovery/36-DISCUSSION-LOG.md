# Phase 36: Supplemental Catalog Discovery - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md.

**Date:** 2026-04-04
**Phase:** 36-supplemental-catalog-discovery
**Areas discussed:** source model, completion logic, storage model, failure handling, identity strategy

---

## Source Model

| Option | Description | Selected |
|--------|-------------|----------|
| Scrape all catalog tiles as sources | Treat every visible catalog tile/source as input, including overlapping ones | ✓ |
| Scrape only manually selected sources | Restrict discovery to a curated subset | |
| Split base vs overlay categories first | Try to classify sources before collection | |

**User's choice:** Scrape all catalog tiles/sources.
**Notes:** Overlap is acceptable. Counts are per source, not a global summed total.

---

## Completion Logic

| Option | Description | Selected |
|--------|-------------|----------|
| Per-source live count target | A source is done when collected items for that source match the live count shown on that source page | ✓ |
| Global summed count target | Sum category counts into one global target | |

**User's choice:** Per-source live count target.
**Notes:** This was clarified explicitly. The purpose of the source count is to prove a source scrape is complete, not to produce a global unique-store total.

---

## Storage Model

| Option | Description | Selected |
|--------|-------------|----------|
| Separate temp file per source | More robust collection; one bad source run should not affect all discovery data | ✓ |
| One big discovery file during collection | Simpler later merge, but weaker isolation during failures | |

**User's choice:** Separate temp file per source.
**Notes:** Robustness was prioritized over later merge convenience.

---

## Failure Handling

| Option | Description | Selected |
|--------|-------------|----------|
| Strict source validity with incremental retries | Keep already collected items, but a source is only valid after a fresh run matches the current live count | ✓ |
| Accept partial source completion | |
| Treat previous success as enough even if current validation fails | |

**User's choice:** Strict source validity with incremental retries.
**Notes:** If a source count mismatches, the source is incomplete. Admin panel logs are required. Existing collected items may remain between failed runs, but only a fresh matching run can mark the source complete.

---

## Identity Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| Lock dedupe to `product_id` immediately | |
| Validate identity key during research/execution | ✓ |
| Use name/url composite key | |

**User's choice:** Validate identity key during research/execution.
**Notes:** `product_id` is the preferred candidate, but it should be verified rather than assumed.

---

## Key Clarification

- The user explicitly clarified that duplicates across sources are acceptable during collection.
- The user explicitly clarified that source totals are used only to verify each source scrape, not to sum one global total.
- The user explicitly accepted the rare stale-item edge case between failed runs, because a fresh matching run is the real validity gate.
