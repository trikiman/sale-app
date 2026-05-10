#!/usr/bin/env bash
# v1.20 Cart-Add Latency Smoke Test
# ---------------------------------
# Runs from local terminal. SSHes to the EC2 scraper host. Reports pass/fail
# per criterion. Exits 0 on all-pass, 1 on any-fail. Idempotent.
#
# Usage:
#   ./scripts/verify_v1.20.sh           # runs all phases
#   ./scripts/verify_v1.20.sh 62        # runs only Phase 62 checks
#
# Grows with each phase. Mirrors scripts/verify_v1.19.sh shape exactly so
# operators don't have to re-learn the smoke interface.
#
# Requires: SSH access to `scraper-ec2` host (configure in ~/.ssh/config).

set -uo pipefail

PHASE="${1:-all}"
EC2_HOST="${EC2_HOST:-scraper-ec2}"
VERCEL_BASE="${VERCEL_BASE:-https://vkusvillsale.vercel.app}"
FAILED=0

_pass() { printf '  \033[32m✓\033[0m %s\n' "$1"; }
_fail() { printf '  \033[31m✗\033[0m %s\n' "$1"; FAILED=1; }
_banner() { echo ""; echo "=== $1 ==="; }
_check_ec2_ssh() { ssh -o BatchMode=yes -o ConnectTimeout=5 "$EC2_HOST" "echo ok" >/dev/null 2>&1; }

_banner "v1.20 Smoke Test (phase: $PHASE)"

if ! _check_ec2_ssh; then
    _fail "Cannot SSH to $EC2_HOST — configure ~/.ssh/config first"
    exit 1
fi
_pass "SSH to $EC2_HOST reachable"

# ---------------------------------------------------------------------------
# Phase 62: Sessid Keep-Alive + On-App-Open Warmup
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "62" || "$PHASE" == "all" ]]; then
    _banner "Phase 62 — Sessid Keep-Alive + On-App-Open Warmup"

    # 62-A: keepalive/warmup.py importable on EC2
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -c 'from keepalive.warmup import start_warmup_loop, CART_ADD_ACTIVE, NUDGE_QUEUE' 2>/dev/null"; then
        _pass "62-A: keepalive.warmup imports cleanly on EC2"
    else
        _fail "62-A: keepalive.warmup FAILS to import — deploy incomplete or circular import"
    fi

    # 62-B: data/warmup_events.jsonl exists, schema valid on most recent line, age <= 21 min
    JSONL_OK=$(ssh "$EC2_HOST" "python3 - <<'PY'
import json, os
from datetime import datetime, timezone
p = '/home/ubuntu/saleapp/data/warmup_events.jsonl'
if not os.path.exists(p):
    print('MISSING'); raise SystemExit(0)
last = None
with open(p) as f:
    for ln in f:
        ln = ln.strip()
        if ln:
            last = ln
if not last:
    print('EMPTY'); raise SystemExit(0)
try:
    d = json.loads(last)
except Exception:
    print('BAD_JSON'); raise SystemExit(0)
required = {'timestamp_iso','user_id_hash','trigger','endpoint','success','outcome','latency_ms','sessid_changed'}
missing = required - set(d.keys())
if missing:
    print('MISSING_KEYS:' + ','.join(sorted(missing))); raise SystemExit(0)
dt = datetime.fromisoformat(d['timestamp_iso'].replace('Z','+00:00'))
age_s = (datetime.now(timezone.utc) - dt).total_seconds()
print('OK' if age_s <= 21*60 else f'STALE:{int(age_s)}s')
PY" 2>/dev/null)
    if [[ "$JSONL_OK" == "OK" ]]; then
        _pass "62-B: data/warmup_events.jsonl schema valid + last entry <= 21 min old"
    else
        _fail "62-B: warmup_events.jsonl check: $JSONL_OK"
    fi

    # 62-C: every linked user appears in the most recent cycle window
    COVERED=$(ssh "$EC2_HOST" "python3 - <<'PY'
import json, os, hashlib
from datetime import datetime, timezone, timedelta
base = '/home/ubuntu/saleapp/data'
linked = set()
uc = os.path.join(base, 'user_cookies')
if os.path.isdir(uc):
    for f in os.listdir(uc):
        if f.endswith('.json') and not f.endswith('_browser.json'):
            linked.add(hashlib.sha256(f[:-5].encode()).hexdigest()[:12])
pm_path = os.path.join(base, 'auth', 'user_phone_map.json')
if os.path.exists(pm_path):
    phone_map = json.load(open(pm_path))
    # Hash phone values (canonical session identifier per 62-01 _collect_linked_users)
    for phone in set(str(v) for v in phone_map.values() if v):
        linked.add(hashlib.sha256(phone.encode()).hexdigest()[:12])
p = os.path.join(base, 'warmup_events.jsonl')
if not os.path.exists(p):
    print('NO_JSONL'); raise SystemExit(0)
cutoff = datetime.now(timezone.utc) - timedelta(minutes=25)
seen = set()
with open(p) as f:
    for ln in f:
        try:
            d = json.loads(ln)
            dt = datetime.fromisoformat(d['timestamp_iso'].replace('Z','+00:00'))
            if dt >= cutoff:
                seen.add(d['user_id_hash'])
        except Exception:
            pass
missing = linked - seen
print('OK' if not missing else f'MISSING:{len(missing)}/{len(linked)}')
PY" 2>/dev/null)
    if [[ "$COVERED" == "OK" ]]; then
        _pass "62-C: every linked user warmed in last 25 min"
    else
        _fail "62-C: coverage check: $COVERED"
    fi

    # 62-D: /api/cart/items nudge path (unconditional nudge, no guest-link dependency).
    # Trigger a hit and observe a new JSONL entry appears within 10 s.
    BACKEND_PORT="${BACKEND_PORT:-8000}"
    SMOKE_UID="${SMOKE_USER_ID:-smoke-v1-20}"
    BEFORE_LINES=$(ssh "$EC2_HOST" "wc -l < /home/ubuntu/saleapp/data/warmup_events.jsonl 2>/dev/null | awk '{print \$1}' || echo 0")
    ssh "$EC2_HOST" "curl -s -o /dev/null --max-time 5 'http://127.0.0.1:$BACKEND_PORT/api/cart/items/$SMOKE_UID' 2>/dev/null || true"
    sleep 10
    AFTER_LINES=$(ssh "$EC2_HOST" "wc -l < /home/ubuntu/saleapp/data/warmup_events.jsonl 2>/dev/null | awk '{print \$1}' || echo 0")
    if [[ "$AFTER_LINES" -gt "$BEFORE_LINES" ]]; then
        _pass "62-D: /api/cart/items nudge produced new JSONL entry (+$((AFTER_LINES-BEFORE_LINES)) lines)"
    else
        _fail "62-D: nudge did NOT produce a new JSONL entry (before=$BEFORE_LINES after=$AFTER_LINES) — import error or flag wiring broken"
    fi

    # 62-E: pool-unhealthy unit test green on EC2 (proves skipped_unhealthy path)
    if ssh "$EC2_HOST" "cd /home/ubuntu/saleapp && python3 -m pytest tests/test_keepalive_warmup.py::test_pool_unhealthy_gate -q 2>&1 | tail -3 | grep -q passed"; then
        _pass "62-E: test_pool_unhealthy_gate green on EC2"
    else
        _fail "62-E: test_pool_unhealthy_gate FAILED on EC2"
    fi
fi

# ---------------------------------------------------------------------------
# Cross-phase: v1.19 regression (OPS-11 carryover)
# ---------------------------------------------------------------------------
if [[ "$PHASE" == "all" ]]; then
    _banner "v1.19 regression (must stay 24/24 green)"
    if bash "$(dirname "$0")/verify_v1.19.sh" all; then
        _pass "v1.19 regression: 24/24 green"
    else
        _fail "v1.19 regression FAILED — roll back v1.20 changes"
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
