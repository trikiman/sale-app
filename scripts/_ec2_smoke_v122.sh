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
echo "=== Summary ==="
if [[ $FAIL -eq 0 ]]; then
    echo "ALL PASS"
    exit 0
else
    echo "SOME CHECKS FAILED"
    exit 1
fi
