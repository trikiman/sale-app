# Phase 71 Verification — Stale Banner Clarification

## Status: CODE SHIPPED locally; awaiting Vercel auto-deploy + live MCP screenshot

**Ships locally:**
- [x] 71-01 `miniapp/src/App.jsx` banner copy + per-source age label (commit `01ac9bb`)
- [x] 71-02 `scripts/verify_v1.22.sh` Phase 71 block + this runbook (this commit)
- [x] `cd miniapp && npm run build` green
- [x] `grep -r 'Источники устарели' miniapp/dist/` finds the new string
- [x] `grep -r 'Данные устарели' miniapp/dist/` finds nothing (old string gone)
- [x] `bash -n scripts/verify_v1.22.sh` exit 0

**NEEDS_OPERATOR:**

### NEEDS_OPERATOR-1: Vercel deploy

The miniapp auto-deploys via Vercel when we push to origin. Wait 2-3 min after push for the new build to go live.

```bash
# Confirm Vercel picked up the new banner string:
curl -fsS https://vkusvillsale.vercel.app/assets/index-*.js 2>/dev/null | grep -c 'Источники устарели' || \
    echo "Vercel bundle does not yet contain new string — wait or check deployment dashboard"
```

### NEEDS_OPERATOR-2: Live Chrome DevTools MCP verification with synthetic stale fixture

```bash
# On EC2: induce a stale green source (30 min old).
ssh ubuntu@13.60.174.46
cd /home/ubuntu/saleapp
touch -d "30 minutes ago" data/green_products.json
# Confirm the backend now reports green as stale:
curl -sS http://127.0.0.1:8000/api/products | python3 -m json.tool | grep -A 6 sourceFreshness | head -20
# Expect: sourceFreshness.green.ageMinutes ~= 30, sourceFreshness.green.isStale: true

# From local (Chrome DevTools MCP via port 9222):
# 1. Navigate to https://vkusvillsale.vercel.app/
# 2. Wait for initial product load.
# 3. Confirm:
#    - Header says "Обновлено: HH:MM" with a RECENT time (merge still fresh).
#    - Banner says "⚠️ Источники устарели: зелёные (30 мин.) — товары и цены могут не совпадать с сайтом"
#    - Banner + header no longer look contradictory.
# 4. Screenshot: .planning/phases/71-stale-banner-clarification/mcp-stale-banner.png

# Restore on EC2 when done:
ssh ubuntu@13.60.174.46 "cd /home/ubuntu/saleapp && sudo systemctl restart saleapp-scheduler"
# Next green scrape cycle within ~3 min writes a fresh green_products.json.
```

### NEEDS_OPERATOR-3: Smoke script live run

```bash
bash scripts/verify_v1.22.sh 71
# Expect:
#   71-A ✓ 'Источники устарели' present on EC2 (source or dist)
#   71-B ✓ 'Данные устарели' removed
#   71-C ✓ staleColorLabels includes per-source age formatting

bash scripts/verify_v1.22.sh all
# Expect all v1.22 checks green + v1.21 13/13 + v1.20 19/19 + v1.19 24/24
```

### NEEDS_OPERATOR-4: Rollback rehearsal

```bash
# On a throwaway worktree:
git revert 01ac9bb     # 71-01 (frontend copy)
cd miniapp && npm run build
# Confirm build succeeds; bundle contains 'Данные устарели' again
grep -r "Данные устарели" miniapp/dist/
# Expect: match
grep -r "Источники устарели" miniapp/dist/
# Expect: no match
```

## Success Criteria

| Criterion | Status | Evidence |
|---|---|---|
| 1. Banner copy changed to 'Источники устарели' | code_complete | commit `01ac9bb` + grep hit in miniapp/dist/ |
| 2. Per-source age surfaced inline via `(N мин.)` | code_complete | staleColorLabels useMemo rewrite |
| 3. Missing file case: `(нет файла)` fallback | code_complete | staleColorLabels branch on `status === 'missing'` |
| 4. `Обновлено: HH:MM` header untouched | code_complete | no diff in header block |
| 5. Threshold (10 min) unchanged | code_complete | `_build_source_freshness(stale_minutes=10)` unchanged |
| 6. Miniapp build green | code_complete | `npm run build` succeeds |
| 7. Old 'Данные устарели' string removed from bundle | code_complete | `grep -c` returns 0 |
| 8. Vercel deploy picks up new string | needs_operator | NEEDS_OPERATOR-1 |
| 9. Live MCP: synthetic stale shows correct banner alongside fresh header | needs_operator | NEEDS_OPERATOR-2 |
| 10. Smoke 71-A/B/C green on live EC2 | needs_operator | NEEDS_OPERATOR-3 |
| 11. Rollback rehearsal green | needs_operator | NEEDS_OPERATOR-4 |

## Phase Boundary

**Ships:** banner rescoped from 'Данные' to 'Источники' + per-source age `(N мин.)` + missing-file fallback `(нет файла)`, 2 commits (implementation + verify+runbook).

**Does NOT ship:**
- Threshold re-tuning (unchanged at 10 min by design, rationale in 71-CONTEXT.md)
- `Обновлено` header semantic change (intentional — preserves existing merge-time signal)
- i18n layer
- admin.html Bug Reports badge (Phase 72)
- gsd-check-todos skill polish (Phase 73)

**Acceptance gate:** grep shows new string in bundle + MCP screenshot proves banner and header no longer look contradictory under synthetic stale fixture.
