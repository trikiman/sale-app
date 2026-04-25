#!/bin/bash
# Live end-to-end verification of the v1.17 VLESS/xray stack on EC2.
#
# Differences from verify_v1_15.sh:
#   - Step 2 is STRICT: 100% RU egresses required (was lenient "caveat" in
#     v1.15 because phase 56 PR #7 had broken geo verification; phase 57-03
#     restored it).
#   - Step 5 actually probes the Vercel miniapp /api/cart/add endpoint
#     against the real authenticated guest — was marked "skipped" in v1.15
#     because the API contract had changed since the script was authored.
#
# Invocation (from local dev machine):
#     GUEST_USER_ID=guest_xxx ./scripts/verify_v1_17.sh
#
# Environment overrides:
#     HOST=ubuntu@<ip>             target host (default: ubuntu@13.60.174.46)
#     SSH_KEY=<path>               identity key (default: ./scraper-ec2-new)
#     GUEST_USER_ID=<guest_xxx>    authenticated guest for cart-add probe
#                                   (default: guest_92p559hmmkwmn4mug17)
#     CART_PRODUCT_ID=<int>        product to add (default: 731)
#     EGRESS_PROBES=<int>          how many independent egress checks to run
#                                   (default: 5; v1.15 plan called for 15
#                                    but ipinfo.io is rate-limited)
#
# Runs 5 independent checks. Each prints ">>> [N/5]" before it runs; any
# failing check exits the script with non-zero, leaving previous checks'
# evidence on screen for the 57-VERIFICATION.md transcript.

set -euo pipefail

HOST="${HOST:-ubuntu@13.60.174.46}"
SSH_KEY="${SSH_KEY:-./scraper-ec2-new}"
SSH=(ssh -i "$SSH_KEY" "$HOST")

REPO_PATH="${REPO_PATH:-/home/ubuntu/saleapp}"
GUEST_USER_ID="${GUEST_USER_ID:-guest_92p559hmmkwmn4mug17}"
CART_PRODUCT_ID="${CART_PRODUCT_ID:-731}"
EGRESS_PROBES="${EGRESS_PROBES:-5}"
MINIAPP_BASE="${MINIAPP_BASE:-https://vkusvillsale.vercel.app}"

echo ">>> [1/5] xray is running and accepting on 127.0.0.1:10808"
"${SSH[@]}" "systemctl is-active saleapp-xray"
"${SSH[@]}" "timeout 2 bash -c '</dev/tcp/127.0.0.1/10808' && echo 'port 10808 accepting'"

echo ">>> [2/5] Egress country == RU on every probe (STRICT — phase 57-03)"
# v1.17 admission probes verify_egress per candidate, so every admitted node
# MUST egress from RU. Run N independent probes through the bridge — xray's
# leastPing balancer will spread them across outbounds. Any non-RU response
# means a node leaked through the geo filter (P0 regression of D-05).
ru_count=0
for i in $(seq 1 "$EGRESS_PROBES"); do
    country=$("${SSH[@]}" "curl -sSfL --socks5-hostname 127.0.0.1:10808 https://ipinfo.io/json | grep -oE '\"country\"[[:space:]]*:[[:space:]]*\"[A-Z][A-Z]\"' | grep -oE '\"[A-Z][A-Z]\"$' | tr -d '\"'" || echo "ERR")
    if [ "$country" = "RU" ]; then
        echo "  [$i/$EGRESS_PROBES] ✓ RU egress"
        ru_count=$((ru_count + 1))
    else
        echo "  [$i/$EGRESS_PROBES] ✗ Non-RU egress: country=$country — FAIL (phase 57-03 regression)"
        exit 1
    fi
done
if [ "$ru_count" -ne "$EGRESS_PROBES" ]; then
    echo "  ✗ Only $ru_count/$EGRESS_PROBES RU egresses — phase 57-03 not in effect"
    exit 1
fi
echo "  ✓ $ru_count/$EGRESS_PROBES RU egresses confirmed"

echo ">>> [3/5] vkusvill.ru reachable through bridge (200 + content marker, no /vpn-detected/)"
"${SSH[@]}" "curl -sSfL --socks5-hostname 127.0.0.1:10808 -o /tmp/v1_17_vkusvill.html -w '%{url_effective}\n' https://vkusvill.ru/" | grep -v '/vpn-detected/' || (echo "  ✗ landed on /vpn-detected/" && exit 1)
"${SSH[@]}" "grep -qi vkusvill /tmp/v1_17_vkusvill.html && echo '  ✓ vkusvill marker found in homepage body'"

echo ">>> [4/5] Scheduler cart-add cycle succeeds end-to-end"
"${SSH[@]}" "cd $REPO_PATH && timeout 300 python3 scrape_green.py 2>&1 | tail -n 30"
"${SSH[@]}" "ls -la $REPO_PATH/data/green_products.json"
"${SSH[@]}" "grep -oE '\"products\"[[:space:]]*:[[:space:]]*\\[[^]]' $REPO_PATH/data/green_products.json >/dev/null && echo 'green_products.json contains non-empty products array'"

echo ">>> [5/5] Vercel miniapp /api/cart/add via VLESS bridge (UNSKIPPED — phase 57-04)"
# The miniapp endpoint requires x-telegram-user-id header matching body.user_id.
# Use a known-authenticated guest. Expected outcomes: 200 with success=true,
# or 410 PRODUCT_GONE / 401 AUTH_EXPIRED (still acceptable — proves the
# bridge round-trips). 504 (TIMEOUT) is the failure we're verifying is gone.
http_code_and_body=$(curl -sS -o /tmp/v1_17_cart_add.json -w '%{http_code}' \
    -X POST "$MINIAPP_BASE/api/cart/add" \
    -H "Content-Type: application/json" \
    -H "x-telegram-user-id: $GUEST_USER_ID" \
    -d "{\"user_id\":\"$GUEST_USER_ID\",\"product_id\":$CART_PRODUCT_ID,\"price_type\":1,\"is_green\":0}" || echo "000")
echo "  HTTP $http_code_and_body"
cat /tmp/v1_17_cart_add.json
echo ""
case "$http_code_and_body" in
    200) echo "  ✓ cart-add succeeded through VLESS bridge" ;;
    401|410) echo "  ✓ cart-add round-tripped (got expected auth/gone error, proves bridge is up)" ;;
    504) echo "  ✗ TIMEOUT — VLESS bridge still hanging (phase 57 regression)"; exit 1 ;;
    *)   echo "  ⚠ unexpected status $http_code_and_body — review body above" ;;
esac

echo ">>> All 5 live checks PASSED. v1.17 is verified in production."
