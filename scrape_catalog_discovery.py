"""
Catalog discovery scraper for Phase 36.

Scrapes every catalog-root tile/source from https://vkusvill.ru/goods/,
collects each source into its own temp file, and tracks source validity
separately from stored progress.
"""
import asyncio
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import urljoin, urlparse

import aiohttp
from bs4 import BeautifulSoup

try:
    from aiohttp_socks import ProxyConnector
    HAS_AIOHTTP_SOCKS = True
except ImportError:
    ProxyConnector = None
    HAS_AIOHTTP_SOCKS = False

from proxy_manager import ProxyManager
from scrape_categories import HEADERS, MAX_CONCURRENT, fetch_page, _extract_id


if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
CATALOG_ROOT_URL = "https://vkusvill.ru/goods/"
CATALOG_SOURCES_PATH = os.path.join(DATA_DIR, "catalog_sources.json")
CATALOG_DISCOVERY_STATE_PATH = os.path.join(DATA_DIR, "catalog_discovery_state.json")
CATALOG_DISCOVERY_SOURCES_DIR = os.path.join(DATA_DIR, "catalog_discovery_sources")
SOURCE_TILE_SELECTORS = [
    ("catalog_tile", "a.VVCategCards2020__Item[href]"),
    ("catalog_slider", "a.VVCatalog20SsRecItem[href]"),
]
SOURCE_PATH_RE = re.compile(r"^/goods/([^/?#]+)/?$")
COUNT_RE = re.compile(r"(\d[\d\s]*)\s+товар")
PAGE_RE = re.compile(r"[?&]PAGEN_1=(\d+)")


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_output_dirs() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(CATALOG_DISCOVERY_SOURCES_DIR, exist_ok=True)


def read_json(path: str, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def atomic_write_json(path: str, data) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        delete=False,
        dir=os.path.dirname(path),
        suffix=".tmp",
    ) as tmp:
        json.dump(data, tmp, ensure_ascii=False, indent=2)
        tmp_path = tmp.name
    os.replace(tmp_path, path)


def source_slug_from_url(url: str) -> str | None:
    path = urlparse(url).path
    match = SOURCE_PATH_RE.match(path)
    if not match:
        return None
    return match.group(1)


def normalize_source_url(href: str) -> str | None:
    if not href:
        return None
    full_url = urljoin(CATALOG_ROOT_URL, href)
    slug = source_slug_from_url(full_url)
    if not slug:
        return None
    return f"{CATALOG_ROOT_URL}{slug}/"


def discover_catalog_sources_from_html(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "lxml")
    results: list[dict] = []
    seen_urls: set[str] = set()

    for source_type, selector in SOURCE_TILE_SELECTORS:
        for link in soup.select(selector):
            href = link.get("href", "").strip()
            url = normalize_source_url(href)
            if not url or url in seen_urls:
                continue
            slug = source_slug_from_url(url)
            if not slug:
                continue
            name = " ".join(link.get_text(" ", strip=True).split()) or slug
            seen_urls.add(url)
            results.append(
                {
                    "name": name,
                    "slug": slug,
                    "url": url,
                    "source_type": source_type,
                }
            )

    if results:
        return results

    for link in soup.select("a.VVCatalog2020Menu__Link[href]"):
        href = link.get("href", "").strip()
        url = normalize_source_url(href)
        if not url or url in seen_urls:
            continue
        slug = source_slug_from_url(url)
        if not slug:
            continue
        name = " ".join(link.get_text(" ", strip=True).split()) or slug
        seen_urls.add(url)
        results.append(
            {
                "name": name,
                "slug": slug,
                "url": url,
                "source_type": "catalog_menu_fallback",
            }
        )
    return results


def extract_source_count_from_html(html: str) -> int | None:
    soup = BeautifulSoup(html, "lxml")
    strings = [" ".join(text.split()) for text in soup.stripped_strings]
    heading = soup.find("h1")

    if heading:
        heading_text = " ".join(heading.get_text(" ", strip=True).split())
        try:
            idx = strings.index(heading_text)
        except ValueError:
            idx = -1
        if idx >= 0:
            for text in strings[idx + 1: idx + 20]:
                match = COUNT_RE.search(text)
                if match:
                    return int(match.group(1).replace(" ", ""))

    for text in strings:
        match = COUNT_RE.search(text)
        if match:
            return int(match.group(1).replace(" ", ""))
    return None


def extract_max_page_from_html(html: str) -> int:
    soup = BeautifulSoup(html, "lxml")
    max_page = 1
    for link in soup.select("a[href*='PAGEN_1=']"):
        href = link.get("href", "")
        match = PAGE_RE.search(href)
        if not match:
            continue
        try:
            max_page = max(max_page, int(match.group(1)))
        except ValueError:
            continue
    return max_page


def extract_numeric_product_id(url: str | None) -> str | None:
    if not url:
        return None
    product_id = _extract_id(url)
    if product_id and str(product_id).isdigit():
        return str(product_id)
    return None


def parse_source_products_from_html(html: str, source_url: str) -> tuple[list[dict], int]:
    soup = BeautifulSoup(html, "lxml")
    cards = soup.select(".ProductCard")
    products: list[dict] = []
    invalid_identity_count = 0

    for card in cards:
        title_link = card.select_one(".ProductCard__link, a[href*='.html']")
        image_link = card.select_one(".ProductCard__imageLink")
        href = ""
        if title_link and title_link.get("href"):
            href = title_link.get("href", "")
        elif image_link and image_link.get("href"):
            href = image_link.get("href", "")

        full_url = urljoin(source_url, href) if href else ""
        product_id = extract_numeric_product_id(full_url)
        if not product_id:
            invalid_identity_count += 1
            continue

        image = card.select_one("img")
        image_url = ""
        if image:
            image_url = (
                image.get("src")
                or image.get("data-src")
                or image.get("data-original")
                or ""
            )

        name = ""
        if title_link:
            name = " ".join(title_link.get_text(" ", strip=True).split())
        if not name and image:
            name = " ".join((image.get("alt", "") or "").split())

        products.append(
            {
                "product_id": product_id,
                "name": name,
                "url": full_url,
                "image_url": image_url,
            }
        )

    return products, invalid_identity_count


def merge_source_products(existing_products: dict, new_products: list[dict], seen_at: str) -> dict:
    merged = dict(existing_products or {})
    for product in new_products:
        product_id = product["product_id"]
        existing = merged.get(product_id, {})
        merged[product_id] = {
            "product_id": product_id,
            "name": product.get("name") or existing.get("name", ""),
            "url": product.get("url") or existing.get("url", ""),
            "image_url": product.get("image_url") or existing.get("image_url", ""),
            "first_seen_at": existing.get("first_seen_at", seen_at),
            "last_seen_at": seen_at,
        }
    return merged


def build_source_state_entry(
    *,
    source: dict,
    expected_count: int | None,
    current_run_count: int,
    stored_count: int,
    complete: bool,
    last_error: str | None,
    last_failed_page: int | None,
    last_run_at: str,
    previous_state: dict | None = None,
) -> dict:
    previous_state = previous_state or {}
    return {
        "source_name": source["name"],
        "source_slug": source["slug"],
        "source_url": source["url"],
        "source_type": source.get("source_type", "catalog_tile"),
        "expected_count": expected_count,
        "collected_count": current_run_count,
        "stored_count": stored_count,
        "complete": bool(complete),
        "last_run_at": last_run_at,
        "last_verified_at": last_run_at if complete else previous_state.get("last_verified_at"),
        "last_error": None if complete else (last_error or "count mismatch"),
        "last_failed_page": last_failed_page,
        "identity_key": "product_id",
    }


def load_source_file(slug: str) -> dict:
    path = os.path.join(CATALOG_DISCOVERY_SOURCES_DIR, f"{slug}.json")
    return read_json(path, {})


def save_source_file(source: dict, expected_count: int | None, products: dict, updated_at: str) -> None:
    path = os.path.join(CATALOG_DISCOVERY_SOURCES_DIR, f"{source['slug']}.json")
    atomic_write_json(
        path,
        {
            "updated_at": updated_at,
            "source_name": source["name"],
            "source_slug": source["slug"],
            "source_url": source["url"],
            "source_type": source.get("source_type", "catalog_tile"),
            "expected_count": expected_count,
            "products": products,
        },
    )


async def discover_catalog_sources(session: aiohttp.ClientSession) -> list[dict]:
    html = await fetch_page(session, CATALOG_ROOT_URL)
    if html is None:
        raise RuntimeError("Failed to load catalog root page")

    sources = discover_catalog_sources_from_html(html)
    if not sources:
        raise RuntimeError("No catalog sources found on the catalog root page")

    manifest = {
        "updated_at": utc_iso(),
        "source_count": len(sources),
        "sources": sources,
    }
    atomic_write_json(CATALOG_SOURCES_PATH, manifest)
    print(f"[catalog-discovery] catalog root manifest saved with {len(sources)} sources")
    return sources


async def scrape_source(session: aiohttp.ClientSession, sem: asyncio.Semaphore, source: dict, state: dict) -> dict:
    now = utc_iso()
    previous_state = state.get(source["slug"], {})
    source_file = load_source_file(source["slug"])
    existing_products = source_file.get("products", {})

    current_run_products: list[dict] = []
    invalid_identity_count = 0
    last_failed_page = None
    last_error = None

    async with sem:
        html = await fetch_page(session, source["url"])
    if html is None:
        last_error = "failed to load source page"
        merged_products = existing_products
        entry = build_source_state_entry(
            source=source,
            expected_count=None,
            current_run_count=0,
            stored_count=len(merged_products),
            complete=False,
            last_error=last_error,
            last_failed_page=1,
            last_run_at=now,
            previous_state=previous_state,
        )
        save_source_file(source, None, merged_products, now)
        print(f"[catalog-discovery] {source['slug']}: FAIL - {last_error}")
        return entry

    expected_count = extract_source_count_from_html(html)
    if expected_count is None:
        last_error = "expected source count not found"

    max_page = extract_max_page_from_html(html)
    page_products, page_invalid = parse_source_products_from_html(html, source["url"])
    current_run_products.extend(page_products)
    invalid_identity_count += page_invalid

    for page_num in range(2, max_page + 1):
        page_url = f"{source['url']}?PAGEN_1={page_num}"
        async with sem:
            page_html = await fetch_page(session, page_url)
        if page_html is None:
            last_failed_page = page_num
            last_error = f"failed to load page {page_num}"
            break

        page_products, page_invalid = parse_source_products_from_html(page_html, source["url"])
        invalid_identity_count += page_invalid

        if not page_products:
            last_failed_page = page_num
            last_error = f"page {page_num} returned 0 products"
            break

        current_run_products.extend(page_products)

    current_run_by_id = {product["product_id"]: product for product in current_run_products}
    merged_products = merge_source_products(existing_products, list(current_run_by_id.values()), now)

    if invalid_identity_count and not last_error:
        last_error = f"{invalid_identity_count} products missing numeric product_id"

    current_run_count = len(current_run_by_id)
    complete = (
        last_error is None
        and expected_count is not None
        and current_run_count == expected_count
    )

    if not complete and last_error is None and expected_count is not None:
        last_error = f"count mismatch: expected {expected_count}, collected {current_run_count}"

    save_source_file(source, expected_count, merged_products, now)
    entry = build_source_state_entry(
        source=source,
        expected_count=expected_count,
        current_run_count=current_run_count,
        stored_count=len(merged_products),
        complete=complete,
        last_error=last_error,
        last_failed_page=last_failed_page,
        last_run_at=now,
        previous_state=previous_state,
    )

    status = "OK" if complete else "INCOMPLETE"
    print(
        f"[catalog-discovery] {source['slug']}: {status} "
        f"(expected={expected_count}, current={current_run_count}, stored={len(merged_products)})"
    )
    if last_error:
        print(f"[catalog-discovery] {source['slug']}: reason={last_error}")
    return entry


async def run_catalog_discovery() -> int:
    ensure_output_dirs()
    state_doc = read_json(CATALOG_DISCOVERY_STATE_PATH, {"updated_at": None, "sources": {}})
    state = state_doc.get("sources", {})

    sem = asyncio.Semaphore(MAX_CONCURRENT)
    pm = ProxyManager()
    proxy_addr = pm.get_working_proxy()
    connector = None
    if proxy_addr and HAS_AIOHTTP_SOCKS:
        connector = ProxyConnector.from_url(f"socks5://{proxy_addr}")
        print(f"[catalog-discovery] using SOCKS5 proxy: {proxy_addr}")
    elif proxy_addr:
        print("[catalog-discovery] proxy available but aiohttp_socks missing; using direct connection")
    else:
        print("[catalog-discovery] no proxy available; using direct connection")

    async with aiohttp.ClientSession(headers=HEADERS, connector=connector) as session:
        sources = await discover_catalog_sources(session)
        updated_state: dict[str, dict] = {}
        for source in sources:
            updated_state[source["slug"]] = await scrape_source(session, sem, source, state)

    state_doc = {
        "updated_at": utc_iso(),
        "sources": updated_state,
    }
    atomic_write_json(CATALOG_DISCOVERY_STATE_PATH, state_doc)

    complete_sources = sum(1 for entry in updated_state.values() if entry.get("complete"))
    incomplete_sources = len(updated_state) - complete_sources
    print(f"[catalog-discovery] finished: {complete_sources} complete, {incomplete_sources} incomplete")
    return 0 if incomplete_sources == 0 else 1


def main() -> int:
    try:
        return asyncio.run(run_catalog_discovery())
    except Exception as exc:
        print(f"[catalog-discovery] fatal error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
