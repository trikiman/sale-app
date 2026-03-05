"""
Category scraper - builds product ID to category mapping from VkusVill catalog
Run daily to keep the category database updated.
Uses aiohttp + asyncio for fast parallel fetching of all categories and pages.
"""
import re
import json
import os
import sys
import asyncio
import aiohttp
from bs4 import BeautifulSoup
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "category_db.json")

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xhtml+xml;q=0.9,*/*;q=0.8',
    'Accept-Language': 'ru-RU,ru;q=0.9,en;q=0.8',
    'Accept-Encoding': 'gzip, deflate, br',
    'Connection': 'keep-alive',
}

# VkusVill category URLs - verified against live site (all use /goods/ path)
CATEGORIES = [
    {"name": "Готовая еда", "url": "https://vkusvill.ru/goods/gotovaya-eda/"},
    {"name": "Орехи, чипсы и снеки", "url": "https://vkusvill.ru/goods/orekhi-chipsy-i-sneki/"},
    {"name": "Овощи, фрукты, ягоды, зелень", "url": "https://vkusvill.ru/goods/ovoshchi-frukty-yagody-zelen/"},
    {"name": "Сладости и десерты", "url": "https://vkusvill.ru/goods/sladosti-i-deserty/"},
    {"name": "Молочные продукты, яйцо", "url": "https://vkusvill.ru/goods/molochnye-produkty-yaytso/"},
    {"name": "Хлеб и выпечка", "url": "https://vkusvill.ru/goods/khleb-i-vypechka/"},
    {"name": "Мясо, птица", "url": "https://vkusvill.ru/goods/myaso-ptitsa/"},
    {"name": "Сыры", "url": "https://vkusvill.ru/goods/syry/"},
    {"name": "Рыба, икра и морепродукты", "url": "https://vkusvill.ru/goods/ryba-ikra-i-moreprodukty/"},
    {"name": "Колбаса, сосиски, деликатесы", "url": "https://vkusvill.ru/goods/kolbasa-sosiski-delikatesy/"},
    {"name": "Мороженое", "url": "https://vkusvill.ru/goods/morozhenoe/"},
    {"name": "Замороженные продукты", "url": "https://vkusvill.ru/goods/zamorozhennye-produkty/"},
    {"name": "Напитки", "url": "https://vkusvill.ru/goods/napitki/"},
    {"name": "Крупы, макароны, мука", "url": "https://vkusvill.ru/goods/krupy-makarony-muka/"},
    {"name": "Алкоголь", "url": "https://vkusvill.ru/goods/alkogol/"},
    {"name": "Консервация", "url": "https://vkusvill.ru/goods/konservatsiya/"},
    {"name": "Чай и кофе", "url": "https://vkusvill.ru/goods/chay-i-kofe/"},
    {"name": "Масла, соусы, специи, сахар и соль", "url": "https://vkusvill.ru/goods/masla-sousy-spetsii-sakhar-i-sol/"},
    {"name": "Косметика, средства гигиены", "url": "https://vkusvill.ru/goods/kosmetika-sredstva-gigieny/"},
    {"name": "Товары для дома и кухни", "url": "https://vkusvill.ru/goods/tovary-dlya-doma-i-kukhni/"},
    {"name": "Сад и огород", "url": "https://vkusvill.ru/goods/sad-i-ogorod/"},
    {"name": "Товары для животных", "url": "https://vkusvill.ru/goods/tovary-dlya-zhivotnykh/"},
    {"name": "Товары для детей", "url": "https://vkusvill.ru/goods/tovary-dlya-detey/"},
    {"name": "Здоровье", "url": "https://vkusvill.ru/goods/zdorove/"},
    {"name": "Особое питание", "url": "https://vkusvill.ru/goods/osoboe-pitanie/"},
    {"name": "Индилавка: вкусы мира", "url": "https://vkusvill.ru/goods/indilavka-vkusy-mira/"},
    {"name": "Выпекаем сами", "url": "https://vkusvill.ru/goods/vypekaem-sami/"},
    {"name": "Добрая полка", "url": "https://vkusvill.ru/goods/dobraya-polka/"},
    # Кафе (in-store cafe items, not in main categories)
    {"name": "Кафе", "url": "https://vkusvill.ru/goods/kafe/"},
    # Супермаркет sub-categories (branded/third-party goods not in main VV catalog)
    {"name": "Мясная гастрономия", "url": "https://vkusvill.ru/goods/supermarket/myasnaya-gastronomiya/"},
    {"name": "Мясо, птица, п/ф", "url": "https://vkusvill.ru/goods/supermarket/myaso-ptitsa-p-f/"},
    {"name": "Молочные продукты, яйцо", "url": "https://vkusvill.ru/goods/supermarket/molochnye-produkty-yaytso/"},
    {"name": "Овощи, фрукты, зелень", "url": "https://vkusvill.ru/goods/supermarket/ovoshchi-frukty-zelen/"},
    {"name": "Рыба, икра", "url": "https://vkusvill.ru/goods/supermarket/ryba-ikra/"},
    {"name": "Сыры", "url": "https://vkusvill.ru/goods/supermarket/syry/"},
    {"name": "Хлеб, хлебные изделия", "url": "https://vkusvill.ru/goods/supermarket/khleb-khlebnye-izdeliya/"},
    {"name": "Сладости", "url": "https://vkusvill.ru/goods/supermarket/sladosti/"},
    {"name": "Замороженные продукты", "url": "https://vkusvill.ru/goods/supermarket/zamorozhennye-produkty/"},
    {"name": "Мороженое", "url": "https://vkusvill.ru/goods/supermarket/morozhenoe/"},
    {"name": "Вода, соки, напитки", "url": "https://vkusvill.ru/goods/supermarket/voda-soki-napitki/"},
    {"name": "Чай, кофе, какао", "url": "https://vkusvill.ru/goods/supermarket/chay-kofe-kakao/"},
    {"name": "Бакалея", "url": "https://vkusvill.ru/goods/supermarket/bakaleya/"},
    {"name": "Консервация и соленья", "url": "https://vkusvill.ru/goods/supermarket/konservatsiya-i-solenya/"},
    {"name": "Чипсы, орехи и снэки", "url": "https://vkusvill.ru/goods/supermarket/chipsy-orekhi-i-sneki/"},
    {"name": "Бытовая химия и хозтовары", "url": "https://vkusvill.ru/goods/supermarket/bytovaya-khimiya-i-khoztovary/"},
    {"name": "Красота и гигиена", "url": "https://vkusvill.ru/goods/supermarket/krasota-i-gigiena/"},
    {"name": "Товары для животных", "url": "https://vkusvill.ru/goods/supermarket/tovary-dlya-zhivotnykh/"},
    {"name": "Детское питание и гигиена", "url": "https://vkusvill.ru/goods/supermarket/detskoe-pitanie-i-gigiena/"},
    {"name": "Спортивное питание", "url": "https://vkusvill.ru/goods/supermarket/sportivnoe-pitanie/"},
    {"name": "Растительное, веганское, постное", "url": "https://vkusvill.ru/goods/supermarket/rastitelnoe-veganskoe-postnoe/"},
    {"name": "Импорт из Азии", "url": "https://vkusvill.ru/goods/supermarket/import-iz-azii/"},
    {"name": "1000 мелочей", "url": "https://vkusvill.ru/goods/supermarket/1000-melochey/"},
]

_ID_PATTERNS = [
    re.compile(r'/goods/(\d+)'),
    re.compile(r'-(\d+)\.html'),
    re.compile(r'(\d+)\.html'),
]


def _extract_id(href: str):
    for pat in _ID_PATTERNS:
        m = pat.search(href)
        if m:
            return m.group(1)
    return None


def _parse_products(html: str):
    """Parse product cards from HTML, return list of {id, name}."""
    soup = BeautifulSoup(html, 'lxml')
    cards = soup.select('.ProductCard')
    if not cards:
        return []
    products = []
    for card in cards:
        link = card.select_one('.ProductCard__link, a[href*=".html"]')
        name_el = card.select_one('.ProductCard__link, .ProductCard__title')
        if not link or not name_el:
            continue
        href = link.get('href', '')
        pid = _extract_id(href)
        if not pid:
            continue
        products.append({'id': pid, 'name': name_el.get_text(strip=True)})
    return products


def load_existing_db():
    """Load existing database if it exists"""
    if os.path.exists(DB_PATH):
        try:
            with open(DB_PATH, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_updated": None, "products": {}}


def save_db(db):
    """Save database to file"""
    os.makedirs(DATA_DIR, exist_ok=True)
    db["last_updated"] = datetime.now().isoformat()
    with open(DB_PATH, 'w', encoding='utf-8') as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


# Global semaphore limits concurrent requests to be polite
MAX_CONCURRENT = 10


async def fetch_page(session: aiohttp.ClientSession, url: str) -> str | None:
    """Fetch a single page, return HTML or None on error."""
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=20)) as resp:
            if resp.status != 200:
                return None
            return await resp.text()
    except Exception:
        return None


async def scrape_category(session: aiohttp.ClientSession, sem: asyncio.Semaphore,
                          cat: dict, max_pages: int = 200) -> tuple[str, list]:
    """Scrape all pages of a single category using async HTTP."""
    all_products = []
    category_url = cat["url"]
    category_name = cat["name"]

    for page_num in range(1, max_pages + 1):
        url = category_url if page_num == 1 else f"{category_url}?PAGEN_1={page_num}"

        async with sem:
            html = await fetch_page(session, url)

        if html is None:
            if page_num == 1:
                print(f"   [{category_name}] page 1: failed to load, skipping category")
            break

        products = _parse_products(html)
        if not products:
            break

        all_products.extend(products)
        print(f"   [{category_name}] page {page_num}: {len(products)} products (total: {len(all_products)})")

        # Small async delay to be polite (much less blocking than sync sleep)
        await asyncio.sleep(0.15)

    print(f"   -> {category_name}: {len(all_products)} total products")
    return category_name, all_products


async def scrape_all_categories_async():
    """Main async function to scrape all categories concurrently."""
    print("Starting category scraper (async, all categories in parallel)...")

    db = load_existing_db()
    total_new = 0
    total_updated = 0

    sem = asyncio.Semaphore(MAX_CONCURRENT)

    async with aiohttp.ClientSession(headers=HEADERS) as session:
        tasks = [scrape_category(session, sem, cat) for cat in CATEGORIES]
        results_list = await asyncio.gather(*tasks, return_exceptions=True)

    results: dict[str, list] = {}
    for i, res in enumerate(results_list):
        if isinstance(res, Exception):
            print(f"   Error scraping {CATEGORIES[i]['name']}: {res}")
        else:
            cat_name, products = res
            results[cat_name] = products

    # Merge results into DB
    for cat in CATEGORIES:
        cat_name = cat["name"]
        products = results.get(cat_name, [])
        for p in products:
            pid = p['id']
            if pid in db['products']:
                if db['products'][pid]['category'] != cat_name:
                    db['products'][pid]['category'] = cat_name
                    db['products'][pid]['name'] = p['name']
                    total_updated += 1
            else:
                db['products'][pid] = {'name': p['name'], 'category': cat_name}
                total_new += 1

    save_db(db)

    print(f"\nDone! {total_new} new products, {total_updated} updated")
    print(f"Database saved to {DB_PATH} ({len(db['products'])} total products)")

    return db


def scrape_all_categories():
    """Sync wrapper for the async scraper."""
    return asyncio.run(scrape_all_categories_async())


if __name__ == "__main__":
    scrape_all_categories()
