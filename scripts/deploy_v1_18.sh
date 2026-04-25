#!/bin/bash
# Deploy v1.18 (phase 58: multi-provider geo resolver + scraper CDP-WS recovery)
# to EC2.
#
# Invocation (run from your local dev machine):
#     ./scripts/deploy_v1_18.sh
#
# Environment overrides:
#     HOST=ubuntu@<ip>      target host (default: ubuntu@13.60.174.46)
#     SSH_KEY=<path>        identity key (default: ./scraper-ec2-new)
#
# v1.18 ships pure Python changes — no new systemd units, no new
# dependencies. Compared to deploy_v1_17.sh this script drops:
#   - bootstrap_xray (xray binary unchanged)
#   - systemd unit installation (units unchanged)
#   - healthcheck cron install (already present)
# and keeps:
#   - git pull
#   - pip install -r requirements.txt (in case any deps shifted)
#   - force pool refresh (exercises the new multi-provider geo resolver)
#   - service restart (picks up vless/xray.py + scrape_green.py changes)

set -euo pipefail

HOST="${HOST:-ubuntu@13.60.174.46}"
SSH_KEY="${SSH_KEY:-./scraper-ec2-new}"
SSH=(ssh -i "$SSH_KEY" "$HOST")

REPO_PATH="${REPO_PATH:-/home/ubuntu/saleapp}"

echo ">>> [1/5] Pulling latest code on EC2"
"${SSH[@]}" "cd $REPO_PATH && git fetch origin && git checkout main && git pull origin main"

echo ">>> [2/5] Ensuring Python deps (no-op unless requirements.txt changed)"
"${SSH[@]}" "cd $REPO_PATH && python3 -m pip install -r requirements.txt --upgrade --break-system-packages"

echo ">>> [3/5] Force pool refresh — exercises multi-provider geo resolver (phase 58-01)"
# The first refresh after deploy is the one that proves the chain:
# the legacy single-provider path would fail ~70% of probes with
# rejected_reason=429, capping the admitted pool. With the chain
# (ipinfo.io → ipapi.co → ip-api.com) the same source list should
# admit a meaningfully larger pool.
"${SSH[@]}" "cd $REPO_PATH && python3 -c 'from vless.manager import VlessProxyManager; pm = VlessProxyManager(auto_install_xray=False); n = pm.refresh_proxy_list(); print(f\"Pool size after refresh: {pm.pool_count()} (admitted {n})\")'"

echo ">>> [4/5] Restarting services to pick up the new code"
"${SSH[@]}" "sudo systemctl restart saleapp-xray.service"
sleep 3
if ! "${SSH[@]}" "systemctl is-active --quiet saleapp-xray.service"; then
    echo "  ✗ saleapp-xray failed to restart — aborting"
    "${SSH[@]}" "sudo journalctl -u saleapp-xray -n 50 --no-pager"
    exit 1
fi
"${SSH[@]}" "sudo systemctl restart saleapp-scheduler.service"
"${SSH[@]}" "sudo systemctl restart saleapp-backend.service"
sleep 3
"${SSH[@]}" "systemctl is-active saleapp-xray saleapp-scheduler saleapp-backend"

echo ">>> [5/5] Deploy complete. Run live verification:"
echo "    ./scripts/verify_v1_18.sh"
