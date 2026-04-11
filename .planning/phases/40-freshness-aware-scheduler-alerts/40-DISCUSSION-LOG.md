# Phase 40: Freshness-Aware Scheduler & Alerts - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in `40-CONTEXT.md` — this log preserves the alternatives considered.

**Date:** 2026-04-05
**Phase:** 40-freshness-aware-scheduler-alerts
**Areas discussed:** scheduler cadence, stale thresholds, warning surfaces, stale-data fallback

---

## Scheduler Cadence

| Option | Description | Selected |
|--------|-------------|----------|
| Single flat interval | Keep the current red -> yellow -> green loop every N minutes | |
| Full-cycle + green-only cadence | Keep a normal full cycle, then run extra green-only passes between full cycles without overlap | ✓ |
| Parallelized color workers | Run different colors independently at the same time | |

**User's choice:** Keep the full cycle, but run extra `GREEN-only` passes between full cycles.  
**Notes:** User clarified the desired rhythm as “yellow and red every 5 min” with green attempts in between. They explicitly want completion-based waiting: if green finishes in 30 seconds wait 30 seconds, if it finishes in 50 seconds wait 10 seconds, and if it takes longer than 1 minute start the next due step immediately.

---

## Full-Cycle Priority

| Option | Description | Selected |
|--------|-------------|----------|
| Full cycle wins | Skip an extra green pass if it would make red/yellow late | ✓ |
| Green always runs first | Let the next full cycle drift if another green pass is ready | |

**User's choice:** Full cycle wins.  
**Notes:** This preserves the 5-minute red/yellow target while still favoring green freshness where capacity exists.

---

## Stale Thresholds

| Option | Description | Selected |
|--------|-------------|----------|
| Different thresholds by color | Green gets a shorter threshold than red/yellow | |
| Same threshold for all colors | All colors are considered stale after the same age | ✓ |

**User's choice:** `10 minutes` stale threshold for **all** colors.  
**Notes:** User explicitly answered “10 min for all”.

---

## Stale/Failed Data Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Hide failed/stale colors | Remove that color until a fresh scrape succeeds | |
| Keep last valid snapshot | Continue showing the last good data, but mark it as old/unreliable | ✓ |

**User's choice:** Keep the **last valid** snapshot.  
**Notes:** User does not want stale colors hidden if the last valid data still exists.

---

## Warning Surface

| Option | Description | Selected |
|--------|-------------|----------|
| Admin/log only | Operators see stale data, normal users do not | |
| Warn all users in MiniApp + admin/logs | Reuse the current site warning pattern so everyone sees outdated data | ✓ |
| MiniApp + Telegram push to everyone | Add a new push alert to all users | |

**User's choice:** Warn **all users** via the site/MiniApp, and also keep admin/log visibility.  
**Notes:** User explicitly said “if smth outdated more than 10 min u need warn all” and chose reuse of the existing warning surface rather than a new pattern.

---

## the agent's Discretion

- Exact due-job algorithm for scheduling `ALL` vs `GREEN-only`
- Exact wording of the stale banner
- Exact per-source freshness fields in backend/admin payloads

## Deferred Ideas

- Telegram push alerts to every user for stale/failure events — deferred; Phase 40 only locks MiniApp warning reuse plus admin/log visibility
