#!/usr/bin/env bash
# v1.19 Reliability Smoke Test
# -----------------------------
# Runs from local terminal. SSHes to the EC2 scraper host. Reports pass/fail
# per criterion. Exits 0 on all-pass, 1 on any-fail. Idempotent.
#
# Usage:
#   ./scripts/verify_v1.19.sh           # runs all phases
#   ./scripts/verify_v1.19.sh 59        # runs only Phase 59 checks
#
# Grows with each phase. Each phase block is gated so partial runs are safe.
#
# Requires: SSH access to `scraper-ec2` host (configure in ~/.ssh/config).
# The Vercel-facing check requires outbound HTTPS from the local machine.

set -uo pipefail

PHASE="${1:-all}"
EC2_HOST="${EC2_HOST:-scraper-ec2}"
VERCEL_BASE="${VERCEL_BASE:-https://vkusvillsale.vercel.app}"
FAILED=0

_pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
_fail() { printf '  \033[31m✗\033[0m %s\n' "$1"; FAILED=1; }

_banner() {
    echo ""
    echo "=== $1 ==="
}

_check_ec2_ssh() {
    ssh -o BatchMode=yes -o ConnectTimeout=5 "$EC2_HOST" "echo ok" >/dev/null 2>&1
}

_banner "v1.19 Smoke Test (phase: $PHASE)"

if ! _check_ec2_ssh; then
    _fail "Cannot SSH to $EC2_HOST — configure ~/.ssh/config first"
    exit 1
fi
_pass "SSH to $EC2_HOST reachable"

# ---------------------------------------------------------------------------
# Phase 59: Corrected Pre-flight VLESS Probe
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "59" || "$PHASE" == "all" ]]; then
    _banner "Phase 59 — Pre-flight VLESS Probe"

    # 59-A: vless/preflight.py deployed
    if ssh "$EC2_HOST" "test -f /home/ubuntu/saleapp/vless/preflight.py"; then
        _pass "59-A: vless/preflight.py exists on EC2"
    else
        _fail "59-A: vless/preflight.py MISSING on EC2 — deploy incomplete"
    fi

    # 59-B: module imports cleanly (no ImportError)
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c 'from vless.preflight import probe_bridge_alive, ProbeResult' 2>/dev/null"; then
        _pass "59-B: vless.preflight imports without error"
    else
        _fail "59-B: vless.preflight FAILS to import — check httpx kwarg compat"
    fi

    # 59-C: timeout floor constant is still >= 12.0 (regression guard)
    FLOOR=$(ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c 'from vless import preflight; print(preflight._PROBE_TIMEOUT_S_FLOOR)'" 2>/dev/null)
    if awk "BEGIN {exit !($FLOOR >= 12.0)}" 2>/dev/null; then
        _pass "59-C: _PROBE_TIMEOUT_S_FLOOR = $FLOOR (>= 12.0)"
    else
        _fail "59-C: _PROBE_TIMEOUT_S_FLOOR = $FLOOR (< 12.0) — PR #25-style regression"
    fi

    # 59-D: scheduler log shows pre-flight probe invoked in recent history
    if ssh "$EC2_HOST" "sudo journalctl -u saleapp-scheduler -n 500 --no-pager 2>/dev/null | grep -q 'Pre-flight probe'"; then
        _pass "59-D: scheduler invokes pre-flight probe (log evidence)"
    else
        _fail "59-D: no 'Pre-flight probe' log in last 500 lines — integration not active"
    fi

    # 59-E: preflight unit tests still green on EC2
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -m pytest tests/test_preflight_timeout_regression.py tests/test_preflight_probe_contract.py tests/test_preflight_rotation_cap.py -q 2>&1 | tail -3 | grep -q 'passed'"; then
        _pass "59-E: preflight pytest suite green on EC2"
    else
        _fail "59-E: preflight pytest suite FAILED on EC2"
    fi

    # 59-F: xray is running (systemd)
    if ssh "$EC2_HOST" "systemctl is-active saleapp-xray 2>/dev/null" | grep -q '^active$'; then
        _pass "59-F: saleapp-xray is active"
    else
        _fail "59-F: saleapp-xray is NOT active"
    fi

    # 59-G: scheduler is running
    if ssh "$EC2_HOST" "systemctl is-active saleapp-scheduler 2>/dev/null" | grep -q '^active$'; then
        _pass "59-G: saleapp-scheduler is active"
    else
        _fail "59-G: saleapp-scheduler is NOT active"
    fi

    # 59-H: Vercel miniapp /api/products returns HTTP 200 (smoke the public edge)
    CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 20 "$VERCEL_BASE/api/products" 2>/dev/null || echo "000")
    if [[ "$CODE" == "200" ]]; then
        _pass "59-H: Vercel /api/products returns HTTP 200 (edge reachable)"
    else
        _fail "59-H: Vercel /api/products returns HTTP $CODE (edge down)"
    fi

    # 59-I: Vercel miniapp cart-add endpoint reachable (no v1.18 regression).
    # Full auth'd cart-add requires a Telegram-bound session and is covered by
    # the manual browser check in 59-VERIFICATION.md. This check confirms the
    # route exists and the backend responds (any 4xx is fine — means routed;
    # only 5xx / 000 means a real problem).
    CODE=$(curl -s -o /dev/null -w "%{http_code}" --max-time 15 -X POST "$VERCEL_BASE/api/cart/add" 2>/dev/null || echo "000")
    if [[ "$CODE" =~ ^(200|400|401|403|422)$ ]]; then
        _pass "59-I: Vercel /api/cart/add reachable (HTTP $CODE; 4xx = authed route works)"
    else
        _fail "59-I: Vercel /api/cart/add HTTP $CODE (5xx/000 indicates backend/route broken)"
    fi
fi

# ---------------------------------------------------------------------------
# Phase 60: Observatory probeURL + Graduated Circuit Breaker
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "60" || "$PHASE" == "all" ]]; then
    _banner "Phase 60 — Observatory probeURL + Circuit Breaker"

    # 60-A: scheduler_state.json gitignored
    if grep -q 'scheduler_state.json' .gitignore 2>/dev/null; then
        _pass "60-A: data/scheduler_state.json is gitignored"
    else
        _fail "60-A: data/scheduler_state.json NOT in .gitignore"
    fi

    # 60-B: xray probeURL references vkusvill.ru on EC2 (built from real config_gen)
    PROBE=$(ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c '
from vless.config_gen import build_xray_config
from vless.parser import VlessNode
n = VlessNode(uuid=\"00000000-0000-0000-0000-000000000000\", host=\"x\", port=443, name=\"x\", reality_pbk=\"a\", reality_sni=\"x\", reality_sid=\"00\", security=\"reality\")
print(build_xray_config([n])[\"observatory\"][\"probeURL\"])
'" 2>/dev/null)
    if [[ "$PROBE" == *"vkusvill.ru"* ]]; then
        _pass "60-B: observatory.probeURL = '$PROBE'"
    else
        _fail "60-B: observatory.probeURL = '$PROBE' (expected vkusvill.ru)"
    fi

    # 60-C: probeInterval <= 60s
    INTERVAL=$(ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c '
from vless.config_gen import build_xray_config
from vless.parser import VlessNode
n = VlessNode(uuid=\"00000000-0000-0000-0000-000000000000\", host=\"x\", port=443, name=\"x\", reality_pbk=\"a\", reality_sni=\"x\", reality_sid=\"00\", security=\"reality\")
print(build_xray_config([n])[\"observatory\"][\"probeInterval\"])
'" 2>/dev/null)
    if [[ "$INTERVAL" == *"s" && "${INTERVAL%s}" -le 60 ]]; then
        _pass "60-C: observatory.probeInterval = $INTERVAL (<= 60s)"
    else
        _fail "60-C: observatory.probeInterval = $INTERVAL (expected <= 60s)"
    fi

    # 60-D: Phase 59 timeout floor regression guard (cross-phase sanity)
    FLOOR=$(ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c 'from vless import preflight; print(preflight._PROBE_TIMEOUT_S_FLOOR)'" 2>/dev/null)
    if awk "BEGIN {exit !($FLOOR >= 12.0)}" 2>/dev/null; then
        _pass "60-D: Phase 59 preflight floor still $FLOOR (>= 12.0)"
    else
        _fail "60-D: Phase 59 preflight floor regressed to $FLOOR"
    fi

    # 60-E: breaker + probeURL pytests green on EC2
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -m pytest tests/test_xray_probe_url_regression.py tests/test_circuit_breaker_state_machine.py -q 2>&1 | tail -3 | grep -q passed"; then
        _pass "60-E: probeURL + breaker pytests green on EC2"
    else
        _fail "60-E: probeURL + breaker pytests FAILED on EC2"
    fi

    # 60-F: scheduler_state.json exists + valid JSON + state in {closed, open, half_open}
    STATE=$(ssh "$EC2_HOST" "test -f /home/ubuntu/saleapp/data/scheduler_state.json && python3 -c 'import json; d=json.load(open(\"/home/ubuntu/saleapp/data/scheduler_state.json\")); print(d[\"state\"])' 2>/dev/null" 2>/dev/null)
    case "$STATE" in
        closed|open|half_open)
            _pass "60-F: data/scheduler_state.json valid (state=$STATE)"
            ;;
        *)
            _fail "60-F: data/scheduler_state.json invalid/missing (state='$STATE')"
            ;;
    esac

    # 60-G: journal evidence of breaker-driven pacing in the last 10 min
    COUNT=$(ssh "$EC2_HOST" "sudo journalctl -u saleapp-scheduler --since '10 minutes ago' --no-pager 2>/dev/null | grep -cE 'Circuit breaker|Loaded breaker state'" 2>/dev/null)
    if [[ "${COUNT:-0}" -gt 0 ]]; then
        _pass "60-G: scheduler emits breaker log lines ($COUNT in last 10 min)"
    else
        _fail "60-G: no breaker log lines in last 10 min — integration inactive"
    fi
fi

# ---------------------------------------------------------------------------
# Future phase 61 appends its block here:
#
# if [[ "$PHASE" == "61" || "$PHASE" == "all" ]]; then
#     _banner "Phase 61 — Deep Health Endpoint + Pool Snapshot"
#     ...
# fi
# ---------------------------------------------------------------------------

_banner "Summary"
if [[ $FAILED -eq 0 ]]; then
    _pass "All checks passed for phase '$PHASE'"
    exit 0
else
    _fail "One or more checks failed — review output above"
    exit 1
fi
