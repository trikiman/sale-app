"""
Merge all scraped products into final proposals.json
Run this after all scrapers complete
"""
import json
import os
import sys
from datetime import datetime
from utils import deduplicate_products, normalize_category, extract_weight, normalize_stock_unit

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def merge_products():
    print("🔀 Merging products...")
    
    all_products = []
    green_live_count = 0  # Live count from VkusVill page (for staleness detection)
    source_timestamps = []  # Track source file ages
    stale_files = []  # Files older than threshold
    STALE_MINUTES = 10  # Consider data stale after 10 minutes
    
    # Load each color's products
    for color in ['green', 'red', 'yellow']:
        path = os.path.join(DATA_DIR, f"{color}_products.json")
        if os.path.exists(path):
            # Check file age
            file_mtime = os.path.getmtime(path)
            file_age_minutes = (datetime.now().timestamp() - file_mtime) / 60
            file_time = datetime.fromtimestamp(file_mtime)
            source_timestamps.append(file_mtime)
            
            if file_age_minutes > STALE_MINUTES:
                stale_files.append(f"{color} ({file_age_minutes:.0f}m old)")
                print(f"  ⚠️ {color}_products.json is STALE ({file_age_minutes:.0f} minutes old, last: {file_time.strftime('%Y-%m-%d %H:%M')})")
            
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Handle both formats: array or object with 'products' key
                if isinstance(data, list):
                    products = data
                elif isinstance(data, dict) and 'products' in data:
                    products = data['products']
                    # Extract live_count metadata from green scraper
                    if color == 'green' and 'live_count' in data:
                        green_live_count = data['live_count']
                        print(f"  📡 Green live count from VkusVill: {green_live_count}")
                else:
                    products = []
                    print(f"  ⚠️ Unknown format in {color} file")
                
                # Ensure each product has the 'type' field
                for p in products:
                    if 'type' not in p:
                        p['type'] = color
                
                all_products.extend(products)
                print(f"  ✅ Loaded {len(products)} {color} products")
        else:
            print(f"  ⚠️ No {color} products file found")
    
    if stale_files:
        print(f"\n  🚨 STALE DATA WARNING: {', '.join(stale_files)}")
        print("  🚨 Run scrapers to refresh!\n")
    
    # Count by type
    all_products = deduplicate_products(all_products)

    # Normalize categories and extract weight from name
    for p in all_products:
        raw_cat = p.get('category', '')
        p['category'] = normalize_category(raw_cat, p.get('name', ''), p.get('id'))
        if not p.get('weight'):
            p['weight'] = extract_weight(p.get('name', ''))
        p['unit'] = normalize_stock_unit(p.get('unit'), p.get('stock'))

    green_count = len([p for p in all_products if p['type'] == 'green'])
    red_count = len([p for p in all_products if p['type'] == 'red'])
    yellow_count = len([p for p in all_products if p['type'] == 'yellow'])
    
    # Use the NEWEST source file timestamp as updatedAt
    # This reflects the most recent successful scraper run
    if source_timestamps:
        newest_ts = max(source_timestamps)  # BUG-L02: renamed from oldest_ts
        from datetime import timezone, timedelta
        _msk = timezone(timedelta(hours=3))  # Moscow timezone
        data_time = datetime.fromtimestamp(newest_ts, tz=_msk).strftime("%Y-%m-%d %H:%M:%S")
    else:
        from datetime import timezone, timedelta
        _msk = timezone(timedelta(hours=3))
        data_time = datetime.now(tz=_msk).strftime("%Y-%m-%d %H:%M:%S")
    
    # BUG-E03: Reuse already-computed green_count instead of re-reading file
    green_path = os.path.join(DATA_DIR, "green_products.json")
    green_missing = not os.path.exists(green_path) or green_count == 0

    # Save results
    output = {
        "updatedAt": data_time,
        "greenLiveCount": green_live_count,
        "greenMissing": green_missing,
        "dataStale": len(stale_files) > 0,
        "staleInfo": stale_files if stale_files else None,
        "products": all_products
    }
    
    # Save to data folder
    proposals_path = os.path.join(DATA_DIR, "proposals.json")
    with open(proposals_path, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # Copy to miniapp
    miniapp_path = os.path.join(BASE_DIR, "miniapp", "public", "data.json")
    if os.path.exists(os.path.dirname(miniapp_path)):
        with open(miniapp_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print("  ✅ Copied to miniapp")
    
    # Record sale history (never fail the merge if this errors)
    try:
        from database.sale_history import record_sale_appearances
        record_sale_appearances(all_products)
    except Exception as e:
        print(f"  ⚠️ Sale history recording failed: {e}")
    
    print(f"\n{'='*60}")
    print(f"✅ MERGED TOTAL: {len(all_products)} products")
    print(f"  💚 Green: {green_count}")
    print(f"  🔴 Red: {red_count}")
    print(f"  🟡 Yellow: {yellow_count}")
    if stale_files:
        print(f"  ⚠️ DATA IS STALE — updatedAt: {data_time}")
    print(f"{'='*60}")


if __name__ == "__main__":
    merge_products()
