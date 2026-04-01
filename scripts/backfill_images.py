#!/usr/bin/env python3
"""One-time backfill: populate image_url in product_catalog from scraped data files.

Reads all scraped product JSON files that contain image URLs and updates
the product_catalog table for matching product IDs.
"""
import json
import sqlite3
import os
import sys

# Determine paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)  # Go up from scripts/ to project root
DATA_DIR = os.path.join(PROJECT_DIR, "data")
DB_PATH = os.path.join(PROJECT_DIR, "database", "sale_monitor.db")

# Files that contain product images
IMAGE_SOURCE_FILES = [
    "products.json",          # main products (current green)
    "green_products.json",    # green tag products
    "red_products.json",      # red tag products
    "yellow_products.json",   # yellow tag products
]

def main():
    if not os.path.exists(DB_PATH):
        print(f"❌ Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    c = conn.cursor()

    # Count products missing images
    c.execute("SELECT COUNT(*) FROM product_catalog WHERE image_url IS NULL OR image_url = ''")
    missing_before = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM product_catalog")
    total = c.fetchone()[0]
    print(f"📊 Products: {total} total, {missing_before} missing images")

    # Collect image URLs from all scraped data files
    images = {}  # product_id -> image_url
    for filename in IMAGE_SOURCE_FILES:
        filepath = os.path.join(DATA_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  ⏭️ {filename} not found, skipping")
            continue
        
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            # Handle both list and dict formats
            products = data if isinstance(data, list) else data.get("products", data)
            if isinstance(products, dict):
                products = list(products.values())
            
            count = 0
            for p in products:
                pid = str(p.get("id", ""))
                img = p.get("image", "") or p.get("image_url", "")
                if pid and img and img.startswith("http"):
                    images[pid] = img
                    count += 1
            
            print(f"  ✅ {filename}: {count} images found")
        except Exception as e:
            print(f"  ❌ {filename}: {e}")

    if not images:
        print("❌ No images found in any source file")
        sys.exit(1)

    print(f"\n🔄 Backfilling {len(images)} image URLs...")

    # Update product_catalog where image_url is missing
    updated = 0
    for pid, img_url in images.items():
        c.execute("""
            UPDATE product_catalog 
            SET image_url = ? 
            WHERE product_id = ? AND (image_url IS NULL OR image_url = '')
        """, (img_url, pid))
        if c.rowcount > 0:
            updated += 1

    conn.commit()

    # Count remaining missing
    c.execute("SELECT COUNT(*) FROM product_catalog WHERE image_url IS NULL OR image_url = ''")
    missing_after = c.fetchone()[0]

    conn.close()

    print(f"\n✅ Backfill complete:")
    print(f"   Updated: {updated} products")
    print(f"   Missing before: {missing_before}")
    print(f"   Missing after:  {missing_after}")
    print(f"   Coverage: {total - missing_after}/{total} ({(total - missing_after) / total * 100:.1f}%)")

if __name__ == "__main__":
    main()
