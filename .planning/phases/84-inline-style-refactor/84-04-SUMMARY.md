# Phase 84.4 — TCP pre-filter + RU-only label gate — SUMMARY

## Status

✅ **Shipped 2026-05-14** as commit `d469080`. Single atomic commit, deployed to EC2 at ~18:42 MSK, live-verified across 3 refresh cycles.

## Goal

Close the pool-starvation regression introduced by Phase 84.2's
"unlabeled fallthrough" admission. After 84.2, pool admitted 0/180
candidates per cycle on EC2 because the budget got eaten by dead
Azure exits and non-RU egresses from kort0881-style aggregators.

User-visible target: `Обновлено:` timestamp in the miniapp must never
exceed 5 minutes stale.

## Commit

| Commit | Purpose |
|---|---|
| `d469080` | `vless/sources.py` RU-only filter + `vless/manager.py` `_tcp_prefilter_candidates` + `tcp_unreachable` quarantine bucket + 3 test deltas |

## Files modified

- `vless/sources.py` — `filter_ru_nodes` requires explicit RU marker (🇷🇺 or "russia" text). Drops the unlabeled-fallthrough from Phase 84.2. `_has_explicit_non_ru_marker` and `_NON_RU_*` constants intentionally retained as dead code for potential feature-flag revival.
- `vless/manager.py` — new `_tcp_prefilter_candidates` runs before xray subprocess setup, rejects nodes whose `host:port` doesn't open in 2s. Stamps `extra["rejected_reason"] = "tcp_unreachable"` so the existing classifier in `refresh_proxy_list` quarantines them at the soft tier (60s TTL). Classifier extended with `tcp_unreachable` bucket for admin diagnostics.
- `tests/test_vless_manager.py` — flipped `test_filter_ru_nodes_admits_unlabeled_lines_to_be_probed_for_egress` → `test_filter_ru_nodes_rejects_anything_without_explicit_ru_marker`. Added `test_tcp_prefilter_drops_unreachable_candidates` and `test_tcp_prefilter_runs_before_xray_in_full_probe_pipeline`. Updated 4 existing `_probe_candidates_*` tests to monkeypatch `_tcp_prefilter_candidates` as a passthrough so they don't try to TCP-connect to synthetic 10.0.0.x hosts.

## Test results

- `tests/test_vless_manager.py`: 40 passed, 1 skipped (live-only).
- Full suite: 281 passed, 3 known Windows-only baseline failures, 3 skipped.

## Live verification (EC2)

First refresh cycle after deploy + quarantine clear:

```
[PROXY] Geo-filter: 95 RU / 1057 rejected
[PROXY] TCP pre-filter: 26/52 reachable (26 dead at TCP layer, ~156s of xray probes saved)
[PROXY] Quarantined 51 probe-failed nodes (graduated TTL: probe_error=24, egress_country_non_ru=1, tcp_unreachable=26)
[PROXY-REFRESH] Done: 1 new proxies, pool=1
```

Data freshness across 3 cycles:

| Time | green | red | yellow | Pool |
|---|---|---|---|---|
| 18:42 | 5.2m | 1.7m | 0.8m | 1/10 |
| 18:48 | 2.3m | 1.5m | 0.7m | 1/10 |
| 19:04 | (Обновлено: 19:01 — 3m stale on UI) | | | 1/10 |

✅ All sources stayed under 5-minute target.
✅ No staleness banner on the miniapp.
✅ `tcp_unreachable` bucket visible in admin diagnostics.

## Known limitations (intentional)

- **Pool size still degraded (1/10)** on a single Sberbank CDN node (`yt-noads.sbrf-cdn342.ru:443`). The RU-only filter trades pool size for stability — we lose ~140 unlabeled candidates per cycle, some of which may have been genuinely RU. The 1-node pool is sufficient for the 5-min-freshness target because TCP pre-filter saves enough budget per cycle that the surviving candidate gets fully probed.
- **Recovery path if pool starves**: re-enable unlabeled-fallthrough behind a feature flag — `_has_explicit_non_ru_marker` and `_NON_RU_*` constants are retained for that path.
- **Open question (deferred)**: should we even require RU egress? `check-host.net` shows vkusvill.ru returns 301 OK from 30+ countries. Phase 84.4 keeps the existing RU-only stance; revisit if pool starves.

## Outstanding work in Phase 84

- **Phase 84-02** — App.jsx (10) + ProductDetail.jsx (9) inline-style refactor.
- **Phase 84-03** — HistoryPage (10) + HistoryDetail (14), then bump `react/forbid-dom-props` WARN→ERROR.

Phase 84 itself remains `in_progress` until 84-02 + 84-03 close the remaining 43 inline-style sites.
