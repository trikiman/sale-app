---
date: 2026-05-13
area: vless/manager.py + scheduler_service.py + observability
priority: P1
source: live outage 2026-05-13 ~16:19-17:30 MSK (~1h empty grid)
---

# VLESS pool recovery takes ~1h because of repeated full re-probes + no quarantine memory

## Incident

2026-05-13 16:19-17:30 MSK (roughly 1 hour): MiniApp grid empty. Caused by VLESS pool collapse and slow recovery. Observed by user as "cusite didn't work around 1 hour".

**User impact:** Family members opening the app saw empty grid + stale banner for ~60 minutes during the outage. App appeared broken.

## Timeline (from systemd journal)

- **16:19** — Pool drops from 7/7 to 3/7 healthy; first "VkusVill: BLOCKED" event, first refresh triggered
- **16:19 → 16:35** — 19 refresh attempts in ~15 min, every one parses 519 nodes → geo-filters to 231 RU → probes them all, finds few working
- **16:35** — Pool at 1/7, all 3 scrapers getting ERROR exit 1
- **16:45** — Scheduler manually restarted (doesn't help; probe loop resumes)
- **~17:10** — Same pattern; pool oscillating 0-4
- **~17:30** — Enough nodes admitted to resume scraping; first successful cycle
- **~17:45** — Pool at 4/7; scrapers succeeding but still flagged degraded
- **~18:28** — Full cycle back to OK on all 3 colors; grid repopulates

**Total outage: ~70 min from first BLOCKED to first successful cycle.**

## Root Causes (compound)

### A. No quarantine memory across refreshes

Every "Pool low — refreshing..." event re-parses the **same 519 nodes → 231 RU** list and re-probes them from scratch. Dead nodes that just failed 2 min ago get probed again. Working nodes that just got admitted get re-tested unnecessarily.

Evidence: log shows `Parsed 519 nodes (90 parse errors)` + `Geo-filter: 231 RU / 288 rejected` repeated 19 times in 15 min, always with identical counts — meaning the node list is being re-downloaded and re-parsed every single refresh, no caching of the "already known dead" set.

**Fix:** Persistent deadlist with TTL (e.g., 20 min). Refresh skips nodes in deadlist. Only probe unknown-state nodes.

### B. Refresh loop without backoff

When pool is low, every failing scrape triggers a refresh. 3 scrapers × failure-per-cycle → refreshes pile up. No throttle; no circuit breaker.

**Fix:** `REFRESH_MIN_INTERVAL_S = 60` (hardcoded minimum time between refreshes). If a refresh just ran, skip the next one and let scrapers wait 60s before trying again. Cuts wasted work by 10-20×.

### C. Pool-size low-water mark too conservative

`min_healthy = 7` but `MAX_CACHED` is (appears to be) 25. Pool can drop from 25 → 6 before refresh triggers — that's 19 nodes lost before we react. In practice the whole pool dies in under a minute when VkusVill rate-limits or routing breaks.

**Fix:** Lower `min_healthy` check to trigger at `min_healthy = 10` (+3 buffer), or trigger on rate-of-decline (e.g., if pool lost 3+ nodes in 5 min, refresh proactively). Early warning is cheaper than late recovery.

### D. No fallback path when pool is 0

All 3 scrapers instantly fail with exit 1 when pool=0. No attempt to:
- Skip the cycle (not retry scrape logic when pool is dead)
- Serve cached-data-only mode to clients (v1.22 already has stale badges)
- Alert operator

Scheduler silently churns refreshes while the app is broken.

**Fix:** Scheduler detects "pool still dead after 3 refreshes" → emit Telegram alert + back off retry cadence (wait 5 min instead of 1 min) + mark proposals with an explicit "pool_dead_since" timestamp that backend can expose.

### E. No operator alert for extended outage

v1.21 added `xray_drift` to `/api/health/deep` but no push alerts. User discovered the outage only by opening the app 60 min in.

**Fix:** Telegram alert on `pool.size == 0 for > 10 min` using the existing bot infrastructure. Wire into v1.19 REL-FUT-05 "Telegram alerts on xray_restart_failed / breaker state transitions" which is already in the tech-debt list.

## Scope for v1.24

Combining these into a cohesive phase makes sense. ~200-300 LOC across 2-3 files:

- `vless/manager.py` — persistent deadlist + refresh throttle + lower low-water mark
- `scheduler_service.py` — skip-scrape-when-pool-dead fallback + exponential refresh backoff
- `backend/notifier.py` or new `bot/alerts.py` — Telegram admin alerts on extended pool outage
- `backend/main.py::products` — respect the pool-dead flag and serve last-good data regardless of staleness (pair with `2026-05-13-empty-grid-when-all-sources-stale-during-pool-recovery.md` P2 todo)

## Target Milestone

v1.24 — proposed scope: "Pool Self-Heal Hardening + Outage UX". Pair with the empty-grid UX todo for cohesive ship. Maybe 2-3 phases total.

## Family Impact

**High.** 1 hour of empty app = family member gives up on the aggregator and opens VkusVill.ru directly. Defeats the entire purpose of the tool. This is worse than a slow app (v1.20) because slow-but-working retains trust; broken-for-an-hour destroys it.

## Historical

- v1.21 shipped self-heal reprobe + auto-reload (REL-13/14). Those solve "pool admitted but some nodes drifted." This outage is different: the pool itself got blown out, and the refresh loop couldn't recover it fast.
- v1.19 circuit breaker is `closed` during the incident — breaker never opened because the scraper process itself kept retrying, not hitting the specific error profile that opens the breaker.
- 2026-05-06 → 05-10 was a similar multi-day outage that v1.21 was built to prevent; today's 1-hour outage is the next iteration — pool-total-death-plus-slow-rebuild.

## Symptoms / Detection Signal (for future occurrences)

- `/api/health/deep` → `status: degraded`, `pool.size < 3`, `quarantined_count > 15` — all simultaneously
- Scheduler log: `Pool low (N/7)` every cycle with `N ≤ 2`
- `proposals.json` mtime stale > 10 min despite scheduler running
- MiniApp: "0 всего 🟢 0 🔴 0 🟡 0" + stale banner on all 3 sources
