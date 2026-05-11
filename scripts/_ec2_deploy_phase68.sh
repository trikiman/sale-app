#!/usr/bin/env bash
# Run ON EC2 to deploy Phase 68 sudoers entry and force a pool_refresh_complete event.
set -uo pipefail

cd /home/ubuntu/saleapp

echo "== Step 1: Write sudoers entry =="
SUDOERS_CONTENT='ubuntu ALL=(root) NOPASSWD: /bin/systemctl reload-or-restart saleapp-xray, /bin/systemctl restart saleapp-xray'
echo "$SUDOERS_CONTENT" | sudo tee /etc/sudoers.d/saleapp-xray-reload >/dev/null
sudo chmod 0440 /etc/sudoers.d/saleapp-xray-reload

echo "== Step 2: Validate with visudo =="
sudo visudo -c -f /etc/sudoers.d/saleapp-xray-reload
if [ $? -ne 0 ]; then
    echo "FAIL: visudo rejected the file"
    sudo rm -f /etc/sudoers.d/saleapp-xray-reload
    exit 1
fi

echo "== Step 3: Dry-run passwordless check =="
if sudo -n /bin/systemctl is-active saleapp-xray >/dev/null 2>&1; then
    echo "OK: passwordless sudo on saleapp-xray confirmed"
else
    echo "FAIL: sudo -n still requires password"
    exit 1
fi

echo "== Step 4: Force a pool refresh to land pool_refresh_complete event =="
python3 - <<'PY'
import sys, time
sys.path.insert(0, "/home/ubuntu/saleapp")
from vless.manager import VlessProxyManager
pm = VlessProxyManager(log_func=lambda m: print("[VLESS]", m))
before = pm.pool_count()
print(f"Pool before refresh: {before}")
pm.refresh_proxy_list()
after = pm.pool_count()
print(f"Pool after refresh: {after}")
PY

echo ""
echo "== Step 5: Confirm fresh pool_refresh_complete =="
tail -n 200 data/proxy_events.jsonl | grep '"event": "pool_refresh_complete"' | tail -1 | python3 -m json.tool

echo ""
echo "Deploy complete."
