#!/bin/bash
# Cron-scheduled safeguard: if saleapp-xray reports active but the SOCKS5
# port is not accepting, restart the unit. Catches silent hangs where the
# xray process is still alive but its listener has crashed.
#
# Install via:
#     */5 * * * * /home/ubuntu/saleapp/scripts/xray_healthcheck.sh >> \
#         /home/ubuntu/saleapp/logs/xray_healthcheck.log 2>&1

set -eo pipefail

PORT="${XRAY_INBOUND_PORT:-10808}"

if systemctl is-active --quiet saleapp-xray; then
  if ! timeout 2 bash -c "</dev/tcp/127.0.0.1/$PORT" 2>/dev/null; then
    echo "$(date -Iseconds) xray active but port $PORT unresponsive — restarting" >&2
    sudo systemctl restart saleapp-xray
  fi
fi
