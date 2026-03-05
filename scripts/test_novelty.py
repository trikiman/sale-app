"""
test_novelty.py — picks 10 random products from proposals.json,
sets their category to 'Новинки', saves the file.
Run restore_novelty.py to undo.
"""
import json
import random
import shutil
import sys
import os

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROPOSALS = os.path.join(BASE_DIR, "data", "proposals.json")
BACKUP    = PROPOSALS + ".bak"

with open(PROPOSALS, "r", encoding="utf-8") as f:
    data = json.load(f)

products = data.get("products", [])
if len(products) < 10:
    print(f"Not enough products ({len(products)}), need at least 10")
    sys.exit(1)

# Backup
shutil.copy2(PROPOSALS, BACKUP)
print(f"Backup saved: {BACKUP}")

# Pick 10 random products that are NOT already 'Новинки'
eligible = [p for p in products if p.get("category") != "Новинки"]
chosen = random.sample(eligible, min(10, len(eligible)))

for p in chosen:
    print(f"  [{p.get('type','?')}] {p.get('name','?')[:50]}  →  Новинки")
    p["category"] = "Новинки"

with open(PROPOSALS, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print(f"\nDone — {len(chosen)} products set to 'Новинки'")
print("Refresh the site to see the chip.")
print("Run restore_novelty.bat to undo.")
