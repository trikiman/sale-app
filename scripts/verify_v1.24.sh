#!/usr/bin/env bash
# v1.24 Pool Self-Heal Hardening + Outage UX Smoke Test
# -----------------------------------------------------
# Runs from local terminal. SSHes to the EC2 scraper host.
# Exits 0 on all-pass, 1 on any-fail. Idempotent.
#
# Usage:
#   ./scripts/verify_v1.24.sh           # all v1.24 phases + v1.23 + ... + v1.19 regression
#   ./scripts/verify_v1.24.sh 77        # only Phase 77 checks
#   ./scripts/verify_v1.24.sh 78        # only Phase 78 checks (placeholder)
#   ./scripts/verify_v1.24.sh 79        # only Phase 79 checks (placeholder)
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

_banner "v1.24 Smoke Test (phase: $PHASE)"

if [[ "$PHASE" != "skip-ec2" ]]; then
    if ! _check_ec2_ssh; then
        _fail "Cannot SSH to $EC2_HOST — configure ~/.ssh/config first"
        exit 1
    fi
    _pass "SSH to $EC2_HOST reachable"
fi

# ---------------------------------------------------------------------------
# Phase 77: Pool Self-Heal Hardening (REL-16/17/18/19)
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "77" || "$PHASE" == "all" ]]; then
    _banner "Phase 77 — Pool Self-Heal Hardening"

    # 77-A: vless.quarantine module importable on EC2
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c 'from vless import quarantine; assert callable(quarantine.record_probe_failure); assert callable(quarantine.get_quarantined_hosts)'"; then
        _pass "77-A: vless.quarantine module present + callable"
    else
        _fail "77-A: vless.quarantine module missing or broken"
    fi

    # 77-B: MIN_HEALTHY bumped to 10 + REFRESH_MIN_INTERVAL_S constant present
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c 'from vless.manager import MIN_HEALTHY, REFRESH_MIN_INTERVAL_S, RATE_DECLINE_WINDOW_S, RATE_DECLINE_THRESHOLD; assert MIN_HEALTHY == 10; assert REFRESH_MIN_INTERVAL_S == 60.0; assert RATE_DECLINE_WINDOW_S == 300; assert RATE_DECLINE_THRESHOLD == 3'"; then
        _pass "77-B: MIN_HEALTHY=10, REFRESH_MIN_INTERVAL_S=60, RATE_DECLINE_WINDOW_S=300, RATE_DECLINE_THRESHOLD=3"
    else
        _fail "77-B: constants not updated — check vless/manager.py"
    fi

    # 77-C: scheduler_service.py has _is_pool_dead + _emit_scheduler_event
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && grep -q '_is_pool_dead' scheduler_service.py && grep -q 'scheduler_pool_dead' scheduler_service.py"; then
        _pass "77-C: scheduler_service.py has graceful-degrade hooks"
    else
        _fail "77-C: scheduler_service.py missing REL-19 hooks"
    fi

    # 77-D: unit tests green on EC2
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -m pytest tests/test_vless_quarantine.py -q 2>&1 | tail -3 | grep -Eq '15 passed'"; then
        _pass "77-D: tests/test_vless_quarantine.py — 15/15 green on EC2"
    else
        _fail "77-D: quarantine tests not 15/15 green"
    fi

    # 77-E: quarantine file writeable (create + remove test)
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c '
from vless import quarantine
quarantine.clear_all()
quarantine.record_probe_failure(\"smoke.test:443\")
assert quarantine.is_quarantined(\"smoke.test:443\")
quarantine.clear_all()
assert not quarantine.is_quarantined(\"smoke.test:443\")
'"; then
        _pass "77-E: data/pool_quarantine.json write+read+clear works"
    else
        _fail "77-E: quarantine I/O broken on EC2"
    fi

    # 77-F: /api/health/deep pool shape still includes size + min_healthy
    if ssh "$EC2_HOST" "curl -sS --max-time 10 http://127.0.0.1:8000/api/health/deep | python3 -c 'import json,sys; d=json.load(sys.stdin); p=d.get(\"pool\",{}); assert \"size\" in p; assert \"min_healthy\" in p; assert p[\"min_healthy\"] == 10'"; then
        _pass "77-F: /api/health/deep reports min_healthy=10"
    else
        _fail "77-F: /api/health/deep shape regression or backend not restarted"
    fi
fi

# ---------------------------------------------------------------------------
# Phase 78: Stale-State UX (UX-STALE-01/02) — placeholder
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "78" ]]; then
    _banner "Phase 78 — Stale-State UX"
    _pass "Phase 78 placeholder (smoke gates added when 78 ships)"
fi

# ---------------------------------------------------------------------------
# Phase 79: Style Guide v2 Enforcement (TOOL-02/03) — placeholder
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "79" ]]; then
    _banner "Phase 79 — Style Guide v2 Enforcement"
    _pass "Phase 79 placeholder (smoke gates added when 79 ships)"
fi

# ---------------------------------------------------------------------------
# Cross-version regression: v1.23 + v1.22 + v1.21 + v1.20 + v1.19
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "all" ]]; then
    _banner "v1.23 + earlier Regression Guard"
    if [[ -x "$(dirname "$0")/verify_v1.23.sh" ]]; then
        if "$(dirname "$0")/verify_v1.23.sh" all; then
            _pass "v1.23 regression: GREEN"
        else
            _fail "v1.23 regression: FAILED — investigate before shipping v1.24"
        fi
    else
        _fail "scripts/verify_v1.23.sh missing or not executable"
    fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
_banner "Summary"
if [[ $FAILED -eq 0 ]]; then
    printf '\033[32mv1.24 smoke: GREEN\033[0m\n'
    exit 0
else
    printf '\033[31mv1.24 smoke: FAILED — see above\033[0m\n'
    exit 1
fi
