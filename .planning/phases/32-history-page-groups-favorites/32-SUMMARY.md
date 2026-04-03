# Phase 32 Summary: History Page Groups & Favorites

**Status:** ✅ Complete
**Completed:** 2026-04-03

## What was built

### History-page hierarchy filters
- Added group chips to the History page
- Added subgroup drill-down row for the selected group
- Wired History page requests to send `group` and `subgroup` to `/api/history/products`

### Favorite integration
- Added group/subgroup favorite support on the History page using the same exact category-key format as the main page

### Post-ship fix
- Fixed a live mismatch where History chips were built from the full catalog but the History list only showed products with sale history
- History chips now use a history-backed scope by default, preventing empty subgroup rows like `Для собак (24)` with zero results

## Verification

- ✅ `miniapp` build succeeded with History page drill-down logic
- ✅ Live API verification confirmed `scope=history` and history product queries now agree
- ✅ History page group/subgroup flow uses the same key contract as Phase 31 favorites

## Requirements covered

- **HIST-01** ✅ History page shows group filter chips
- **HIST-02** ✅ Selecting a group shows subgroup chips
- **HIST-03** ✅ Same subgroup hide rules apply on History page
- **HIST-04** ✅ Group/subgroup favorites work on History page
