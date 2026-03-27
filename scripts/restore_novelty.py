"""restore_novelty.py — restores proposals.json from .bak"""
import shutil
import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPOSALS = os.path.join(BASE_DIR, "data", "proposals.json")
BACKUP    = PROPOSALS + ".bak"

if not os.path.exists(BACKUP):
    print("No backup found — nothing to restore.")
    sys.exit(1)

shutil.copy2(BACKUP, PROPOSALS)
os.remove(BACKUP)
print("Restored proposals.json from backup.")
print("Refresh the site — 'Новинки' chip should be gone.")
