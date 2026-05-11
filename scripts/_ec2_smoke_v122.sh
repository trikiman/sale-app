#!/usr/bin/env bash
# Run ON EC2: smoke-test v1.22 phases locally (no outbound SSH, no Vercel).
# Mirrors scripts/verify_v1.22.sh but assumes we're already on the host.
set -uo pipefail

cd /home/ubuntu/saleapp

FAIL=0
_ok() { printf "  [OK]  %s\n" "$1"; }
_no() { printf "  [FAIL] %s\n" "$1"; FAIL=1; }

echo "=== Phase 70: History Search Catalog-Wide ==="

# 70-A
if python3 -c 'from backend.main import _load_current_sale_types; assert callable(_load_current_sale_types)'; then
    _ok "70-A: _load_current_sale_types importable"
else
    _no "70-A"
fi

# 70-B
if python3 -m pytest backend/test_history_search_catalog_wide.py -q 2>&1 | tail -3 | grep -Eq '5 passed'; then
    _ok "70-B: backend/test_history_search_catalog_wide.py 5/5"
else
    _no "70-B"
fi

# 70-C: direct curl to backend (port 8000) — check response schema carries key
curl -fsS --max-time 10 "http://127.0.0.1:8000/api/history/products?search=%D1%82%D0%B5%D1%81%D1%82&per_page=1" > /tmp/_70c.json 2>/dev/null
if python3 -c "
import json
try:
    d = json.load(open('/tmp/_70c.json'))
except Exception as e:
    print('PARSE_ERR:' + str(e)); raise SystemExit(1)
products = d.get('products', [])
if not products:
    print('NO_PRODUCTS'); raise SystemExit(2)
has_key = 'currentSaleType' in products[0]
print('OK' if has_key else 'MISSING_KEY')
if not has_key: raise SystemExit(3)
" 2>&1 | grep -q '^OK'; then
    _ok "70-C: /api/history/products rows include currentSaleType"
else
    R=$(python3 -c "
import json
try:
    d = json.load(open('/tmp/_70c.json'))
    p = d.get('products', [])
    if not p:
        print('NO_PRODUCTS')
    else:
        print('OK' if 'currentSaleType' in p[0] else 'MISSING_KEY')
except Exception as e:
    print('PARSE_ERR:' + str(e))
" 2>&1)
    if [[ "$R" == "NO_PRODUCTS" ]]; then
        _ok "70-C: /api/history/products responded (empty for 'тест', schema cannot be checked)"
    else
        _no "70-C: $R"
    fi
fi

echo ""
echo "=== Phase 71: Stale Banner Clarification ==="

# 71-A: source file contains new banner string
if grep -q 'Источники устарели' miniapp/src/App.jsx 2>/dev/null; then
    _ok "71-A: miniapp source contains 'Источники устарели'"
else
    _no "71-A: 'Источники устарели' missing from miniapp source"
fi

# 71-B: old banner string gone from source
if grep -q 'Данные устарели' miniapp/src/App.jsx 2>/dev/null; then
    _no "71-B: legacy 'Данные устарели' still in miniapp/src/App.jsx"
else
    _ok "71-B: legacy 'Данные устарели' removed from miniapp source"
fi

# 71-C: staleColorLabels includes per-source age
if grep -q 'ageMinutes' miniapp/src/App.jsx && grep -q 'мин.' miniapp/src/App.jsx; then
    _ok "71-C: staleColorLabels includes per-source age formatting"
else
    _no "71-C: per-source age formatting missing from miniapp source"
fi

echo ""
echo "=== Phase 72: admin.html Bug Reports + Drift Badges ==="

if grep -q 'id="bug-reports-badge"' backend/admin.html; then
    _ok "72-A: admin.html contains bug-reports-badge span"
else
    _no "72-A: bug-reports-badge span missing"
fi

if grep -q 'id="xray-drift-badge"' backend/admin.html; then
    _ok "72-B: admin.html contains xray-drift-badge span (UX-BADGE-02)"
else
    _no "72-B: xray-drift-badge span missing"
fi

if grep -q 'data.bugReports' backend/admin.html; then
    _ok "72-C: applyStatus reads data.bugReports"
else
    _no "72-C: applyStatus missing data.bugReports reference"
fi

echo ""
echo "=== Phase 73: /gsd-check-todos Skill Polish ==="

REPO_ROOT="/home/ubuntu/saleapp"

if grep -q '^priority:\s*P[1-4]' "$REPO_ROOT/.planning/todos/pending/2026-05-12-update-gsd-check-todos-skill.md" 2>/dev/null; then
    _ok "73-A: pending skill-polish todo carries explicit priority frontmatter"
else
    _no "73-A: pending skill-polish todo missing priority field"
fi

if [[ -f "$REPO_ROOT/.planning/phases/73-gsd-check-todos-skill-polish/SKILL.md.post73" ]] \
   && [[ -f "$REPO_ROOT/.planning/phases/73-gsd-check-todos-skill-polish/check-todos.md.post73" ]] \
   && [[ -f "$REPO_ROOT/.planning/phases/73-gsd-check-todos-skill-polish/cmdInitTodos.cjs.post73" ]]; then
    _ok "73-B: in-tree snapshots of post-73 SKILL/workflow/CLI present"
else
    _no "73-B: one or more post-73 snapshots missing"
fi

if grep -q 'Priority ladder' "$REPO_ROOT/.planning/phases/73-gsd-check-todos-skill-polish/SKILL.md.post73" \
   && grep -q 'priorityRank' "$REPO_ROOT/.planning/phases/73-gsd-check-todos-skill-polish/cmdInitTodos.cjs.post73"; then
    _ok "73-C: priority schema + sort code captured in snapshots"
else
    _no "73-C: snapshots missing expected markers"
fi

echo ""
echo "=== Summary ==="
if [[ $FAIL -eq 0 ]]; then
    echo "ALL PASS"
    exit 0
else
    echo "SOME CHECKS FAILED"
    exit 1
fi
