#!/usr/bin/env bash
# v1.21 VLESS Pool Self-Healing & Reload Pipeline Smoke Test
# ----------------------------------------------------------
# Runs from local terminal. SSHes to the EC2 scraper host.
# Exits 0 on all-pass, 1 on any-fail. Idempotent.
#
# Usage:
#   ./scripts/verify_v1.21.sh           # all phases + v1.20 + v1.19 regression
#   ./scripts/verify_v1.21.sh 67        # only Phase 67 checks
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

_banner "v1.21 Smoke Test (phase: $PHASE)"

if ! _check_ec2_ssh; then
    _fail "Cannot SSH to $EC2_HOST — configure ~/.ssh/config first"
    exit 1
fi
_pass "SSH to $EC2_HOST reachable"

# ---------------------------------------------------------------------------
# Phase 67: Admitted-Node Self-Healing Loop (REL-13, REL-15)
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "67" || "$PHASE" == "all" ]]; then
    _banner "Phase 67 — Admitted-Node Self-Healing Loop"

    # 67-A: keepalive.reprobe module importable on EC2 with expected exports
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c 'from keepalive.reprobe import start_reprobe_loop, _run_cycle, REPROBE_INTERVAL_S, REPROBE_BOOT_GRACE_S; assert REPROBE_INTERVAL_S == 600.0; assert REPROBE_BOOT_GRACE_S == 120.0'"; then
        _pass "67-A: keepalive.reprobe imports cleanly on EC2 with locked constants"
    else
        _fail "67-A: import or constant check FAILED on EC2"
    fi

    # 67-B: VlessProxyManager exposes record_outcome + success_rate + iter_admitted_hosts
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c '
from vless.manager import VlessProxyManager, SUCCESS_RATE_WINDOW, SUCCESS_RATE_MIN_SAMPLES, SUCCESS_RATE_DEAD_THRESHOLD
assert SUCCESS_RATE_WINDOW == 100
assert SUCCESS_RATE_MIN_SAMPLES == 20
assert SUCCESS_RATE_DEAD_THRESHOLD == 0.1
for method in (\"record_outcome\", \"success_rate\", \"iter_admitted_hosts\", \"_is_node_dead\"):
    assert hasattr(VlessProxyManager, method), f\"missing {method}\"
'"; then
        _pass "67-B: VlessProxyManager exposes REL-15 API with locked constants"
    else
        _fail "67-B: manager API or constants check FAILED on EC2"
    fi

    # 67-C: pytest 6 new tests green on EC2
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -m pytest tests/test_reprobe_loop.py -q 2>&1 | tail -3 | grep -Eq '6 passed'"; then
        _pass "67-C: tests/test_reprobe_loop.py — 6/6 tests green on EC2"
    else
        _fail "67-C: tests/test_reprobe_loop.py FAILED on EC2 (expect 6 passed)"
    fi

    # 67-D: reprobe_cycle_complete event present in proxy_events.jsonl within 25 min of scheduler restart
    REPROBE_OK=$(ssh "$EC2_HOST" "python3 - <<'PY'
import json, os
from datetime import datetime, timezone, timedelta
p = '/home/ubuntu/saleapp/data/proxy_events.jsonl'
if not os.path.exists(p):
    print('NO_FILE'); raise SystemExit(0)
cutoff = datetime.now(timezone.utc) - timedelta(minutes=25)
found = 0
with open(p) as f:
    for ln in f:
        try:
            d = json.loads(ln)
            if d.get('event') == 'reprobe_cycle_complete':
                dt = datetime.fromisoformat(d['ts'].replace('Z','+00:00'))
                if dt >= cutoff:
                    found += 1
        except Exception:
            pass
print(f'OK:{found}' if found >= 1 else 'NO_RECENT_EVENTS')
PY" 2>/dev/null)
    if [[ "$REPROBE_OK" == OK:* ]]; then
        _pass "67-D: reprobe_cycle_complete events present (${REPROBE_OK})"
    else
        _fail "67-D: no reprobe_cycle_complete events in last 25 min — daemon may not be running ($REPROBE_OK)"
    fi
fi

# ---------------------------------------------------------------------------
# Phase 68: xray Auto-Reload on Admission Change (REL-14, OBS-07 partial)
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "68" || "$PHASE" == "all" ]]; then
    _banner "Phase 68 — xray Auto-Reload on Admission Change"

    # 68-A: REL-14 constants locked in vless/manager.py
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c '
from vless.manager import XRAY_RESTART_THROTTLE_S, XRAY_RESTART_TIMEOUT_S, SYSTEMCTL_ARGS
assert XRAY_RESTART_THROTTLE_S == 90.0, XRAY_RESTART_THROTTLE_S
assert XRAY_RESTART_TIMEOUT_S == 30.0, XRAY_RESTART_TIMEOUT_S
assert SYSTEMCTL_ARGS == [\"sudo\", \"systemctl\", \"reload-or-restart\", \"saleapp-xray\"], SYSTEMCTL_ARGS
'"; then
        _pass "68-A: REL-14 constants locked (throttle=90s, timeout=30s, argv shape)"
    else
        _fail "68-A: REL-14 constants check FAILED on EC2"
    fi

    # 68-B: _extract_running_hosts + _reload_xray_systemd on VlessProxyManager
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c '
from vless.manager import VlessProxyManager
for m in (\"_extract_running_hosts\", \"_reload_xray_systemd\"):
    assert hasattr(VlessProxyManager, m), f\"missing {m}\"
'"; then
        _pass "68-B: VlessProxyManager exposes _extract_running_hosts + _reload_xray_systemd"
    else
        _fail "68-B: manager helper methods missing on EC2"
    fi

    # 68-C: sudoers entry deployed (passwordless reload on saleapp-xray only)
    if ssh "$EC2_HOST" "test -r /etc/sudoers.d/saleapp-xray-reload && \
        sudo -n grep -q 'saleapp-xray' /etc/sudoers.d/saleapp-xray-reload 2>/dev/null"; then
        _pass "68-C: /etc/sudoers.d/saleapp-xray-reload present and references saleapp-xray"
    else
        _fail "68-C: sudoers entry missing or unreadable — see 68-VERIFICATION.md NEEDS_OPERATOR-1"
    fi

    # 68-D: unit tests green on EC2
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -m pytest tests/test_xray_reload.py -q 2>&1 | tail -3 | grep -Eq '12 passed'"; then
        _pass "68-D: tests/test_xray_reload.py — 12/12 green on EC2"
    else
        _fail "68-D: tests/test_xray_reload.py FAILED on EC2 (expect 12 passed)"
    fi

    # 68-E: most recent pool_refresh_complete event has the Phase-68 schema
    POOL_EVT=$(ssh "$EC2_HOST" "python3 - <<'PY'
import json, os
p = '/home/ubuntu/saleapp/data/proxy_events.jsonl'
if not os.path.exists(p):
    print('NO_FILE'); raise SystemExit(0)
latest = None
with open(p) as f:
    for ln in f:
        try:
            d = json.loads(ln)
            if d.get('event') == 'pool_refresh_complete':
                latest = d
        except Exception:
            pass
if latest is None:
    print('NO_EVENT')
else:
    required = {'admitted_count','admitted_hosts_before','admitted_hosts_after','added_hosts','removed_hosts','xray_restart_triggered','restart_outcome'}
    missing = required - latest.keys()
    print('OK' if not missing else f'MISSING:{sorted(missing)}')
PY" 2>/dev/null)
    if [[ "$POOL_EVT" == "OK" ]]; then
        _pass "68-E: pool_refresh_complete event carries REL-14 + OBS-07 schema"
    else
        _fail "68-E: pool_refresh_complete event missing or incomplete ($POOL_EVT)"
    fi
fi

# ---------------------------------------------------------------------------
# Cross-version: v1.20 + v1.19 regression (OPS-12 carryover)
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "all" ]]; then
    _banner "v1.20 regression (must stay green)"
    if bash "$(dirname "$0")/verify_v1.20.sh" all; then
        _pass "v1.20 regression: green"
    else
        _fail "v1.20 regression FAILED — roll back v1.21 changes"
    fi

    _banner "v1.19 regression (must stay 24/24 green)"
    if bash "$(dirname "$0")/verify_v1.19.sh" all; then
        _pass "v1.19 regression: 24/24 green"
    else
        _fail "v1.19 regression FAILED — roll back v1.21 changes"
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
