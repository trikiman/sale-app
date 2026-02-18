"""
Merge all scraped products into final proposals.json
Run this after all scrapers complete
"""
import json
import os
import sys
from datetime import datetime
from utils import deduplicate_products, normalize_category

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

def merge_products():
    print("🔀 Merging products...")
    
    all_products = []
    
    # Load each color's products
    for color in ['green', 'red', 'yellow']:
        path = os.path.join(DATA_DIR, f"{color}_products.json")
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Handle both formats: array or object with 'products' key
                if isinstance(data, list):
                    products = data
                elif isinstance(data, dict) and 'products' in data:
                    products = data['products']
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
    
    # Count by type
    all_products = deduplicate_products(all_products)

    # Normalize categories for all products (especially Green which often has "Зелёные ценники")
    for p in all_products:
        raw_cat = p.get('category', '')
        p['category'] = normalize_category(raw_cat, p.get('name', ''), p.get('id'))

    green_count = len([p for p in all_products if p['type'] == 'green'])
    red_count = len([p for p in all_products if p['type'] == 'red'])
    yellow_count = len([p for p in all_products if p['type'] == 'yellow'])
    
    # Save results
    output = {
        "updatedAt": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
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
        print(f"  ✅ Copied to miniapp")
    
    print(f"\n{'='*60}")
    print(f"✅ MERGED TOTAL: {len(all_products)} products")
    print(f"  💚 Green: {green_count}")
    print(f"  🔴 Red: {red_count}")
    print(f"  🟡 Yellow: {yellow_count}")
    print(f"{'='*60}")


if __name__ == "__main__":
    merge_products()
