# Phase 72 Verification — admin.html Bug Reports + Drift Badges

## Status: CODE SHIPPED locally; awaiting EC2 auto-deploy + admin view screenshot

**Ships locally:**
- [x] 72-01 `backend/admin.html` — new `.badge-warn` CSS, new spans for `bug-reports-badge` + `xray-drift-badge`, `applyStatus` wiring (commit `69098b3`)
- [x] 72-02 `scripts/verify_v1.22.sh` Phase 72 block + this runbook (this commit)
- [x] Admin HTML grep finds both badge IDs + `data.bugReports` reference
- [x] No backend diff (all data sources exist from v1.16 + v1.21)
- [x] `bash -n scripts/verify_v1.22.sh` exit 0

**NEEDS_OPERATOR:**

### NEEDS_OPERATOR-1: EC2 auto-deploy

Backend auto-deploys via github-webhook. No restart needed — `admin.html` is a static template served by the existing FastAPI route. Vercel does NOT proxy `/admin` (admin UI is served directly from EC2), so the Vercel rebuild cycle is irrelevant for this phase.

```bash
ssh ubuntu@13.60.174.46 "cd /home/ubuntu/saleapp && git log -1 --oneline"
# Expect: HEAD is the 72-02 commit
```

### NEEDS_OPERATOR-2: Live admin view verification

Open the admin dashboard (EC2 direct, since Vercel doesn't proxy /admin):

```
http://13.60.174.46:8000/admin
```

Paste the admin token. Expected:

1. **Header row layout:**
   - Left: `🛠️ VkusVill Admin`
   - Right: [badges if any] `Обновлено: HH:MM:SS` [Выйти]
2. **Bug Reports badge:**
   - If `bugReports.unread == 0`: badge is hidden (not visible at all).
   - If `bugReports.unread > 0`: badge visible with text `Bug Reports (N)`, amber color.
   - Click → navigates to `/admin/bug-reports` JSON view.
3. **xray_drift badge:**
   - If `drift_count == 0`: badge hidden.
   - If `drift_count > 0`: badge visible with text `Drift (N)`, amber color.
   - Click → navigates to `/api/health/deep`.

Screenshot captured in `.planning/phases/72-admin-html-bug-reports-badge/mcp-admin-badges.png`.

To force both badges visible for screenshot:
```bash
# Seed a fake bug report:
ssh ubuntu@13.60.174.46 "cd /home/ubuntu/saleapp && \
  echo '{\"reason\":\"test\",\"created\":\"2026-05-12T23:00:00Z\",\"user_id\":0,\"device\":\"smoke\"}' \
    > data/bug_reports/test-$(date +%s).json"
# Inject drift (remember to clean up):
ssh ubuntu@13.60.174.46 "cd /home/ubuntu/saleapp && \
  python3 -c 'import json,pathlib; p=pathlib.Path(\"data/vless_pool.json\"); d=json.loads(p.read_text()); d[\"nodes\"].append({\"host\":\"127.0.0.99\",\"port\":443,\"name\":\"drift-for-screenshot\"}); p.write_text(json.dumps(d,indent=2))'"
# Refresh admin page → both badges visible.
# Cleanup after screenshot:
ssh ubuntu@13.60.174.46 "rm -f /home/ubuntu/saleapp/data/bug_reports/test-*.json"
ssh ubuntu@13.60.174.46 "cd /home/ubuntu/saleapp && python3 -c 'import json,pathlib; p=pathlib.Path(\"data/vless_pool.json\"); d=json.loads(p.read_text()); d[\"nodes\"]=[n for n in d[\"nodes\"] if n.get(\"host\")!=\"127.0.0.99\"]; p.write_text(json.dumps(d,indent=2))'"
```

### NEEDS_OPERATOR-3: Smoke script live run

```bash
bash scripts/verify_v1.22.sh 72
# Expect:
#   72-A ✓ admin.html contains bug-reports-badge span
#   72-B ✓ admin.html contains xray-drift-badge span
#   72-C ✓ applyStatus reads data.bugReports
#   72-D ✓ /admin/status exposes bugReports.{count,unread}  (skipped without ADMIN_TOKEN)
```

### NEEDS_OPERATOR-4: Rollback rehearsal

```bash
git revert 69098b3
# admin.html returns to pre-72 state. No backend/JS logic change to worry about.
```

## Success Criteria

| Criterion | Status | Evidence |
|---|---|---|
| 1. `bug-reports-badge` span in admin.html | code_complete | commit `69098b3` + grep hit |
| 2. `xray-drift-badge` span in admin.html | code_complete | commit `69098b3` + grep hit |
| 3. `applyStatus(data)` reads `data.bugReports.unread` / `.count` | code_complete | JS block in commit `69098b3` |
| 4. `applyStatus(data)` reads `data.reliability.xray_drift.drift_count` | code_complete | same JS block |
| 5. `.badge-warn` CSS class present | code_complete | top of admin.html `<style>` |
| 6. Badge hidden when counter is 0 | code_complete | `brBadge.hidden = true` branch |
| 7. Click handler navigates to `/admin/bug-reports` | code_complete | inline `onclick` |
| 8. Click handler on drift badge navigates to `/api/health/deep` | code_complete | inline `onclick` |
| 9. Live: admin view shows badges correctly when counters > 0 | needs_operator | NEEDS_OPERATOR-2 |
| 10. Live: badges hidden when counters are 0 | needs_operator | NEEDS_OPERATOR-2 |
| 11. Smoke 72-A/B/C green on live EC2 | needs_operator | NEEDS_OPERATOR-3 |
| 12. Rollback rehearsal green | needs_operator | NEEDS_OPERATOR-4 |

## Phase Boundary

**Ships:** admin header Bug Reports badge + xray_drift badge (UX-BADGE-02 fold-in) + `.badge-warn` CSS + `applyStatus` wiring + smoke 72-A/B/C/D.

**Does NOT ship:**
- Rich admin UI for individual bug reports (current JSON view is enough for family-scale)
- Mark-as-read action in admin UI
- Per-drift-host click-through in admin view
- gsd-check-todos skill polish (Phase 73)

**Acceptance gate:** grep + admin view shows both badges rendering correctly under both "0" and ">0" states.
