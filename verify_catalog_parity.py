"""
Phase 38 parity verification against live VkusVill search and local History search.
"""
import asyncio
import json
import os
from urllib.parse import quote

import aiohttp
from fastapi.testclient import TestClient

import backend.main as main
from scrape_categories import HEADERS
from scrape_catalog_discovery import extract_max_page_from_html, parse_source_products_from_html


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
QUERY_FILE = os.path.join(BASE_DIR, "backend", "catalog_parity_queries.json")
REPORT_PATH = os.path.join(DATA_DIR, "catalog_parity_report.json")
SEARCH_URL = "https://vkusvill.ru/search/?type=products&q={query}"


def read_queries() -> list[dict]:
    with open(QUERY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)["queries"]


async def fetch_live_query_result(session: aiohttp.ClientSession, query: str) -> dict:
    first_url = SEARCH_URL.format(query=quote(query))
    async with session.get(first_url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
        html = await resp.text()

    page_products, _ = parse_source_products_from_html(html, first_url)
    products = list(page_products)
    max_page = extract_max_page_from_html(html)

    for page_num in range(2, max_page + 1):
        url = f"{first_url}&PAGEN_1={page_num}"
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as resp:
            page_html = await resp.text()
        page_products, _ = parse_source_products_from_html(page_html, first_url)
        if not page_products:
            break
        products.extend(page_products)

    raw_count = len(products)
    unique_ids = sorted({p["product_id"] for p in products})
    return {
        "raw_count": raw_count,
        "unique_count": len(unique_ids),
        "product_ids": unique_ids,
    }


def fetch_local_query_result(client: TestClient, query: str) -> dict:
    page = 1
    per_page = 200
    products = []
    while True:
        response = client.get("/api/history/products", params={"search": query, "page": page, "per_page": per_page})
        response.raise_for_status()
        body = response.json()
        products.extend(body["products"])
        if page >= body.get("pages", 0):
            break
        page += 1
    unique_ids = sorted({p["id"] for p in products})
    return {
        "total": len(products),
        "unique_count": len(unique_ids),
        "product_ids": unique_ids,
    }


async def build_parity_report() -> dict:
    queries = read_queries()
    client = TestClient(main.app)
    rows = []

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        for item in queries:
            live = await fetch_live_query_result(session, item["query"])
            local = fetch_local_query_result(client, item["query"])
            expected_id = item.get("expected_product_id")
            row = {
                "label": item["label"],
                "query": item["query"],
                "type": item["type"],
                "live_unique_count": live["unique_count"],
                "local_unique_count": local["unique_count"],
                "live_product_ids": live["product_ids"],
                "local_product_ids": local["product_ids"],
                "expected_product_id": expected_id,
                "expected_found_locally": expected_id in local["product_ids"] if expected_id else None,
            }
            rows.append(row)

    passed = True
    for row in rows:
        if row["type"] == "exact" and not row["expected_found_locally"]:
            passed = False
        if row["type"] == "broad" and row["local_unique_count"] == 0:
            passed = False

    report = {
        "queries": rows,
        "status": "passed" if passed else "gaps_found",
    }
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    return report


def main_func() -> int:
    report = asyncio.run(build_parity_report())
    print(f"[catalog-parity] status={report['status']} queries={len(report['queries'])}")
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main_func())
