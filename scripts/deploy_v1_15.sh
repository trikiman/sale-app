#!/bin/bash
# Deploy v1.15 (VLESS + xray-core bridge) to EC2.
#
# Invocation (run from your local dev machine):
#     ./scripts/deploy_v1_15.sh
#
# Environment overrides:
#     HOST=ubuntu@<ip>      target host (default: ubuntu@13.60.174.46)
#     SSH_KEY=<path>        identity key (default: ./scraper-ec2-new)
#
# Exit non-zero on any step failure so this is usable from CI or a manual
# playbook. Each step prints a ">>>" banner; step 7 and 8 leave the
# `systemctl status` output on screen so operators can visually confirm.

set -euo pipefail

HOST="${HOST:-ubuntu@13.60.174.46}"
SSH_KEY="${SSH_KEY:-./scraper-ec2-new}"
SSH=(ssh -i "$SSH_KEY" "$HOST")
SCP=(scp -i "$SSH_KEY")

REPO_PATH="${REPO_PATH:-/home/ubuntu/saleapp}"

echo ">>> [1/9] Pulling latest code on EC2"
"${SSH[@]}" "cd $REPO_PATH && git fetch origin && git checkout main && git pull origin main"

echo ">>> [2/9] Ensuring Python deps"
# Ubuntu 24.04 enforces PEP 668 on system python, so --break-system-packages
# is required. The EC2 scheduler.service runs /usr/bin/python3 directly (no
# venv), so we must install into the system site-packages.
"${SSH[@]}" "cd $REPO_PATH && python3 -m pip install -r requirements.txt --upgrade --break-system-packages"

echo ">>> [3/9] Installing xray-core (pinned version)"
"${SSH[@]}" "cd $REPO_PATH && python3 scripts/bootstrap_xray.py"

echo ">>> [4/9] Running initial VLESS pool refresh (>=5 nodes required)"
"${SSH[@]}" "cd $REPO_PATH && python3 -c 'from vless.manager import VlessProxyManager; pm = VlessProxyManager(); n = pm.refresh_proxy_list(); print(f\"admitted {n} nodes\"); assert n >= 5, \"pool below minimum\"'"

echo ">>> [5/9] Installing systemd units"
# saleapp-xray.service is brand new, so we install it as a full unit.
# saleapp-scheduler.service and saleapp-backend.service already exist on
# EC2 — scheduler wraps python3 in xvfb-run for Chromium cart-add, backend
# runs uvicorn. Instead of overwriting those units (which would drop their
# existing ExecStart/Environment), we install drop-in overrides that add
# the xray dependency while preserving the current unit definitions.
"${SCP[@]}" systemd/saleapp-xray.service "$HOST:/tmp/"
"${SCP[@]}" systemd/saleapp-scheduler.service.d/10-xray.conf "$HOST:/tmp/10-xray-scheduler.conf"
"${SCP[@]}" systemd/saleapp-backend.service.d/10-xray.conf "$HOST:/tmp/10-xray-backend.conf"
"${SSH[@]}" "sudo mv /tmp/saleapp-xray.service /etc/systemd/system/ && \
                sudo mkdir -p /etc/systemd/system/saleapp-scheduler.service.d \
                             /etc/systemd/system/saleapp-backend.service.d && \
                sudo mv /tmp/10-xray-scheduler.conf /etc/systemd/system/saleapp-scheduler.service.d/10-xray.conf && \
                sudo mv /tmp/10-xray-backend.conf /etc/systemd/system/saleapp-backend.service.d/10-xray.conf"
"${SSH[@]}" "sudo systemctl daemon-reload"

echo ">>> [6/9] Installing health-check cron"
"${SCP[@]}" scripts/xray_healthcheck.sh "$HOST:$REPO_PATH/scripts/"
"${SSH[@]}" "chmod +x $REPO_PATH/scripts/xray_healthcheck.sh"
"${SSH[@]}" "(crontab -l 2>/dev/null | grep -v xray_healthcheck; echo '*/5 * * * * $REPO_PATH/scripts/xray_healthcheck.sh >> $REPO_PATH/logs/xray_healthcheck.log 2>&1') | crontab -"

echo ">>> [7/9] Enabling and starting xray service"
"${SSH[@]}" "sudo systemctl enable saleapp-xray && sudo systemctl restart saleapp-xray"
sleep 3
"${SSH[@]}" "sudo systemctl status saleapp-xray --no-pager -l | head -n 20"

echo ">>> [8/9] Restarting scheduler to pick up xray dependency"
"${SSH[@]}" "sudo systemctl restart saleapp-scheduler"
sleep 3
"${SSH[@]}" "sudo systemctl status saleapp-scheduler --no-pager -l | head -n 10"

echo ">>> [9/9] Restarting backend to pick up xray dependency (powers miniapp /api/cart/add)"
"${SSH[@]}" "sudo systemctl restart saleapp-backend"
sleep 3
"${SSH[@]}" "sudo systemctl status saleapp-backend --no-pager -l | head -n 10"

echo ">>> Deploy complete. Run live verification:"
echo "    ./scripts/verify_v1_15.sh"
