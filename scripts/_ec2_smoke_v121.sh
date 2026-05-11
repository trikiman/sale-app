#!/usr/bin/env bash
# Run ON EC2: smoke-test v1.21 phases locally (no outbound SSH, no Vercel).
# Mirrors scripts/verify_v1.21.sh but assumes we're already on the host.
set -uo pipefail

cd /home/ubuntu/saleapp

FAIL=0
_ok() { printf "  [OK]  %s\n" "$1"; }
_no() { printf "  [FAIL] %s\n" "$1"; FAIL=1; }

echo "=== Phase 67: Admitted-Node Self-Healing Loop ==="

# 67-A
if python3 -c '
from keepalive.reprobe import (
    start_reprobe_loop, _run_cycle,
    REPROBE_INTERVAL_S, REPROBE_BOOT_GRACE_S,
)
assert REPROBE_INTERVAL_S == 600.0, REPROBE_INTERVAL_S
assert REPROBE_BOOT_GRACE_S == 120.0, REPROBE_BOOT_GRACE_S
'; then
    _ok "67-A: keepalive.reprobe imports + locked constants"
else
    _no "67-A"
fi

# 67-B
if python3 -c '
from vless.manager import (
    VlessProxyManager,
    SUCCESS_RATE_WINDOW, SUCCESS_RATE_MIN_SAMPLES, SUCCESS_RATE_DEAD_THRESHOLD,
)
assert SUCCESS_RATE_WINDOW == 100
assert SUCCESS_RATE_MIN_SAMPLES == 20
assert SUCCESS_RATE_DEAD_THRESHOLD == 0.1
for m in ("record_outcome", "success_rate", "iter_admitted_hosts", "_is_node_dead"):
    assert hasattr(VlessProxyManager, m), m
'; then
    _ok "67-B: VlessProxyManager REL-15 surface + constants"
else
    _no "67-B"
fi

# 67-C
if python3 -m pytest tests/test_reprobe_loop.py -q 2>&1 | tail -3 | grep -Eq '6 passed'; then
    _ok "67-C: tests/test_reprobe_loop.py 6/6"
else
    _no "67-C"
fi

# 67-D: reprobe_cycle_complete event within 25 min window
R=$(python3 - <<'PY'
import json, os
from datetime import datetime, timezone, timedelta
p = "/home/ubuntu/saleapp/data/proxy_events.jsonl"
if not os.path.exists(p):
    print("NO_FILE"); raise SystemExit(0)
cutoff = datetime.now(timezone.utc) - timedelta(minutes=25)
found = 0
with open(p) as f:
    for ln in f:
        try:
            d = json.loads(ln)
            if d.get("event") == "reprobe_cycle_complete":
                ts = d.get("ts", "")
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                except Exception:
                    dt = datetime.fromisoformat(ts).replace(tzinfo=timezone.utc)
                if dt >= cutoff:
                    found += 1
        except Exception:
            pass
print(f"OK:{found}" if found >= 1 else "NO_RECENT_EVENTS")
PY
)
if [[ "$R" == OK:* ]]; then
    _ok "67-D: reprobe_cycle_complete ($R)"
else
    _no "67-D: $R"
fi

echo ""
echo "=== Phase 68: xray Auto-Reload on Admission Change ==="

# 68-A
if python3 -c '
from vless.manager import (
    XRAY_RESTART_THROTTLE_S, XRAY_RESTART_TIMEOUT_S, SYSTEMCTL_ARGS,
)
assert XRAY_RESTART_THROTTLE_S == 90.0
assert XRAY_RESTART_TIMEOUT_S == 30.0
assert SYSTEMCTL_ARGS == ["sudo", "systemctl", "reload-or-restart", "saleapp-xray"]
'; then
    _ok "68-A: REL-14 constants locked"
else
    _no "68-A"
fi

# 68-B
if python3 -c '
from vless.manager import VlessProxyManager
for m in ("_extract_running_hosts", "_reload_xray_systemd"):
    assert hasattr(VlessProxyManager, m), m
'; then
    _ok "68-B: _extract_running_hosts + _reload_xray_systemd"
else
    _no "68-B"
fi

# 68-C: sudoers entry
if sudo -n /bin/systemctl is-active saleapp-xray >/dev/null 2>&1; then
    _ok "68-C: sudoers grants passwordless systemctl on saleapp-xray"
else
    _no "68-C: sudoers NOT deployed (68-VERIFICATION.md NEEDS_OPERATOR-1)"
fi

# 68-D
if python3 -m pytest tests/test_xray_reload.py -q 2>&1 | tail -3 | grep -Eq '13 passed'; then
    _ok "68-D: tests/test_xray_reload.py 13/13"
else
    _no "68-D"
fi

# 68-E: latest pool_refresh_complete has Phase 68 schema
R=$(python3 - <<'PY'
import json, os
p = "/home/ubuntu/saleapp/data/proxy_events.jsonl"
if not os.path.exists(p):
    print("NO_FILE"); raise SystemExit(0)
latest = None
with open(p) as f:
    for ln in f:
        try:
            d = json.loads(ln)
            if d.get("event") == "pool_refresh_complete":
                latest = d
        except Exception:
            pass
if latest is None:
    print("NO_EVENT")
else:
    required = {"admitted_count", "admitted_hosts_before", "admitted_hosts_after",
                "added_hosts", "removed_hosts", "xray_restart_triggered",
                "restart_outcome"}
    missing = required - latest.keys()
    print("OK" if not missing else f"MISSING:{sorted(missing)}")
PY
)
if [[ "$R" == "OK" ]]; then
    _ok "68-E: pool_refresh_complete schema complete"
elif [[ "$R" == "NO_EVENT" ]]; then
    _no "68-E: no pool_refresh_complete yet (scheduler hasn't refreshed since deploy)"
else
    _no "68-E: $R"
fi

echo ""
echo "=== Phase 69: Drift Visibility ==="

# 69-A
if python3 -c '
from backend.main import (
    _compute_xray_drift_block,
    _extract_running_xray_hosts_for_health,
    _load_admitted_host_set,
    _DEEP_DRIFT_DEGRADED_S,
    _DEEP_DRIFT_UNHEALTHY_CYCLE_AGE_S,
    _DRIFT_FIRST_SEEN,
)
assert _DEEP_DRIFT_DEGRADED_S == 300
assert _DEEP_DRIFT_UNHEALTHY_CYCLE_AGE_S == 600
'; then
    _ok "69-A: OBS-06 thresholds + helpers"
else
    _no "69-A"
fi

# 69-B
if python3 -m pytest tests/test_xray_drift_health.py -q 2>&1 | tail -3 | grep -Eq '12 passed'; then
    _ok "69-B: tests/test_xray_drift_health.py 12/12"
else
    _no "69-B"
fi

# 69-C: direct curl on backend (port 8000)
R=$(curl -fsS --max-time 10 http://127.0.0.1:8000/api/health/deep 2>/dev/null | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    print("PARSE_ERR"); raise SystemExit(0)
xd = d.get("xray_drift")
if xd is None:
    print("ABSENT")
else:
    required = {"admitted_hosts", "active_outbounds", "drift_count", "drifted_hosts", "first_seen_at"}
    missing = required - xd.keys()
    if missing:
        print("MISSING:" + str(sorted(missing)))
    else:
        print("OK:drift=" + str(xd["drift_count"]) + ",admitted=" + str(xd["admitted_hosts"]) + ",active=" + str(xd["active_outbounds"]))
')
if [[ "$R" == OK:* ]]; then
    _ok "69-C: /api/health/deep xray_drift block ($R)"
else
    _no "69-C: $R"
fi

# 69-D
R=$(python3 - <<'PY'
import json, os
p = "/home/ubuntu/saleapp/data/proxy_events.jsonl"
if not os.path.exists(p):
    print("NO_FILE"); raise SystemExit(0)
latest = None
with open(p) as f:
    for ln in f:
        try:
            d = json.loads(ln)
            if d.get("event") == "pool_refresh_complete":
                latest = d
        except Exception:
            pass
if latest is None:
    print("NO_EVENT")
elif "success_rate_drops" not in latest:
    print("MISSING_KEY")
else:
    drops = latest["success_rate_drops"]
    print("OK:drops=" + str(len(drops)))
PY
)
if [[ "$R" == OK:* ]]; then
    _ok "69-D: success_rate_drops present ($R)"
elif [[ "$R" == "NO_EVENT" ]]; then
    _no "69-D: no pool_refresh_complete yet"
else
    _no "69-D: $R"
fi

echo ""
echo "=== Summary ==="
if [[ $FAIL -eq 0 ]]; then
    echo "ALL PASS"
    exit 0
else
    echo "SOME CHECKS FAILED (see above)"
    exit 1
fi
