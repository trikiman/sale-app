"""
Green scraper — Script 2: Read green items from cart and write JSON.
No modal interaction, no adding items. Just reads basket_recalc API + green section DOM.

Flow:
1. Launch Chrome, load cookies, navigate to /cart/
2. Close delivery modal
3. Read green section for inline items (data-max, prices)
4. Call basket_recalc API via CDP for stock data
5. Enrich, deduplicate, validate
6. Save green_products.json
7. Close browser
"""
import asyncio
import json
import os
import sys
import time

from green_common import (
    BASE_DIR, DATA_DIR, GREEN_URL, SCREENSHOT_DIR,
    step_screenshot, launch_browser, load_cookies, js, navigate,
    close_delivery_modal, check_login, cleanup_browser,
    inspect_green_section, normalize_unit, format_quantity, stock_text_from_map,
    fetch_basket_snapshot, build_basket_stock_map, fetch_basket_via_cdp,
    extract_green_from_basket_dict, fetch_green_from_basket_async,
    parse_nodriver_dict,
)
from utils import (
    normalize_category, parse_stock, clean_price,
    deduplicate_products, synthesize_discount,
    save_products_safe, check_vkusvill_available, normalize_stock_unit,
)

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

TAG = "GREEN-DATA"


# ── Validation helpers ───────────────────────────────────────────────────────

def _load_existing_green_product_count() -> int:
    path = os.path.join(DATA_DIR, "green_products.json")
    if not os.path.exists(path):
        return 0
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return 0
    if isinstance(data, dict):
        products = data.get('products', [])
    elif isinstance(data, list):
        products = data
    else:
        products = []
    return len(products) if isinstance(products, list) else 0


def _is_suspicious_empty(section_found, live_count, product_count, existing_count=0):
    return product_count == 0 and ((not section_found) or live_count > 0 or existing_count > 0)


def _is_suspicious_single(live_count, product_count, existing_count=0):
    try:
        live_count = int(live_count or 0)
    except (TypeError, ValueError):
        live_count = 0
    try:
        product_count = int(product_count or 0)
    except (TypeError, ValueError):
        product_count = 0
    try:
        existing_count = int(existing_count or 0)
    except (TypeError, ValueError):
        existing_count = 0
    return product_count == 1 and live_count <= 1 and existing_count >= 5


# ── Main async function ─────────────────────────────────────────────────────

async def scrape_green_data_async():
    """Read all green items from cart via basket_recalc + DOM. Write green_products.json."""
    print(f"🔄 [{TAG}] Starting...")

    if not check_vkusvill_available():
        print(f"❌ [{TAG}] VkusVill not available")
        return [], False

    browser = None
    proc = None
    tmp_profile = None
    products = []
    live_count = 0
    scrape_success = False

    try:
        # ── STEP 1: Launch browser, load cookies, go to /cart/ ──
        browser, proc, tmp_profile = await launch_browser(tag=TAG)
        page = await browser.get('about:blank')
        await asyncio.sleep(1)

        cookies_ok = await load_cookies(page, tag=TAG)
        if not cookies_ok:
            print(f"⚠️ [{TAG}] No cookies loaded.")

        await navigate(page, GREEN_URL, wait=15)

        if not await check_login(page, tag=TAG):
            return [], False

        # ── STEP 2: Close delivery modal ──
        print(f"  [{TAG}] Closing delivery modal...")
        for _attempt in range(3):
            dm_result = await close_delivery_modal(page, tag=TAG)
            if dm_result == 'no_delivery_modal':
                break
            await asyncio.sleep(1)

        # ── STEP 2.5: Load modal products from scrape_green_add.py ──
        # scrape_green_add.py scrapes product data from the modal DOM before adding to cart.
        # This is the primary product source — ensures 100% capture even if cart drops some clicks.
        modal_products = []
        modal_path = os.path.join(DATA_DIR, 'green_modal_products.json')
        if os.path.exists(modal_path):
            try:
                with open(modal_path, 'r', encoding='utf-8') as f:
                    modal_data = json.load(f)
                modal_products = modal_data.get('products', [])
                modal_ts = modal_data.get('timestamp', 0)
                age_min = (time.time() - modal_ts) / 60 if modal_ts else 999
                print(f"  [{TAG}] Loaded {len(modal_products)} modal products (age: {age_min:.1f} min)")
                MAX_MODAL_AGE_MIN = 15
                if age_min > MAX_MODAL_AGE_MIN:
                    print(f"  [{TAG}] ❌ Modal products too stale ({age_min:.0f}min old, max={MAX_MODAL_AGE_MIN}min) — ignoring")
                    modal_products = []
            except Exception as e:
                print(f"  [{TAG}] ⚠️ Could not load modal products: {e}")
        else:
            print(f"  [{TAG}] No modal products file found (first run?)")

        # ── STEP 3: Read green section from DOM ──
        print(f"  [{TAG}] Step 3: Inspecting green section...")
        await js(page, """
            (() => {
                const gs = document.getElementById('js-Delivery__Order-green-state-not-empty');
                if (gs) {
                    gs.scrollIntoView({behavior: 'instant', block: 'center'});
                } else {
                    window.scrollTo(0, document.body.scrollHeight);
                }
            })()
        """)
        await asyncio.sleep(4)

        _, _, live_count = await inspect_green_section(page)
        print(f"  [{TAG}] live_count={live_count}")

        # Paginate Swiper to force lazy-loaded slides
        paginated_total = await js(page, r"""
            (async () => {
                const section = document.getElementById('js-Delivery__Order-green-state-not-empty');
                if (!section) return 0;
                const swiperEl = section.querySelector('.swiper-container, .swiper');
                if (!swiperEl || !swiperEl.swiper) return -1;
                const s = swiperEl.swiper;
                const total = s.slides ? s.slides.length : 0;
                if (total <= 0) return 0;
                for (let i = 0; i < total; i += 3) {
                    s.slideTo(Math.min(i, total - 1), 0);
                    await new Promise(r => setTimeout(r, 300));
                }
                s.slideTo(0, 0);
                return total;
            })()
        """) or 0
        if paginated_total and paginated_total > 0:
            print(f"  [{TAG}] Swiper paginated: {paginated_total} slides")
            await asyncio.sleep(2)

        # Read green section items (inline)
        raw_products = await js(page, r"""
            (() => {
                const products = [];
                const greenSection = document.getElementById('js-Delivery__Order-green-state-not-empty');
                if (!greenSection) return products;
                const cards = greenSection.querySelectorAll('.ProductCard, .HProductCard');
                cards.forEach(card => {
                    const titleEl = card.querySelector('.ProductCard__link');
                    if (!titleEl) return;
                    const name = titleEl.innerText.trim();
                    if (!name) return;

                    let currentPrice = '';
                    const priceSelectors = [
                        '.HProductCard__Price', '.ProductCard__price', '.Price__value',
                        '[class*="price"]', '[class*="Price"]'
                    ];
                    for (const sel of priceSelectors) {
                        const el = card.querySelector(sel);
                        if (el) {
                            currentPrice = (el.innerText || '').trim();
                            if (currentPrice) break;
                        }
                    }

                    const oldPriceEl = card.querySelector(
                        '.js-datalayer-catalog-list-price-old, [class*="OldPrice"], [class*="oldPrice"], [class*="old-price"], del, s'
                    );
                    const oldPrice = oldPriceEl ? (oldPriceEl.innerText || '').trim() : '';

                    const imgEl = card.querySelector('img');
                    const image = imgEl ? (imgEl.src || '') : '';

                    const linkEl = card.querySelector('a[href*="/goods/"]') || card.querySelector('a');
                    const url = linkEl ? linkEl.href : '';

                    let productId = '';
                    const dataIdEl = card.querySelector('[data-id]');
                    if (dataIdEl) {
                        productId = dataIdEl.getAttribute('data-id') || '';
                    }
                    if (!productId && url) {
                        const idMatch = url.match(/-(\d+)\.html/);
                        if (idMatch) productId = idMatch[1];
                    }

                    let dataMax = '';
                    const addBtn = card.querySelector('.js-delivery__basket--add, [data-max], button[class*="Cart"]');
                    if (addBtn && addBtn.getAttribute('data-max')) {
                        dataMax = addBtn.getAttribute('data-max');
                    }
                    if (!dataMax) {
                        const qtyCtrl = card.querySelector('[data-max]');
                        if (qtyCtrl) dataMax = qtyCtrl.getAttribute('data-max') || '';
                    }

                    let stockText = '';
                    if (dataMax && parseFloat(dataMax) > 0) {
                        const priceText = card.innerText || '';
                        const unit = /кг/.test(priceText) ? 'кг' : 'шт';
                        stockText = 'В наличии ' + dataMax + ' ' + unit;
                    } else {
                        const cardText = card.innerText || '';
                        const stockPatterns = [
                            /(?:В наличии|в наличии)[:\s]*([\d.,]+)\s*(шт|кг)/i,
                            /(?:Осталось|осталось)\s*([\d.,]+)\s*(шт|кг)/i,
                            /([\d.,]+)\s*(шт|кг)\s*(?:в наличии|осталось)/i
                        ];
                        for (const pat of stockPatterns) {
                            const m = cardText.match(pat);
                            if (m) {
                                stockText = 'В наличии ' + m[1] + ' ' + m[2];
                                break;
                            }
                        }
                        if (!stockText && /(?:В наличии|Мало|мало)/i.test(cardText)) {
                            stockText = 'В наличии';
                        }
                    }

                    products.push({ id: productId, name, currentPrice, oldPrice, stockText, dataMax, image, url });
                });
                return products;
            })()
        """) or []
        if not isinstance(raw_products, list):
            raw_products = []
        print(f"  [{TAG}] Green section: found {len(raw_products)} green items")
        for rp in raw_products:
            st = rp.get('stockText', '')
            dm = rp.get('dataMax', '')
            print(f"    → id={rp.get('id','?'):>6} {rp.get('name','')[:30]:30s} dataMax='{dm}' stockText='{st}'")

        # ── STEP 3.5: Merge modal products into raw_products ──
        # Modal products (from scrape_green_add.py) are the primary source — they contain
        # 100% of items from the popup. Inline section items supplement with data-max stock.
        if modal_products:
            inline_by_id = {str(p.get('id', '')): p for p in raw_products if p.get('id')}
            merged = []
            merged_ids = set()
            # Start with modal products (complete set)
            for mp in modal_products:
                pid = str(mp.get('id', ''))
                if not pid:
                    continue
                # Enrich with inline data-max if available
                if pid in inline_by_id:
                    ip = inline_by_id[pid]
                    if ip.get('dataMax') and not mp.get('dataMax'):
                        mp['dataMax'] = ip['dataMax']
                    if ip.get('stockText') and not mp.get('stockText'):
                        mp['stockText'] = ip['stockText']
                merged.append(mp)
                merged_ids.add(pid)
            # Add any inline items NOT in modal (rare edge case)
            for rp in raw_products:
                pid = str(rp.get('id', ''))
                if pid and pid not in merged_ids:
                    merged.append(rp)
                    merged_ids.add(pid)
            print(f"  [{TAG}] Merged: {len(modal_products)} modal + {len(raw_products)} inline → {len(merged)} unique products")
            raw_products = merged

        # ── STEP 4: Fetch stock data from basket_recalc API ──
        print(f"  [{TAG}] Step 4: Fetching stock data from basket_recalc API...")
        basket_products, full_stock_map = await fetch_green_from_basket_async(page, tag=TAG)
        if basket_products:
            print(f"  [{TAG}] Basket API: {len(basket_products)} products with stock data")
            basket_by_id = {}
            for bp in basket_products:
                pid = str(bp.get('id', ''))
                if pid:
                    basket_by_id[pid] = bp
            # Enrich existing raw_products
            enriched = 0
            for p in raw_products:
                pid = str(p.get('id', ''))
                if pid and pid in basket_by_id:
                    bp = basket_by_id[pid]
                    p['stock'] = bp.get('stock', p.get('stock', 0))
                    p['unit'] = bp.get('unit', p.get('unit', 'шт'))
                    p['can_buy'] = bp.get('can_buy', True)
                    if bp.get('currentPrice') and bp['currentPrice'] != '0':
                        p['currentPrice'] = bp['currentPrice']
                    if bp.get('oldPrice') and bp['oldPrice'] != '0':
                        p['oldPrice'] = bp['oldPrice']
                    if bp.get('image'):
                        p['image'] = bp['image']
                    p['stockText'] = bp.get('stockText', '')
                    enriched += 1
                else:
                    if pid and pid in full_stock_map:
                        sm = full_stock_map[pid]
                        if sm.get('value') and sm['value'] not in (0, 99):
                            p['stock'] = sm['value']
                            p['unit'] = sm.get('unit', 'шт')
                            enriched += 1
                    if 'stock' not in p or p.get('stock') is None:
                        p['stock'] = 0
                    if 'can_buy' not in p:
                        p['can_buy'] = True
                    if 'unit' not in p or not p.get('unit'):
                        p['unit'] = 'шт'
                p['type'] = 'green'
            # Basket API is used ONLY to enrich existing products (stock, price, image).
            # It must NEVER add new products — IS_GREEN=1 from basket_recalc is a stale
            # cached flag that doesn't reflect current green section state.
            print(f"  [{TAG}] Enriched {enriched}/{len(raw_products)} with basket stock data")
        else:
            print(f"  [{TAG}] ⚠️ No items from basket — trying full stock map...")
            sm_enriched = 0
            for p in raw_products:
                pid = str(p.get('id', ''))
                if pid and full_stock_map and pid in full_stock_map:
                    sm = full_stock_map[pid]
                    if sm.get('value') and sm['value'] not in (0, 99):
                        p['stock'] = sm['value']
                        p['unit'] = sm.get('unit', 'шт')
                        sm_enriched += 1
                if 'stock' not in p or p.get('stock') is None:
                    p['stock'] = 0
                if 'can_buy' not in p:
                    p['can_buy'] = True
                p['type'] = 'green'
            if sm_enriched:
                print(f"  [{TAG}] Full stock map enriched {sm_enriched}/{len(raw_products)} items")

        # ── STEP 5: Enrich missing from data-max ──
        missing_stock = [p for p in raw_products if not p.get('stock')]
        if missing_stock:
            dm_filled = 0
            for p in missing_stock:
                dm = p.get('dataMax', '')
                if dm:
                    try:
                        val = float(dm.replace(',', '.'))
                        if val > 0:
                            p['stock'] = val if '.' in str(dm) else int(val)
                            cp = p.get('currentPrice', '')
                            p['unit'] = 'кг' if 'кг' in cp else 'шт'
                            dm_filled += 1
                    except (ValueError, TypeError):
                        pass
            print(f"  [{TAG}] data-max enriched {dm_filled}/{len(missing_stock)} items")

        # ── STEP 5.5: Last resort stockText/default ──
        still_missing = [p for p in raw_products if not p.get('stock')]
        if still_missing:
            parsed_count = 0
            default_count = 0
            for p in still_missing:
                dm = p.get('dataMax', '')
                if dm:
                    try:
                        val = float(dm.replace(',', '.'))
                        if val > 0:
                            p['stock'] = val if '.' in str(dm) else int(val)
                            parsed_count += 1
                            continue
                    except (ValueError, TypeError):
                        pass
                st = p.get('stockText', '')
                parsed = parse_stock(st) if st else 0
                if parsed and parsed not in (99,):
                    p['stock'] = parsed
                    parsed_count += 1
                else:
                    p['stock'] = 1
                    default_count += 1
                if not p.get('unit'):
                    p['unit'] = 'шт'
            print(f"  [{TAG}] Last resort: {parsed_count} from data-max/card, {default_count} defaulted to 1")

        green_button_state = await js(page, r"""
            (() => {
                const btn = document.getElementById('js-Delivery__Order-green-show-all');
                if (!btn) return 'not_in_dom';
                if (btn.classList.contains('_hidden')) return 'hidden';
                return 'visible';
            })()
        """) or 'not_in_dom'
        section_found = str(green_button_state) != 'not_in_dom'

        # Save stock cache
        try:
            stock_cache = {}
            for p in raw_products:
                pid = str(p.get('id', ''))
                sv = p.get('stock')
                if pid and sv is not None and sv != 99 and sv != 0:
                    stock_cache[pid] = {'stock': sv, 'unit': p.get('unit', 'шт')}
            if stock_cache:
                cache_path = os.path.join(DATA_DIR, 'green_stock_cache.json')
                with open(cache_path, 'w', encoding='utf-8') as f:
                    json.dump(stock_cache, f, ensure_ascii=False)
                print(f"  [{TAG}] Saved {len(stock_cache)} stock values to cache")
        except Exception as e:
            print(f"  [{TAG}] Failed to save stock cache: {e}")

        # Check all unavailable
        if raw_products:
            unavailable = [p for p in raw_products if 'нет в наличии' in p.get('stockText', '').lower()]
            if len(unavailable) == len(raw_products):
                print(f"⚠️ [{TAG}] ALL items unavailable — green price is gone.")
                raw_products = []

        # Suspicious result checks
        existing_count = _load_existing_green_product_count()
        if _is_suspicious_empty(section_found, live_count, len(raw_products), existing_count):
            print(f"⚠️ [{TAG}] Empty result suspicious — preserving existing snapshot.")
            return [], False
        if _is_suspicious_single(live_count, len(raw_products), existing_count):
            print(f"⚠️ [{TAG}] Single-item result suspicious — preserving existing snapshot.")
            return [], False

        # Load stock cache as fallback
        prev_stock_map = {}
        try:
            cache_path = os.path.join(DATA_DIR, 'green_stock_cache.json')
            if os.path.exists(cache_path):
                with open(cache_path, 'r', encoding='utf-8') as f:
                    prev_stock_map = json.load(f)
                if prev_stock_map:
                    print(f"  [{TAG}] Loaded {len(prev_stock_map)} cached stock values as fallback")
        except Exception:
            pass

        # Process products
        products = []
        for p in raw_products:
            if not isinstance(p, dict) or 'name' not in p:
                continue
            p.pop('unavailable', None)
            p['currentPrice'] = clean_price(p.get('currentPrice', '0'))
            p['oldPrice'] = clean_price(p.get('oldPrice', '0'))
            p = synthesize_discount(p)
            existing_stock = p.get('stock')
            if existing_stock and existing_stock not in [0, '0']:
                p['stock'] = existing_stock
            else:
                p['stock'] = parse_stock(p.get('stockText', ''))
            p['unit'] = normalize_stock_unit(p.get('unit'), p['stock'])

            # Fallback from cache
            if p['stock'] in (0, 99):
                pid = str(p.get('id', ''))
                if pid in prev_stock_map:
                    cached = prev_stock_map[pid]
                    cached_stock = cached['stock']
                    if cached_stock and cached_stock not in (0, 99):
                        old_stock = p['stock']
                        p['stock'] = cached_stock
                        p['unit'] = cached['unit']
                        print(f"  [{TAG}] Cache fallback for {p.get('name','')[:25]}: {old_stock} → {p['stock']} {p['unit']}")

            if 'stockText' in p:
                del p['stockText']
            p['category'] = normalize_category('Зелёные ценники', p.get('name', ''), p.get('id'))
            products.append(p)

        products = deduplicate_products(products)
        # live_count comes only from inspect_green_section() DOM detection — NOT inflated
        print(f"✅ [{TAG}] Found {len(products)} green products")
        scrape_success = True

    except Exception as e:
        print(f"❌ [{TAG}] Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        cleanup_browser(browser, proc, tmp_profile)

        # Save results
        output_path = os.path.join(DATA_DIR, "green_products.json")
        if scrape_success:
            output_data = {
                "live_count": live_count,
                "scraped_count": len(products),
                "products": products
            }
            try:
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                save_products_safe(output_data, output_path)
                print(f"✅ Saved {len(products)} products (live_count={live_count}) -> {output_path}")
            except Exception as e:
                print(f"❌ Error saving {output_path}: {e}")
        else:
            print(f"⚠️ Scraper failed — keeping existing {output_path}")

    return products, scrape_success


def scrape_green_data():
    """Sync wrapper."""
    if not check_vkusvill_available():
        return False
    _, scrape_success = asyncio.run(scrape_green_data_async())
    return scrape_success


if __name__ == "__main__":
    raise SystemExit(0 if scrape_green_data() else 1)
