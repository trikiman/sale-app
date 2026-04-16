#!/usr/bin/env python3
"""
Comprehensive health check and auto-fix script for VkusVill Sale Monitor.
Prevents common issues:
- Stale proxy cache
- Zombie Chrome processes
- Database connectivity issues
- Disk space issues
"""
import os
import sys
import sqlite3
import subprocess
import time
from datetime import datetime, timedelta
from pathlib import Path

# Add project to path
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR))

from config import DATABASE_PATH, DATA_DIR

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    RESET = '\033[0m'

def log(status, message):
    color = Colors.GREEN if status == "OK" else Colors.YELLOW if status == "WARN" else Colors.RED
    print(f"{color}[{status}]{Colors.RESET} {message}")

def check_database():
    """Check database connectivity and health"""
    log("INFO", "Checking database...")
    
    if not os.path.exists(DATABASE_PATH):
        log("FAIL", f"Database file not found: {DATABASE_PATH}")
        return False
    
    try:
        conn = sqlite3.connect(DATABASE_PATH)
        c = conn.cursor()
        c.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [r[0] for r in c.fetchall()]
        conn.close()
        
        expected = ['users', 'favorite_products', 'seen_products']
        missing = [t for t in expected if t not in tables]
        
        if missing:
            log("WARN", f"Missing tables: {missing}")
        else:
            log("OK", f"Database OK - {len(tables)} tables")
        return True
    except Exception as e:
        log("FAIL", f"Database error: {e}")
        return False

def check_proxy_cache():
    """Check and refresh proxy cache if stale"""
    log("INFO", "Checking proxy cache...")
    
    try:
        from proxy_manager import ProxyManager, CACHE_TTL
        pm = ProxyManager()
        
        pool_count = pm.pool_count()
        is_stale = pm.is_cache_stale()
        
        if pool_count == 0:
            log("WARN", "Proxy pool empty - refreshing...")
            pm.refresh_proxy_list()
            log("OK", f"Proxy pool refreshed to {pm.pool_count()}")
        elif is_stale:
            log("WARN", f"Proxy cache stale (>24h) - refreshing...")
            pm.refresh_proxy_list()
            log("OK", f"Proxy cache refreshed. Pool: {pm.pool_count()}")
        else:
            log("OK", f"Proxy cache OK. Pool: {pool_count}, Healthy: {pm.pool_healthy()}")
        return True
    except Exception as e:
        log("FAIL", f"Proxy check failed: {e}")
        return False

def check_chrome_processes():
    """Check and kill zombie Chrome processes"""
    log("INFO", "Checking Chrome processes...")
    
    try:
        # Count Chrome processes using tasklist
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq chrome.exe', '/NH'],
            capture_output=True, text=True
        )
        lines = [l for l in result.stdout.split('\n') if 'chrome.exe' in l.lower()]
        count = len(lines)
        
        if count > 20:
            log("WARN", f"Found {count} Chrome processes - cleaning zombies...")
            # Kill Chrome processes older than 2 hours using taskkill
            subprocess.run(
                ['taskkill', '/F', '/IM', 'chrome.exe', '/FI', 'STATUS eq NOT RESPONDING'],
                capture_output=True
            )
            log("OK", "Zombie Chrome processes cleaned")
        else:
            log("OK", f"Chrome processes OK: {count}")
        return True
    except Exception as e:
        log("WARN", f"Chrome check error: {e}")
        return True  # Non-critical

def check_disk_space():
    """Check available disk space"""
    log("INFO", "Checking disk space...")
    
    try:
        import shutil
        stat = shutil.disk_usage(DATA_DIR)
        free_gb = stat.free / (1024**3)
        
        if free_gb < 1:
            log("FAIL", f"Low disk space: {free_gb:.1f} GB remaining!")
            return False
        elif free_gb < 5:
            log("WARN", f"Disk space getting low: {free_gb:.1f} GB remaining")
        else:
            log("OK", f"Disk space OK: {free_gb:.1f} GB free")
        return True
    except Exception as e:
        log("WARN", f"Disk check error: {e}")
        return True

def check_log_rotation():
    """Check if logs need rotation"""
    log("INFO", "Checking logs...")
    
    logs_dir = BASE_DIR / "logs"
    if not logs_dir.exists():
        log("OK", "No logs directory")
        return True
    
    large_logs = []
    for log_file in logs_dir.glob("*.log"):
        size_mb = log_file.stat().st_size / (1024*1024)
        if size_mb > 100:  # 100MB threshold
            large_logs.append((log_file.name, size_mb))
    
    if large_logs:
        log("WARN", f"Large log files: {', '.join(f'{n}({s:.0f}MB)' for n,s in large_logs)}")
    else:
        log("OK", "Log files OK")
    return True

def auto_fix():
    """Attempt to auto-fix common issues"""
    log("INFO", "Running auto-fixes...")
    
    fixes_applied = []
    
    # Fix 1: Refresh stale proxy cache
    try:
        from proxy_manager import ProxyManager
        pm = ProxyManager()
        if pm.is_cache_stale() or pm.pool_count() < 5:
            pm.refresh_proxy_list()
            fixes_applied.append("proxy_cache_refreshed")
    except Exception as e:
        log("WARN", f"Proxy fix failed: {e}")
    
    # Fix 2: Clean non-responding Chrome processes
    try:
        result = subprocess.run(
            ['taskkill', '/F', '/IM', 'chrome.exe', '/FI', 'STATUS eq NOT RESPONDING'],
            capture_output=True, text=True
        )
        if 'terminated' in result.stdout.lower():
            fixes_applied.append("chrome_zombies_cleaned")
    except Exception:
        pass
    
    if fixes_applied:
        log("OK", f"Auto-fixes applied: {', '.join(fixes_applied)}")
    else:
        log("OK", "No fixes needed")
    
    return fixes_applied

def main():
    print("=" * 60)
    print("VkusVill Sale Monitor - Health Check")
    print(f"Time: {datetime.now().isoformat()}")
    print("=" * 60)
    
    # Run checks
    checks = [
        ("Database", check_database),
        ("Proxy Cache", check_proxy_cache),
        ("Chrome Processes", check_chrome_processes),
        ("Disk Space", check_disk_space),
        ("Log Files", check_log_rotation),
    ]
    
    results = {}
    for name, check_fn in checks:
        try:
            results[name] = check_fn()
        except Exception as e:
            log("FAIL", f"{name} check crashed: {e}")
            results[name] = False
    
    # Auto-fix
    print()
    fixes = auto_fix()
    
    # Summary
    print()
    print("=" * 60)
    failed = [n for n, r in results.items() if not r]
    
    if failed:
        log("FAIL", f"Checks failed: {', '.join(failed)}")
        sys.exit(1)
    else:
        log("OK", "All checks passed!")
        sys.exit(0)

if __name__ == "__main__":
    main()
