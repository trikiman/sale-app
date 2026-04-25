#!/bin/bash
# Deploy v1.17 (VLESS timeout hardening: policy + observatory + leastPing,
# aligned timeouts, restored geo verification) to EC2.
#
# Invocation (run from your local dev machine):
#     ./scripts/deploy_v1_17.sh
#
# Environment overrides:
#     HOST=ubuntu@<ip>      target host (default: ubuntu@13.60.174.46)
#     SSH_KEY=<path>        identity key (default: ./scraper-ec2-new)
#
# Exit non-zero on any step failure so this is usable from CI or a manual
# playbook. Each step prints a ">>>" banner; step 7-9 leave the
# `systemctl status` output on screen so operators can visually confirm.
#
# Built on top of deploy_v1_15.sh — adds step 10 (force pool refresh +
# final xray restart) so the new policy + observatory + leastPing config
# is applied immediately without waiting for the 24h timer.

set -euo pipefail

HOST="${HOST:-ubuntu@13.60.174.46}"
SSH_KEY="${SSH_KEY:-./scraper-ec2-new}"
SSH=(ssh -i "$SSH_KEY" "$HOST")
SCP=(scp -i "$SSH_KEY")

REPO_PATH="${REPO_PATH:-/home/ubuntu/saleapp}"

echo ">>> [1/10] Pulling latest code on EC2"
"${SSH[@]}" "cd $REPO_PATH && git fetch origin && git checkout main && git pull origin main"

echo ">>> [2/10] Ensuring Python deps"
"${SSH[@]}" "cd $REPO_PATH && python3 -m pip install -r requirements.txt --upgrade --break-system-packages"

echo ">>> [3/10] Installing xray-core (pinned version)"
"${SSH[@]}" "cd $REPO_PATH && python3 scripts/bootstrap_xray.py"

echo ">>> [4/10] Running initial VLESS pool refresh (>=5 nodes required)"
"${SSH[@]}" "cd $REPO_PATH && python3 -c 'from vless.manager import VlessProxyManager; pm = VlessProxyManager(); n = pm.refresh_proxy_list(); print(f\"admitted {n} nodes\"); assert n >= 5, \"pool below minimum\"'"

echo ">>> [5/10] Installing systemd units"
"${SCP[@]}" systemd/saleapp-xray.service "$HOST:/tmp/"
"${SCP[@]}" systemd/saleapp-scheduler.service.d/10-xray.conf "$HOST:/tmp/10-xray-scheduler.conf"
"${SCP[@]}" systemd/saleapp-backend.service.d/10-xray.conf "$HOST:/tmp/10-xray-backend.conf"
"${SSH[@]}" "sudo mv /tmp/saleapp-xray.service /etc/systemd/system/ && \
                sudo mkdir -p /etc/systemd/system/saleapp-scheduler.service.d \
                             /etc/systemd/system/saleapp-backend.service.d && \
                sudo mv /tmp/10-xray-scheduler.conf /etc/systemd/system/saleapp-scheduler.service.d/10-xray.conf && \
                sudo mv /tmp/10-xray-backend.conf /etc/systemd/system/saleapp-backend.service.d/10-xray.conf"
"${SSH[@]}" "sudo systemctl daemon-reload"

echo ">>> [6/10] Installing health-check cron"
"${SCP[@]}" scripts/xray_healthcheck.sh "$HOST:$REPO_PATH/scripts/"
"${SSH[@]}" "chmod +x $REPO_PATH/scripts/xray_healthcheck.sh"
"${SSH[@]}" "(crontab -l 2>/dev/null | grep -v xray_healthcheck; echo '*/5 * * * * $REPO_PATH/scripts/xray_healthcheck.sh >> $REPO_PATH/logs/xray_healthcheck.log 2>&1') | crontab -"

echo ">>> [7/10] Enabling and starting xray service"
"${SSH[@]}" "sudo systemctl enable saleapp-xray && sudo systemctl restart saleapp-xray"
sleep 3
"${SSH[@]}" "sudo systemctl status saleapp-xray --no-pager -l | head -n 20"

echo ">>> [8/10] Restarting scheduler to pick up xray dependency"
"${SSH[@]}" "sudo systemctl restart saleapp-scheduler"
sleep 3
"${SSH[@]}" "sudo systemctl status saleapp-scheduler --no-pager -l | head -n 10"

echo ">>> [9/10] Restarting backend to pick up xray dependency (powers miniapp /api/cart/add)"
"${SSH[@]}" "sudo systemctl restart saleapp-backend"
sleep 3
"${SSH[@]}" "sudo systemctl status saleapp-backend --no-pager -l | head -n 10"

echo ">>> [10/10] Force pool refresh + final xray restart for new policy/observatory/leastPing"
# v1.17 changed config_gen.py (added policy block, observatory block, swapped
# balancer to leastPing). Without this step the existing active.json is stale
# (pre-observatory) and leastPing falls back to random until the 24h scheduled
# refresh runs. Force a refresh now so the new architecture takes effect
# immediately, then restart xray once more so it reads the fresh active.json.
"${SSH[@]}" "cd $REPO_PATH && python3 -c 'from vless.manager import VlessProxyManager; pm = VlessProxyManager(auto_install_xray=False); pm.refresh_proxy_list(); print(f\"Pool size after refresh: {pm.pool_count()}\")'"
"${SSH[@]}" "sudo systemctl restart saleapp-xray.service"
sleep 3
if ! "${SSH[@]}" "systemctl is-active --quiet saleapp-xray.service"; then
    echo "  ✗ saleapp-xray failed to restart after refresh — aborting"
    "${SSH[@]}" "sudo journalctl -u saleapp-xray -n 50 --no-pager"
    exit 1
fi
echo "  ✓ xray restarted with fresh config (policy + observatory + leastPing applied)"

echo ">>> Deploy complete. Run live verification:"
echo "    ./scripts/verify_v1_17.sh"
