"""
Merge all scraped products into final proposals.json
Run this after all scrapers complete
"""
import json
import os
import sys
import tempfile
from datetime import datetime
from utils import deduplicate_products, normalize_category, extract_weight, normalize_stock_unit

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")


def _sanitize_subgroup_label(value):
    if not value:
        return None
    label = str(value).replace('\xa0', ' ').replace('\u00a0', ' ').strip()
    folded = label.casefold()
    if '%' in label:
        return None
    if 'скидк' in folded:
        return None
    return label


def _atomic_write_json(path: str, data: dict) -> None:
    """Atomically write a JSON file: temp file in same dir, then os.replace.

    v1.27 hotfix 2026-05-26: user reported greens count flickering 90→0→84
    on mobile during a refresh. Root cause: open(path, 'w') truncates the
    file to 0 bytes BEFORE writing new content. The /api/products endpoint
    reading during that ~50ms window sees an empty/partial file (its 2-try
    retry just hits the same partial state). Atomic write means readers
    always see either the OLD complete file or the NEW complete file —
    never an in-between empty state.
    """
    directory = os.path.dirname(path) or "."
    fd, tmp_path = tempfile.mkstemp(prefix=".", suffix=".tmp", dir=directory)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp_path, path)
    except Exception:
        # Best-effort cleanup if the temp file survived but rename failed.
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


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

    # Normalize categories, extract weight, and add group/subgroup from category_db
    catdb = {}
    catdb_path = os.path.join(DATA_DIR, "category_db.json")
    if os.path.exists(catdb_path):
        try:
            with open(catdb_path, 'r', encoding='utf-8') as f:
                catdb_data = json.load(f)
                catdb = catdb_data.get('products', {})
            print(f"  📚 Loaded category_db with {len(catdb)} products")
        except Exception as e:
            print(f"  ⚠️ Failed to load category_db: {e}")
    
    for p in all_products:
        raw_cat = p.get('category', '')
        p['category'] = normalize_category(raw_cat, p.get('name', ''), p.get('id'))
        if not p.get('weight'):
            p['weight'] = extract_weight(p.get('name', ''))
        p['unit'] = normalize_stock_unit(p.get('unit'), p.get('stock'))
        
        # Add group/subgroup from category_db
        pid = str(p.get('id', ''))
        if pid and pid in catdb:
            info = catdb[pid]
            # Support both old format (category) and new format (group/subgroups)
            p['group'] = info.get('group', info.get('category', ''))
            subgroups = info.get('subgroups', [])
            p['subgroup'] = _sanitize_subgroup_label(subgroups[0]) if subgroups else None
        else:
            p['group'] = p.get('category', '') or 'Без категории'
            p['subgroup'] = None

    # v1.27.1: NEW-product detection with sliding 30-min window. Earlier
    # version flagged isNew=true only for the *single* merge cycle right
    # after appearance, then the flag flipped back to false on the next
    # cycle (~5 min later). Users who didn't reload the app within that
    # tiny window saw nothing — reported on 2026-05-25 09:27 ("on mobile
    # NEW feature didnt work at all"). Mobile users typically open the
    # app every few hours, not every 5 min.
    #
    # New behavior: snapshot stores `first_seen_at` per id (ISO timestamp).
    # On each merge:
    #   - new id          → first_seen_at = now, isNew=True
    #   - existing id     → carry forward first_seen_at; isNew=True if
    #                       (now - first_seen_at) ≤ NEW_DURATION_MIN
    #   - id no longer present → drop from snapshot
    #
    # Backward-compat: old snapshots in `{"ids": [...]}` shape are loaded
    # as if every id had first_seen_at = now (so they don't suddenly all
    # appear as NEW after deploy — but they also won't be NEW at all,
    # which matches user expectation that "newness" only marks fresh
    # appearances after the upgrade).
    NEW_DURATION_MIN = 30
    prev_ids_path = os.path.join(DATA_DIR, "previous_run_ids.json")
    prev_first_seen: dict[str, str] = {}
    previous_run_existed = False
    if os.path.exists(prev_ids_path):
        try:
            with open(prev_ids_path, 'r', encoding='utf-8') as f:
                snapshot = json.load(f)
            previous_run_existed = True
            stored = snapshot.get('first_seen', None)
            if isinstance(stored, dict):
                # New format: {pid: iso_timestamp}
                prev_first_seen = {str(k): str(v) for k, v in stored.items()}
            else:
                # Legacy format: {"ids": [...]} — treat as already-known
                # so they don't suddenly all appear as NEW after deploy.
                # Use current time as their first_seen so they immediately
                # graduate out of the window.
                legacy_ids = snapshot.get('ids', []) or []
                # Use a timestamp far enough in the past that they won't
                # qualify as NEW under the new rule.
                ancient = datetime(2000, 1, 1).isoformat()
                prev_first_seen = {str(pid): ancient for pid in legacy_ids}
        except Exception as e:  # noqa: BLE001 — corrupt snapshot → treat as first run
            print(f"  ⚠️ Could not read previous_run_ids.json: {e}; treating as first run")

    now_dt = datetime.now()
    now_iso = now_dt.isoformat(timespec='seconds')
    current_first_seen: dict[str, str] = {}
    new_count = 0
    for p in all_products:
        pid = str(p.get('id', ''))
        if not pid:
            p['isNew'] = False
            continue
        first_seen_iso = prev_first_seen.get(pid)
        if first_seen_iso is None:
            # Genuinely new id — appearing for the first time in our snapshot.
            first_seen_iso = now_iso
        current_first_seen[pid] = first_seen_iso
        # Compute age. Skip the NEW flag entirely on the very first run
        # (no previous_run_existed) to avoid the cold-start flood.
        if not previous_run_existed:
            p['isNew'] = False
            continue
        try:
            first_seen_dt = datetime.fromisoformat(first_seen_iso)
            age_min = (now_dt - first_seen_dt).total_seconds() / 60.0
        except Exception:  # noqa: BLE001 — bad timestamp → treat as not new
            age_min = NEW_DURATION_MIN + 1
        is_new = age_min <= NEW_DURATION_MIN
        p['isNew'] = is_new
        if is_new:
            new_count += 1

    if previous_run_existed:
        print(f"  🆕 Marked {new_count} new products (within {NEW_DURATION_MIN}-min window; tracking {len(current_first_seen)} ids)")
    else:
        print(f"  🆕 First run — initialized first_seen baseline for {len(current_first_seen)} ids; no NEW marker on first run")

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
    
    # Save to data folder (atomic — see _atomic_write_json docstring).
    proposals_path = os.path.join(DATA_DIR, "proposals.json")
    _atomic_write_json(proposals_path, output)

    # v1.27.1: persist current run's first_seen map as next merge's
    # baseline. Done AFTER proposals.json is committed so a partial-write
    # here doesn't corrupt the user-facing data file. Old `ids:` key is
    # also written for transient backward compat (older readers can
    # still parse the legacy field), but new readers prefer `first_seen`.
    try:
        _atomic_write_json(prev_ids_path, {
            'first_seen': current_first_seen,
            'updatedAt': data_time,
            'count': len(current_first_seen),
            'ids': sorted(current_first_seen.keys()),  # legacy compat
        })
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠️ Could not write previous_run_ids.json: {e}")
    
    # Copy to miniapp (also atomic — same flicker bug would surface if
    # something served data.json directly during a write).
    miniapp_path = os.path.join(BASE_DIR, "miniapp", "public", "data.json")
    if os.path.exists(os.path.dirname(miniapp_path)):
        _atomic_write_json(miniapp_path, output)
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
