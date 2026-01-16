import os
import shutil
import sys
import time

"""
Syncs the 'shared' Chrome profile (where you log in) to the dedicated profiles
(green, red, yellow) used by the parallel scrapers.
This ensures they all share the same login session/cookies.
"""

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
SOURCE_PROFILE = os.path.join(DATA_DIR, "chrome_profile_shared")
TARGETS = ["chrome_profile_green", "chrome_profile_red", "chrome_profile_yellow"]

def sync_profiles():
    print("="*60)
    print("🔄 SYNCING CHROME PROFILES")
    print("="*60)
    print(f"Source: {SOURCE_PROFILE}")

    if not os.path.exists(SOURCE_PROFILE):
        print(f"❌ Source profile not found! Please run setup_login.py first.")
        return

    # Check if Chrome is running (simple check)
    if os.path.exists(os.path.join(SOURCE_PROFILE, "SingletonLock")):
        print("⚠️ Warning: Source profile might be in use (SingletonLock exists).")
        print("   Ideally, close Chrome before syncing to ensure database consistency.")

    for target_name in TARGETS:
        target_path = os.path.join(DATA_DIR, target_name)
        print(f"\n➡️ Target: {target_name}")

        try:
            # We use shutil.copytree with dirs_exist_ok=True (Python 3.8+)
            # We exclude temporary/lock files and caches to save time and avoid errors
            shutil.copytree(
                SOURCE_PROFILE,
                target_path,
                dirs_exist_ok=True,
                ignore=shutil.ignore_patterns(
                    "Singleton*",
                    "*.lock",
                    "Cache*",
                    "Code Cache",
                    "Crashpad",
                    "Safe Browsing*",
                    "Dumps",
                    "GPUCache",
                    "DawnCache",
                    "GrShaderCache",
                    "ShaderCache"
                )
            )
            print(f"  ✅ Synced successfully")

        except Exception as e:
            print(f"  ❌ Failed to sync: {e}")

    print("\n" + "="*60)
    print("✅ Sync complete. You can now run the parallel scraper.")

if __name__ == "__main__":
    sync_profiles()
