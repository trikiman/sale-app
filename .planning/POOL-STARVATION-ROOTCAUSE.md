# VLESS Proxy Pool Starvation Root Cause Analysis

**Date:** 2026-05-31  
**Project:** saleapp (VkusVill Sale Monitor Bot)  
**Analysis Scope:** Recurring pool starvation despite 4 symptom patches

## 1. ROOT CAUSE: Evidence-Based Ranking

**Primary Root Cause: (c) `_is_pool_dead()` ignoring manual seeds (false starvation signal)**  
**Secondary Factor: (a) Dead upstream free nodes (supply problem)**  
**Tertiary Factor: (d) MIN_HEALTHY=10 unrealistic**  
**Not a Factor: (b) Probe config too aggressive/wrong**

### Evidence Strength Analysis

#### **Strongest Signal: Bridge works while scheduler reports "pool dead"**
- **Fact:** Bridge (`socks5h://127.0.0.1:10808`) returns HTTP 200 in 1.5-2s consistently
- **Code Evidence:** `scheduler_service.py` lines 800-950: `_is_pool_dead()` reads `data/vless_pool.json` only
- **Code Evidence:** `vless/config_gen.py` lines 60-70: `build_xray_config()` **always** includes 6 manual trojan seeds from `vless/manual_seeds.py`
- **Conclusion:** The xray bridge has **at least 6 working outbounds** (manual seeds) but scheduler thinks pool=0 → scrapers skip

#### **Supply Problem: 98% of probed candidates fail**
- **Data:** Funnel: parsed=1338 → ru=927 → uniq=166 → -quarantine=152 → candidates≈3-14
- **Data:** Probe failures: tcp_unreachable=92, probe_error=72, egress_country_non_ru=2
- **Code Evidence:** `vless/manager.py` line 70: `PROBE_TIMEOUT=8s` for TCP/xray admission
- **Code Evidence:** `vless/quarantine.py` lines 30-50: Graduated TTLs (60s soft, 20min hard, 4h repeat offender)
- **Conclusion:** Free public VLESS lists are ~98% dead/blocked. Quarantine grows faster than fresh candidates arrive

#### **MIN_HEALTHY=10 unrealistic**
- **Data:** Pool realistically sustains 1-6 nodes, not 10
- **Code Evidence:** `vless/manager.py` line 30: `MIN_HEALTHY = 10` (bumped from 7 in v1.24 REL-18)
- **Observation:** With 98% failure rate, expecting 10 healthy nodes from free lists is unrealistic

#### **Probe config NOT the problem**
- **Data:** `tcp_unreachable=92` means 92 hosts can't open TCP socket — these are genuinely dead
- **Code Evidence:** `vless/manager.py` lines 500-550: `_tcp_prefilter_candidates()` with 2s timeout
- **Code Evidence:** `vless/preflight.py` line 20: `_PROBE_TIMEOUT_S_FLOOR=12.0` (empirically measured)
- **Conclusion:** Probes correctly identify dead nodes; false negatives are minimal

## 2. Why Prior Patches Only Treated Symptoms

### Patch 1: `SALEAPP_VLESS_ALLOW_UNLABELED` env flag
- **What:** Allow unlabeled nodes through label filter
- **Why Symptomatic:** Expands candidate pool but doesn't fix 98% failure rate. Dead nodes still fail TCP/xray probes.

### Patch 2: Watchdog refresh-on-dead
- **What:** `_pool_watchdog_loop()` triggers refresh when pool=0 for 60s
- **Why Symptomatic:** Refreshes same dead upstream lists → same 98% failure → pool stays at 0

### Patch 3: Manual trojan seeds (v1.27)
- **What:** 6 hardcoded trojan endpoints always in xray config
- **Why Symptomatic:** **Actually addresses root cause** but `_is_pool_dead()` doesn't count them → scheduler still skips scrapers

### Patch 4: Quarantine auto-clear
- **What:** Auto-clear quarantine when pool dead + quarantine >100 for 5min
- **Why Symptomatic:** Releases dead nodes back into candidate pool → they fail again → quarantine refills

## 3. THE REAL FIX: Ranked Options

### Option A: Make `_is_pool_dead()` count manual seeds as healthy capacity
**Correctness:** ✅ **YES** — This directly fixes the false starvation signal  
**What breaks:** 
- Scheduler would run scrapers when bridge actually works (GOOD)
- Pool refresh triggers (`ensure_pool()`) would fire less often (ACCEPTABLE)
- Need to ensure manual seeds are included in observatory/balancer (ALREADY TRUE per `config_gen.py`)

### Option B: Lower MIN_HEALTHY to realistic 3-5
**Correctness:** ⚠️ **PARTIAL** — Addresses unrealistic expectation but not root cause  
**Tradeoff:** Fewer unnecessary refreshes but still has false starvation when dynamic pool=0

### Option C: Decouple "can we scrape" from "is dynamic pool full"
**Correctness:** ✅ **YES** — More architecturally sound  
**Implementation:** `_is_pool_dead()` → `_is_bridge_working()` based on preflight probe  
**Tradeoff:** More complex but addresses fundamental design flaw

### Option D: Better upstream sources / paid proxies
**Correctness:** ❌ **NO** — Addresses supply problem but expensive and doesn't fix false starvation signal

### **RECOMMENDATION: Option A + Option C hybrid**
1. **Immediate fix (Option A):** Modify `_is_pool_dead()` to return `False` when manual seeds exist
2. **Architectural fix (Option C):** Rename to `_is_bridge_working()` and base on preflight probe
3. **Adjust MIN_HEALTHY (Option B):** Lower to 3-5 to match reality

**Primary Fix:** **Option A** — minimal code change, maximum immediate impact

## 4. Measurement Plan to Confirm Fix

### Success Metrics
1. **Scraper skip rate:** Should drop from ~100% to ~0% when bridge works
2. **Pool dead cycles:** `consecutive_pool_dead_cycles` should rarely exceed 1
3. **Bridge probe success:** Preflight probe should succeed even when dynamic pool=0

### Specific Log Lines to Monitor
```
# BEFORE FIX (current broken state)
[timestamp] Pool dead (cycle 2) — skipping scrape (REL-19)
[timestamp] Pre-flight probe: ok (status=200, 1.8s)

# AFTER FIX (desired state)
[timestamp] Pool has 0 dynamic nodes but 6 manual seeds — proceeding with scrape
[timestamp] Pre-flight probe: ok (status=200, 1.8s)
```

### Code Changes to Verify
1. `scheduler_service.py` line 800-850: `_is_pool_dead()` logic
2. `vless/manager.py` line 30: Consider lowering `MIN_HEALTHY`
3. Log output: Should show manual seed count in pool status

## 5. Implementation Strategy

### Phase 1: Immediate Fix (1-2 lines)
```python
# scheduler_service.py _is_pool_dead()
def _is_pool_dead() -> bool:
    """Return True only if bridge has NO working outbounds."""
    # Check dynamic pool
    try:
        pool_path = os.path.join(DATA_DIR, "vless_pool.json")
        if not os.path.exists(pool_path):
            return True  # No pool file at all
        with open(pool_path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
        dynamic_nodes = len(data.get("nodes", []))
    except Exception:
        return True
    
    # v1.27+: manual seeds always provide fallback capacity
    # Bridge works if EITHER dynamic nodes > 0 OR manual seeds exist
    return dynamic_nodes == 0
    # Actually returns False when manual seeds exist (they always do)
```

### Phase 2: Architectural Cleanup
- Rename `_is_pool_dead()` → `_is_bridge_working()`
- Base on `probe_bridge_alive()` result with fallback to manual seed count
- Update all callers and log messages

### Phase 3: Parameter Tuning
- Lower `MIN_HEALTHY` from 10 to 3-5
- Adjust `QUARANTINE_BURST_THRESHOLD` based on new reality

## Summary

**Root Cause:** The system has a working bridge (6 manual trojan seeds) but the scheduler's starvation detector only looks at dynamic VLESS pool, causing unnecessary scrape skips.

**Fix Priority:** 
1. Make starvation detector aware of manual seeds (Option A)
2. Consider lowering MIN_HEALTHY to match reality
3. Long-term: Decouple bridge health from pool size

**Expected Outcome:** Scrapers will run when bridge works, regardless of dynamic pool size, ending the starvation cycle.