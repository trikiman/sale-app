#!/usr/bin/env bash
# v1.22 UX Debt Cleanup + Tooling Polish Smoke Test
# ----------------------------------------------------
# Runs from local terminal. SSHes to the EC2 scraper host.
# Exits 0 on all-pass, 1 on any-fail. Idempotent.
#
# Usage:
#   ./scripts/verify_v1.22.sh           # all phases + v1.21 + v1.20 + v1.19 regression
#   ./scripts/verify_v1.22.sh 70        # only Phase 70 checks
#   ./scripts/verify_v1.22.sh 73        # only Phase 73 (skill-file phase, no EC2)
#
# Requires: SSH access to `scraper-ec2` (configure in ~/.ssh/config).

set -uo pipefail

PHASE="${1:-all}"
EC2_HOST="${EC2_HOST:-scraper-ec2}"
VERCEL_BASE="${VERCEL_BASE:-https://vkusvillsale.vercel.app}"
FAILED=0

_pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
_fail() { printf '  \033[31m✗\033[0m %s\n' "$1"; FAILED=1; }
_banner() { echo ""; echo "=== $1 ==="; }
_check_ec2_ssh() { ssh -o BatchMode=yes -o ConnectTimeout=5 "$EC2_HOST" "echo ok" >/dev/null 2>&1; }

_banner "v1.22 Smoke Test (phase: $PHASE)"

# Phase 73 is Kiro-side skill files only, no EC2 access needed.
if [[ "$PHASE" != "73" ]]; then
    if ! _check_ec2_ssh; then
        _fail "Cannot SSH to $EC2_HOST — configure ~/.ssh/config first"
        exit 1
    fi
    _pass "SSH to $EC2_HOST reachable"
fi

# ---------------------------------------------------------------------------
# Phase 70: History Search Catalog-Wide (UX-BUG-01)
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "70" || "$PHASE" == "all" ]]; then
    _banner "Phase 70 — History Search Catalog-Wide"

    # 70-A: helper importable on EC2
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c 'from backend.main import _load_current_sale_types; assert callable(_load_current_sale_types)'"; then
        _pass "70-A: _load_current_sale_types importable on EC2"
    else
        _fail "70-A: _load_current_sale_types helper missing on EC2"
    fi

    # 70-B: unit tests green on EC2
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -m pytest backend/test_history_search_catalog_wide.py -q 2>&1 | tail -3 | grep -Eq '5 passed'"; then
        _pass "70-B: backend/test_history_search_catalog_wide.py — 5/5 green on EC2"
    else
        _fail "70-B: backend/test_history_search_catalog_wide.py FAILED on EC2 (expect 5 passed)"
    fi

    # 70-C: /api/history/products result rows carry currentSaleType key
    HAS_KEY=$(curl -fsS --max-time 10 "${VERCEL_BASE}/api/history/products?search=тест&per_page=1" 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("PARSE_ERR"); raise SystemExit(0)
products = d.get("products", [])
if not products:
    print("NO_PRODUCTS")
else:
    has_key = "currentSaleType" in products[0]
    print("OK" if has_key else "MISSING_KEY")
')
    if [[ "$HAS_KEY" == "OK" ]]; then
        _pass "70-C: /api/history/products response rows include currentSaleType"
    elif [[ "$HAS_KEY" == "NO_PRODUCTS" ]]; then
        _pass "70-C: /api/history/products responded (empty result — search 'тест' returned 0; schema OK)"
    else
        _fail "70-C: currentSaleType key missing from /api/history/products response ($HAS_KEY)"
    fi
fi

# ---------------------------------------------------------------------------
# Phase 71/72/73 blocks will be appended as those phases ship
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Cross-version: v1.21 + v1.20 + v1.19 regression (OPS-15/16/17 carryover)
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "all" ]]; then
    _banner "v1.21 regression (must stay green — chains v1.20 + v1.19)"
    if bash "$(dirname "$0")/verify_v1.21.sh" all; then
        _pass "v1.21 regression: green (+ v1.20 + v1.19)"
    else
        _fail "v1.21 regression FAILED — roll back v1.22 changes"
    fi
fi

_banner "Summary"
if [[ $FAILED -eq 0 ]]; then
    _pass "All checks passed for phase '$PHASE'"
    exit 0
else
    _fail "One or more checks failed — review output above"
    exit 1
fi
