#!/bin/bash
# Live end-to-end verification of the v1.15 VLESS/xray stack on EC2.
#
# Invocation (from local dev machine):
#     PHPSESSID=<cookie> ./scripts/verify_v1_15.sh
#
# Environment overrides:
#     HOST=ubuntu@<ip>      target host (default: ubuntu@13.60.174.46)
#     SSH_KEY=<path>        identity key (default: ./scraper-ec2-new)
#     PHPSESSID=<cookie>    required for check 5 (cart add/remove)
#
# Runs 5 independent checks. Each prints ">>> [N/5]" before it runs; any
# failing check exits the script with non-zero, leaving previous checks'
# evidence on screen for the 56-VERIFICATION.md transcript.

set -euo pipefail

HOST="${HOST:-ubuntu@13.60.174.46}"
SSH_KEY="${SSH_KEY:-./scraper-ec2-new}"
SSH=(ssh -i "$SSH_KEY" "$HOST")

REPO_PATH="${REPO_PATH:-/home/ubuntu/saleapp}"
PHPSESSID="${PHPSESSID:-}"

echo ">>> [1/5] xray is running and accepting on 127.0.0.1:10808"
"${SSH[@]}" "systemctl is-active saleapp-xray"
"${SSH[@]}" "timeout 2 bash -c '</dev/tcp/127.0.0.1/10808' && echo 'port 10808 accepting'"

echo ">>> [2/5] Egress country == RU"
# Use grep instead of nested python to avoid multi-level quote escaping.
# ipinfo.io returns e.g. '"country": "RU"' — the single-quoted extended
# regex tolerates whitespace between the colon and the value.
"${SSH[@]}" 'curl -sSfL --socks5-hostname 127.0.0.1:10808 https://ipinfo.io/json | tee /tmp/v1_15_ipinfo.json && grep -qE "\"country\"[[:space:]]*:[[:space:]]*\"RU\"" /tmp/v1_15_ipinfo.json && echo country=RU confirmed'

echo ">>> [3/5] vkusvill.ru reachable through bridge (200 + content marker)"
"${SSH[@]}" "curl -sSfL --socks5-hostname 127.0.0.1:10808 https://vkusvill.ru/ | grep -qi vkusvill && echo 'marker found'"

echo ">>> [4/5] Scraper cycle succeeds end-to-end"
"${SSH[@]}" "cd $REPO_PATH && timeout 300 python3 scrape_green.py 2>&1 | tail -n 30"
"${SSH[@]}" "ls -la $REPO_PATH/data/green_products.json"
# Count products via grep to avoid double-quote escaping in python -c.
"${SSH[@]}" "grep -oE '\"products\"[[:space:]]*:[[:space:]]*\\[[^]]' $REPO_PATH/data/green_products.json >/dev/null && echo 'green_products.json contains non-empty products array'"

echo ">>> [5/5] Live cart add/remove through bridge"
if [ -z "$PHPSESSID" ]; then
  echo "SKIP: PHPSESSID not set in environment — manual cart probe skipped."
  echo "      Export PHPSESSID before running to include this check."
  exit 0
fi
"${SSH[@]}" "curl -sSfL -X POST https://vkusvillsale.vercel.app/api/cart/add -H 'Content-Type: application/json' -d '{\"product_id\": 33215, \"qty\": 1}' --cookie 'PHPSESSID=$PHPSESSID' | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d); assert d.get(\"ok\"), d'"
"${SSH[@]}" "curl -sSfL -X POST https://vkusvillsale.vercel.app/api/cart/remove -H 'Content-Type: application/json' -d '{\"product_id\": 33215}' --cookie 'PHPSESSID=$PHPSESSID' | python3 -c 'import sys,json; d=json.load(sys.stdin); print(d); assert d.get(\"ok\"), d'"

echo ">>> All 5 live checks PASSED. v1.15 is verified in production."
