# Phase 70 Verification — History Search Catalog-Wide

## Status: CODE SHIPPED locally; awaiting EC2 auto-deploy + live MCP check

**Ships locally:**
- [x] 70-01 `_load_current_sale_types` helper + `/api/history/products` enrichment (commit `baa4a77` + `ba3cbd5`)
- [x] 70-02 `HistoryPage.jsx` badge uses `currentSaleType` first (commit `53ab983`)
- [x] 70-03 `scripts/verify_v1.22.sh` Phase 70 block + this runbook (this commit)
- [x] 5/5 tests pass in `backend/test_history_search_catalog_wide.py`
- [x] Full local suite 360 passed + 3 baseline Windows-only unchanged
- [x] `cd miniapp && npm run build` green
- [x] `bash -n scripts/verify_v1.22.sh` exit 0

**NEEDS_OPERATOR:**

### NEEDS_OPERATOR-1: EC2 + Vercel deploy

```bash
# Backend auto-deploys via github-webhook. Miniapp auto-deploys via Vercel push.
ssh ubuntu@13.60.174.46 "cd /home/ubuntu/saleapp && git log -1 --oneline"
# Expect: HEAD is the 70-03 commit

# If the miniapp build needs a backend restart to serve fresh dist/:
ssh ubuntu@13.60.174.46 "sudo systemctl restart saleapp-backend && sleep 5 && systemctl is-active saleapp-backend"
```

### NEEDS_OPERATOR-2: Live Chrome DevTools MCP verification

```
1. Open Chrome via the shared CDP bridge (port 9222).
2. Navigate to https://vkusvillsale.vercel.app/ and switch to the History tab.
3. Search for a product known to be CURRENTLY on sale today (e.g. pick a
   product_id visible on the main page and search its name — a common
   green product works well).
4. Confirm:
   - The matching card renders with the CURRENT badge color, not the
     historical one.
   - The red "●" live-dot is present.
   - Other matching products (history-only) still render with ghost-card
     styling and their historical last_sale_type color.
5. Screenshot: .planning/phases/70-history-search-catalog-wide/mcp-history-live-badge.png
```

### NEEDS_OPERATOR-3: Smoke script live run

```bash
bash scripts/verify_v1.22.sh 70
# Expect:
#   70-A ✓ _load_current_sale_types importable on EC2
#   70-B ✓ backend/test_history_search_catalog_wide.py — 5/5 green on EC2
#   70-C ✓ /api/history/products response rows include currentSaleType

bash scripts/verify_v1.22.sh all
# Expect all v1.22 checks green + v1.21 13/13 + v1.20 19/19 + v1.19 24/24
```

### NEEDS_OPERATOR-4: Rollback rehearsal

```bash
# On a throwaway worktree:
git revert 53ab983 ba3cbd5 baa4a77   # 70-02 first (frontend), then 70-01 commits
python3 -m pytest backend/ tests/ -q
# Expect: 355 passed + 3 baseline (back to pre-v1.22 baseline)
cd miniapp && npm run build
# Expect: build succeeds; HistoryPage-*.js back to prev hash
sudo systemctl restart saleapp-backend
# Confirm /api/history/products response no longer has currentSaleType key:
curl -fsS 'https://vkusvillsale.vercel.app/api/history/products?search=test&per_page=1' | \
    python3 -c 'import json,sys; d=json.load(sys.stdin); p=d.get("products",[]); print("reverted" if not p or "currentSaleType" not in p[0] else "still present")'
```

## Success Criteria

| Criterion | Status | Evidence |
|---|---|---|
| 1. `_load_current_sale_types` importable, defensive on missing/malformed | code_complete | `test_load_current_sale_types_*` 3/3 green |
| 2. `/api/history/products` response carries `currentSaleType` on every row | code_complete | `test_history_search_exposes_current_sale_type_for_live_product` |
| 3. `is_currently_on_sale` upgraded to OR proposals + sale_sessions | code_complete | same test asserts `is_currently_on_sale: true` for live-only-in-proposals product |
| 4. Frontend HistoryPage renders live badge color first | code_complete | commit `53ab983` + npm build green |
| 5. No `.planning/` regression on full test suite | code_complete | 360 passed + 3 baseline |
| 6. Live: searching a known-live product shows correct current-color badge | needs_operator | NEEDS_OPERATOR-2 MCP screenshot |
| 7. Smoke script 70-A/B/C green on live EC2 | needs_operator | NEEDS_OPERATOR-3 |
| 8. Rollback rehearsal green | needs_operator | NEEDS_OPERATOR-4 |
| 9. v1.21 + v1.20 + v1.19 regression green | needs_operator | `verify_v1.22.sh all` tail |

## Phase Boundary

**Ships:** `currentSaleType` response field + upgraded `is_currently_on_sale` + frontend badge-color fix + 5 unit tests + 3 smoke checks.

**Does NOT ship:**
- "Live only" filter toggle (separate phase)
- Sort-live-first (separate phase)
- Proposals.json mtime-TTL cache (profile first)
- Stale banner clarification (Phase 71)
- admin.html Bug Reports badge (Phase 72)
- gsd-check-todos skill polish (Phase 73)

**Acceptance gate:** 5/5 tests green + 3/3 smoke on EC2 + live MCP screenshot proving live-product badge renders with current color.
