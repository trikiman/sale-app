"""
Merge Phase 36 catalog discovery source files into a deduped discovery artifact
and backfill category_db.json additively.
"""
import json
import os
import tempfile
from datetime import datetime, timezone

import config


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = config.DATA_DIR
DISCOVERY_STATE_PATH = os.path.join(DATA_DIR, "catalog_discovery_state.json")
DISCOVERY_SOURCES_DIR = os.path.join(DATA_DIR, "catalog_discovery_sources")
MERGED_DISCOVERY_PATH = os.path.join(DATA_DIR, "catalog_discovery_merged.json")
CATEGORY_DB_PATH = os.path.join(DATA_DIR, "category_db.json")
NON_BLOCKING_SOURCE_SLUGS = {"set-vashi-skidki"}


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_json(path: str, default):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def atomic_write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", delete=False, dir=os.path.dirname(path), suffix=".tmp"
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    os.replace(tmp_path, path)


def eligible_source_slugs(state_doc: dict) -> list[str]:
    slugs = []
    for slug, entry in (state_doc.get("sources") or {}).items():
        if entry.get("complete"):
            slugs.append(slug)
        elif slug in NON_BLOCKING_SOURCE_SLUGS:
            slugs.append(slug)
    return sorted(slugs)


def merge_source_product_maps(state_doc: dict, source_dir: str) -> dict:
    merged: dict[str, dict] = {}
    for slug in eligible_source_slugs(state_doc):
        path = os.path.join(source_dir, f"{slug}.json")
        if not os.path.exists(path):
            continue
        source_doc = read_json(path, {})
        source_name = source_doc.get("source_name", slug)
        for product_id, product in (source_doc.get("products") or {}).items():
            existing = merged.get(product_id, {})
            source_slugs = sorted(set(existing.get("source_slugs", [])) | {slug})
            source_names = sorted(set(existing.get("source_names", [])) | {source_name})
            merged[product_id] = {
                "product_id": product_id,
                "name": existing.get("name") or product.get("name", ""),
                "url": existing.get("url") or product.get("url", ""),
                "image_url": existing.get("image_url") or product.get("image_url", ""),
                "source_slugs": source_slugs,
                "source_names": source_names,
            }
    return merged


def merge_into_category_products(existing_products: dict, merged_products: dict) -> tuple[dict, int, int]:
    updated_products = dict(existing_products or {})
    added = 0
    updated = 0

    for product_id, merged in merged_products.items():
        existing = dict(updated_products.get(product_id, {}))
        if existing:
            before = dict(existing)
            if not existing.get("name") and merged.get("name"):
                existing["name"] = merged["name"]
            if not existing.get("image_url") and merged.get("image_url"):
                existing["image_url"] = merged["image_url"]
            if not existing.get("url") and merged.get("url"):
                existing["url"] = merged["url"]
            existing["discovery_sources"] = sorted(
                set(existing.get("discovery_sources", [])) | set(merged.get("source_slugs", []))
            )
            existing["discovery_source_names"] = sorted(
                set(existing.get("discovery_source_names", [])) | set(merged.get("source_names", []))
            )
            updated_products[product_id] = existing
            if existing != before:
                updated += 1
            continue

        updated_products[product_id] = {
            "name": merged.get("name", ""),
            "category": "",
            "group": "",
            "subgroups": [],
            "image_url": merged.get("image_url", ""),
            "url": merged.get("url", ""),
            "discovery_sources": merged.get("source_slugs", []),
            "discovery_source_names": merged.get("source_names", []),
        }
        added += 1

    return updated_products, added, updated


def run_merge_catalog_discovery() -> dict:
    state_doc = read_json(DISCOVERY_STATE_PATH, {"updated_at": None, "sources": {}})
    merged_products = merge_source_product_maps(state_doc, DISCOVERY_SOURCES_DIR)

    merged_doc = {
        "updated_at": utc_iso(),
        "product_count": len(merged_products),
        "products": merged_products,
    }
    atomic_write_json(MERGED_DISCOVERY_PATH, merged_doc)

    category_db = read_json(CATEGORY_DB_PATH, {"last_updated": None, "products": {}})
    existing_products = category_db.get("products", {})
    updated_products, added, updated = merge_into_category_products(existing_products, merged_products)
    category_db["last_updated"] = utc_iso()
    category_db["products"] = updated_products
    atomic_write_json(CATEGORY_DB_PATH, category_db)

    return {
        "merged_count": len(merged_products),
        "category_db_added": added,
        "category_db_updated": updated,
        "merged_path": MERGED_DISCOVERY_PATH,
        "category_db_path": CATEGORY_DB_PATH,
    }


def main() -> int:
    result = run_merge_catalog_discovery()
    print(
        "[catalog-merge] merged={merged_count} added={category_db_added} updated={category_db_updated}".format(
            **result
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
