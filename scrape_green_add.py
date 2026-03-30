"""
Green scraper — Script 1: Add ALL green items to cart.
No data scraping, no JSON writing. Just gets every green item into the VkusVill cart.

Flow:
1. Launch Chrome, load cookies, navigate to /cart/
2. Toggle "Больше товаров" switch
3. Seed item if cart is empty (prevents force-reload on first add)
4. Clear unavailable items
5. Close delivery modal
6. Open green modal (if visible) → scroll to load ALL items → click "В корзину" on each
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
    close_delivery_modal, close_green_modal, check_login, cleanup_browser,
    inspect_green_section, parse_nodriver_dict,
)
from utils import check_vkusvill_available

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

TAG = "GREEN-ADD"


# ── Card scope helpers ───────────────────────────────────────────────────────

def _green_inline_scope_expr() -> str:
    return r"""
        (() => {
            const isVisible = (el) => !!(el && el.offsetParent !== null && !el.classList.contains('_hidden'));
            const directGreenSection = document.getElementById('js-Delivery__Order-green-state-not-empty');
            if (isVisible(directGreenSection) && directGreenSection.querySelector('.ProductCard')) {
                return directGreenSection;
            }

            const candidates = [];
            const pushCandidate = (candidate) => {
                if (candidate && !candidates.includes(candidate)) {
                    candidates.push(candidate);
                }
            };

            const action = document.querySelector('[data-action="GreenLabels"]');
            if (action) {
                pushCandidate(action.closest('section, [class*="Section"], [class*="Tizer"], [class*="Cart"]'));
                let current = action.parentElement;
                for (let depth = 0; depth < 6 && current; depth += 1) {
                    pushCandidate(current);
                    current = current.parentElement;
                }
            }

            document.querySelectorAll('section, div, article').forEach((node) => {
                const text = (node.textContent || '').replace(/\u00a0/g, ' ');
                const isGreenSection = text.includes('Зелёные ценники')
                    || text.includes('Зеленые ценники');
                const hasNonGreen = text.includes('Добавьте в заказ');
                if (isGreenSection && !hasNonGreen && node.querySelector('.ProductCard')) {
                    pushCandidate(node);
                }
            });

            for (const candidate of candidates) {
                if (candidate && candidate.querySelector('.ProductCard')) {
                    return candidate;
                }
            }
            return null;
        })()
    """


def _green_card_scope_expr(card_source: str) -> str:
    if card_source == 'modal':
        return "document.getElementById('js-modal-cart-prods-scroll')"
    return _green_inline_scope_expr()


# ── Add to cart (batch JS) ───────────────────────────────────────────────────

async def _add_green_cards_to_cart(page, card_source: str, total_cards: int):
    """Click 'В корзину' on every green card in batches with delays."""
    scope_expr = _green_card_scope_expr(card_source)
    BATCH_SIZE = 10
    total_added = 0
    total_already = 0
    total_no_button = 0
    total_no_card = 0

    for batch_start in range(0, total_cards, BATCH_SIZE):
        batch_end = min(batch_start + BATCH_SIZE, total_cards)
        result_json = await js(page, f"""
            (() => {{
                const results = {{no_card: 0, already_in_cart: 0, added: 0, no_button: 0}};
                const scope = {scope_expr};
                if (!scope) return JSON.stringify(results);
                const cards = scope.querySelectorAll('.ProductCard, .ProductCards__item');
                for (let i = {batch_start}; i < {batch_end}; i++) {{
                    const card = cards[i];
                    if (!card) {{ results.no_card++; continue; }}
                    if (card.querySelector('.ProductCard__quantityControl, [class*="quantityControl"]')) {{
                        results.already_in_cart++;
                        continue;
                    }}
                    card.scrollIntoView({{behavior: 'instant', block: 'center'}});
                    let clicked = false;
                    const btns = card.querySelectorAll('button');
                    for (const btn of btns) {{
                        if (btn.disabled) continue;
                        const text = (btn.innerText || '').toLowerCase().trim();
                        if (text.includes('в корзину') || text.includes('корзин') || text.includes('добавить') || text.includes('доставить')) {{
                            btn.click();
                            clicked = true;
                            break;
                        }}
                    }}
                    if (!clicked) {{
                        const cssBtn = card.querySelector(
                            '.js-delivery__basket--add, .CartButton__content--add, .CartButton__content, ' +
                            '.ProductCard__add, .ProductCard__addToCart'
                        );
                        if (cssBtn) {{ cssBtn.click(); clicked = true; }}
                    }}
                    if (clicked) {{
                        results.added++;
                    }} else {{
                        results.no_button++;
                    }}
                    // Dismiss popups inline (sync)
                    const modals = document.querySelectorAll('[class*="Modal"]');
                    for (const m of modals) {{
                        if (m.id === 'js-modal-cart-prods-scroll') continue;
                        const txt = m.innerText || '';
                        if (txt.includes('Уже работаем') || txt.includes('похожие товары')) {{
                            const close = m.querySelector('[class*="close"], [class*="Close"]');
                            if (close) close.click();
                        }}
                    }}
                }}
                return JSON.stringify(results);
            }})()
        """)

        try:
            if isinstance(result_json, str):
                batch_data = json.loads(result_json)
            elif isinstance(result_json, dict):
                batch_data = result_json
            else:
                batch_data = {}
        except (json.JSONDecodeError, TypeError):
            batch_data = {}

        total_added += int(batch_data.get('added', 0))
        total_already += int(batch_data.get('already_in_cart', 0))
        total_no_button += int(batch_data.get('no_button', 0))
        total_no_card += int(batch_data.get('no_card', 0))

        if batch_start + BATCH_SIZE < total_cards:
            await asyncio.sleep(1.5)  # Let VkusVill process the batch

    results_summary = {
        'no_scope': 0, 'no_card': total_no_card, 'already_in_cart': total_already,
        'added': total_added, 'no_button': total_no_button,
    }
    return results_summary, total_added


# ── Main async function ─────────────────────────────────────────────────────

async def add_green_to_cart_async():
    """Add ALL green items to cart. No scraping, no JSON."""
    print(f"🔄 [{TAG}] Starting...")

    if not check_vkusvill_available():
        print(f"❌ [{TAG}] VkusVill not available")
        return False

    browser = None
    proc = None
    tmp_profile = None

    try:
        # ── STEP 1: Launch browser, load cookies, go to /cart/ ──
        browser, proc, tmp_profile = await launch_browser(tag=TAG)
        page = await browser.get('about:blank')
        await asyncio.sleep(1)

        cookies_ok = await load_cookies(page, tag=TAG)
        if not cookies_ok:
            print(f"⚠️ [{TAG}] No cookies loaded. Run tech-login from admin panel first.")

        await navigate(page, GREEN_URL, wait=15)

        if not await check_login(page, tag=TAG):
            return False

        # ── STEP 2: "Больше товаров" toggle — DISABLED ──
        # BUG-067 fix: This toggle expands product visibility to include items
        # from other delivery windows that the user doesn't see by default.
        # Result: scraper captured 12 items when VkusVill default shows 7.
        # Disabled so scraped data matches what users actually see on the site.
        print(f"  [{TAG}] Step 2: 'Больше товаров' toggle SKIPPED (matches user's default view)")

        # ── STEP 2.5: Seed item ──
        cart_check = await js(page, r"""
            (() => {
                const bodyText = document.body.innerText || '';
                if (bodyText.includes('Корзина ждёт') || bodyText.includes('Корзина пуста')) {
                    return {empty: true, reason: 'empty_text'};
                }
                const cartItems = document.querySelectorAll('.js-delivery-basket-item, .Delivery__Order__BasketItem');
                if (cartItems.length > 0) {
                    return {empty: false, reason: 'cart_items_' + cartItems.length};
                }
                const clearBtn = [...document.querySelectorAll('*')].find(el =>
                    (el.textContent || '').trim().includes('Очистить корзину') &&
                    (el.textContent || '').trim().length < 30
                );
                if (clearBtn) {
                    return {empty: false, reason: 'clear_btn_exists_but_0_items'};
                }
                return {empty: true, reason: 'no_items_no_clear'};
            })()
        """)
        cart_check = parse_nodriver_dict(cart_check)
        cart_empty = isinstance(cart_check, dict) and cart_check.get('empty', False)
        print(f"  [{TAG}] Cart empty: {cart_empty}")
        if cart_empty:
            print(f"  [{TAG}] Step 2.5: Cart is empty — adding seed item...")
            seed_added = await js(page, r"""
                (() => {
                    const sections = document.querySelectorAll('.VV23_CartPage_Section, [class*="Recommend"], [class*="recommend"]');
                    for (const section of sections) {
                        const title = section.querySelector('h2, h3, [class*="title"], [class*="Title"]');
                        if (title && (title.textContent || '').includes('Добавьте в заказ')) {
                            section.scrollIntoView({behavior: 'instant', block: 'center'});
                            const btn = section.querySelector('.js-delivery__basket--add, .CartButton__content, button[class*="cart"], button[class*="Cart"]');
                            if (btn) {
                                btn.scrollIntoView({behavior: 'instant', block: 'center'});
                                btn.click();
                                return 'added_from_recommend';
                            }
                        }
                    }
                    const greenSection = document.getElementById('js-Delivery__Order-green-state-not-empty');
                    const allBtns = document.querySelectorAll('.js-delivery__basket--add, .CartButton__content--add');
                    for (const btn of allBtns) {
                        if (greenSection && greenSection.contains(btn)) continue;
                        btn.scrollIntoView({behavior: 'instant', block: 'center'});
                        btn.click();
                        return 'added_fallback';
                    }
                    const allButtons = document.querySelectorAll('button');
                    for (const btn of allButtons) {
                        const t = (btn.innerText || '').toLowerCase();
                        if (t.includes('корзин') && !greenSection?.contains(btn)) {
                            btn.scrollIntoView({behavior: 'instant', block: 'center'});
                            btn.click();
                            return 'added_text_match';
                        }
                    }
                    return 'no_button_found';
                })()
            """)
            print(f"  [{TAG}] Seed item: {seed_added}")
            if seed_added and seed_added != 'no_button_found':
                await asyncio.sleep(5)
                await navigate(page, GREEN_URL, wait=8)
                print(f"  [{TAG}] Seed item added — cart is now non-empty")

        # ── STEP 2.9: Clear unavailable items ──
        print(f"  [{TAG}] Step 2.9: Clearing unavailable items from cart...")
        clear_result = await js(page, r"""
            (() => {
                const safeBtn = document.querySelector('button.js-delivery__basket_unavailable--clear');
                if (safeBtn) {
                    safeBtn.click();
                    return {method: 'unavailable_clear_btn', status: 'clicked'};
                }
                const unavailFooter = document.querySelector('.js-delivery__basket_footer--items-unavailable');
                if (unavailFooter) {
                    const deleteEls = unavailFooter.querySelectorAll('a, button, span, div');
                    for (const el of deleteEls) {
                        const text = (el.textContent || '').trim();
                        if (text.includes('Удалить') && text.length < 30) {
                            el.click();
                            return {method: 'footer_delete_text', status: 'clicked'};
                        }
                    }
                    return {method: 'none', status: 'footer_found_no_button'};
                }
                return {method: 'none', status: 'no_unavailable_section'};
            })()
        """)
        clear_result = parse_nodriver_dict(clear_result)
        if isinstance(clear_result, dict) and clear_result.get('status') == 'clicked':
            await asyncio.sleep(2)
            print(f"  [{TAG}] ✅ Cleared unavailable items via {clear_result.get('method')}")
            await navigate(page, GREEN_URL, wait=8)

        # ── STEP 2.95: Force-close delivery modal ──
        print(f"  [{TAG}] Step 2.95: Closing any delivery modal...")
        for _attempt in range(3):
            dm_result = await close_delivery_modal(page, tag=TAG)
            if dm_result == 'no_delivery_modal':
                break
            print(f"  [{TAG}] Delivery modal close attempt {_attempt+1}: {dm_result}")
            await asyncio.sleep(1)

        # ── STEP 3: Find green section ──
        print(f"  [{TAG}] Step 3: Looking for green section...")
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
        print(f"  [{TAG}] Inspected: live_count={live_count}")

        # Count inline green items
        inline_count = await js(page, r"""
            (() => {
                const gs = document.getElementById('js-Delivery__Order-green-state-not-empty');
                if (!gs) return 0;
                return gs.querySelectorAll('.ProductCard, .HProductCard').length;
            })()
        """) or 0
        print(f"  [{TAG}] Inline green items: {inline_count}")

        # ── STEP 4: Check green button state ──
        green_button = await js(page, r"""
            (() => {
                const btn = document.getElementById('js-Delivery__Order-green-show-all');
                if (!btn) return 'not_in_dom';
                if (btn.classList.contains('_hidden')) {
                    const section = document.getElementById('js-Delivery__Order-green-state-not-empty');
                    const inlineCards = section ? section.querySelectorAll('.ProductCard').length : 0;
                    return 'hidden:' + inlineCards;
                }
                return 'visible';
            })()
        """) or 'not_in_dom'
        green_button = str(green_button)
        print(f"  [{TAG}] Button state: {green_button}")

        total_added = 0

        if green_button == 'visible':
            # ── Button visible → click → modal → add all ──
            print(f"  [{TAG}] Opening green modal...")

            modal_ready = False
            for modal_attempt in range(3):
                dm_check = await close_delivery_modal(page, tag=TAG)
                if dm_check != 'no_delivery_modal':
                    print(f"  [{TAG}] Closed delivery modal before green button (attempt {modal_attempt+1})")
                    await asyncio.sleep(1)

                await js(page, r"""
                    (() => {
                        const section = document.getElementById('js-Delivery__Order-green-state-not-empty');
                        if (section) section.scrollIntoView({behavior: 'instant', block: 'center'});
                    })()
                """)
                await asyncio.sleep(1)

                clicked = await js(page, r"""
                    (() => {
                        const btn = document.getElementById('js-Delivery__Order-green-show-all');
                        if (btn && !btn.classList.contains('_hidden') && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
                            btn.click();
                            return true;
                        }
                        return false;
                    })()
                """)
                print(f"  [{TAG}] Button clicked: {clicked} (attempt {modal_attempt+1})")
                await asyncio.sleep(3)

                modal_state = await js(page, r"""
                    (() => {
                        const modal = document.getElementById('js-modal-cart-prods-scroll');
                        if (!modal) return 'not_open';
                        const _ms = getComputedStyle(modal);
                        if (_ms.display === 'none' || _ms.visibility === 'hidden') return 'not_open';

                        function _isVis(el) {
                            if (!el) return false;
                            const s = getComputedStyle(el);
                            return s.display !== 'none' && s.visibility !== 'hidden' && s.opacity !== '0';
                        }
                        const deliverySelectors = ['.VV23_RWayModal', '[class*="RWayModal"]', '[class*="DeliveryModal"]'];
                        for (const sel of deliverySelectors) {
                            const dm = document.querySelector(sel);
                            if (_isVis(dm)) return 'blocked_by_delivery';
                        }
                        const allModals = document.querySelectorAll('[class*="Modal"]');
                        for (const m of allModals) {
                            if (m === modal || m.contains(modal) || modal.contains(m)) continue;
                            if (!_isVis(m)) continue;
                            const text = (m.innerText || '').substring(0, 200);
                            if (text.includes('Ассортимент зависит') || text.includes('времени доставки')) {
                                return 'blocked_by_delivery';
                            }
                        }

                        const cards = modal.querySelectorAll('.ProductCard');
                        if (cards.length === 0) return 'open_but_empty';
                        return 'ready:' + cards.length;
                    })()
                """) or 'not_open'
                modal_state = str(modal_state)
                print(f"  [{TAG}] Modal state: {modal_state} (attempt {modal_attempt+1})")

                if modal_state.startswith('ready:'):
                    modal_ready = True
                    break
                elif modal_state == 'blocked_by_delivery':
                    print(f"  [{TAG}] ⚠️ Delivery modal blocking green modal — closing...")
                    await close_delivery_modal(page, tag=TAG)
                    await asyncio.sleep(2)
                    await close_green_modal(page)
                    await asyncio.sleep(1)
                    continue
                elif modal_state == 'open_but_empty':
                    print(f"  [{TAG}] Modal open but no cards yet — waiting...")
                    await asyncio.sleep(3)
                    recheck = await js(page, """
                        (() => {
                            const modal = document.getElementById('js-modal-cart-prods-scroll');
                            return modal ? modal.querySelectorAll('.ProductCard').length : 0;
                        })()
                    """) or 0
                    if int(recheck or 0) > 0:
                        modal_ready = True
                        break
                    continue

            if modal_ready:
                # ── Scroll modal to load ALL items ──
                # Simple approach: scroll down + click "показать ещё" until button
                # disappears and card count stops growing. No expected_total needed.
                print(f"  [{TAG}] Loading all modal items (live_count={live_count})...")

                prev_count = 0
                no_change = 0
                max_iters = 100
                for i in range(max_iters):
                    state = await js(page, r"""
                        (() => {
                            const modal = document.getElementById('js-modal-cart-prods-scroll');
                            if (!modal) return [0, false, 0, false];

                            const cards = modal.querySelectorAll('.ProductCard');

                            // Scroll to bottom to trigger lazy loading
                            if (cards.length > 0) {
                                cards[cards.length - 1].scrollIntoView({behavior: 'instant', block: 'end'});
                            }
                            modal.scrollTop = modal.scrollHeight;
                            modal.dispatchEvent(new Event('scroll', {bubbles: true}));

                            // Find and click "показать ещё" / "load more" button
                            let clicked = false;
                            let btnExists = false;

                            // CSS selectors for known load-more buttons
                            const selectors = ['.js-prods-modal-load-more', '.ProductCard__more',
                                               '.ModalProds__more', '[class*="load-more"]', '[class*="show-more"]',
                                               '[class*="LoadMore"]', '[class*="ShowMore"]'];
                            for (const sel of selectors) {
                                const btn = document.querySelector(sel);
                                if (btn && (btn.offsetParent !== null || btn.offsetWidth > 0)) {
                                    btn.click();
                                    clicked = true;
                                    btnExists = true;
                                    break;
                                }
                            }

                            // Text-based search for load-more button
                            if (!clicked) {
                                const allBtns = modal.querySelectorAll('button, a, span, div');
                                for (const el of allBtns) {
                                    const t = (el.innerText || '').trim().toLowerCase();
                                    if ((t.includes('показать ещё') || t.includes('загрузить ещё') ||
                                         t.includes('показать еще') || t.includes('загрузить еще') ||
                                         t.includes('ещё товар') || t.includes('еще товар')) && t.length < 50) {
                                        // Check if element is visible
                                        if (el.offsetParent !== null || el.offsetWidth > 0) {
                                            el.click();
                                            clicked = true;
                                            btnExists = true;
                                            break;
                                        }
                                    }
                                }
                            }

                            return [cards.length, clicked, modal.scrollHeight, btnExists];
                        })()
                    """) or [0, False, 0, False]
                    if not isinstance(state, list) or len(state) < 2:
                        state = [0, False, 0, False]
                    count = int(state[0] or 0)
                    clicked_more = bool(state[1])
                    scroll_h = int(state[2] or 0) if len(state) > 2 else 0
                    btn_exists = bool(state[3]) if len(state) > 3 else False

                    if i % 10 == 0 or count != prev_count or clicked_more:
                        print(f"    iter {i+1}: cards={count}, loaded_more={clicked_more}, btn_exists={btn_exists}, scrollH={scroll_h}")

                    if clicked_more:
                        # Button was clicked — wait for AJAX to load new items
                        # Poll DOM until card count increases or 6s timeout
                        old_count = count
                        for wait_step in range(12):
                            await asyncio.sleep(0.5)
                            new_count = await js(page, r"""
                                (() => {
                                    const m = document.getElementById('js-modal-cart-prods-scroll');
                                    return m ? m.querySelectorAll('.ProductCard').length : 0;
                                })()
                            """) or 0
                            new_count = int(new_count)
                            if new_count > old_count:
                                count = new_count
                                break
                        if count == old_count:
                            # AJAX might be slow, give it extra time
                            await asyncio.sleep(3)
                    else:
                        await asyncio.sleep(1.0)

                    # Stop condition: no "показать ещё" button AND card count stopped growing
                    if not btn_exists and not clicked_more and count == prev_count:
                        no_change += 1
                        if no_change >= 3:
                            print(f"    ✅ All items loaded: {count} cards (no more button, count stable)")
                            break
                    else:
                        no_change = 0

                    prev_count = count

                total_in_modal = max(prev_count, count) if (prev_count > 0 or count > 0) else 0
                print(f"  [{TAG}] Modal loaded: {total_in_modal} cards")

                # ── Scrape product data from modal DOM (BEFORE adding to cart) ──
                # This captures ALL products even if VkusVill drops some cart clicks.
                # Same approach as the original working scrape_green.py
                if total_in_modal > 0:
                    print(f"  [{TAG}] Scraping product data from modal DOM...")
                    modal_products = await js(page, r"""
                        (() => {
                            const products = [];
                            const modal = document.getElementById('js-modal-cart-prods-scroll');
                            if (!modal) return products;

                            modal.querySelectorAll('.ProductCard').forEach(card => {
                                const nameEl = card.querySelector('.ProductCard__link');
                                const priceEl = card.querySelector('.ProductCard__price--current, .Price__value, .ProductCard__price');
                                const oldPriceEl = card.querySelector('.ProductCard__price--old, .ProductCard__OldPrice, .js-datalayer-catalog-list-price-old, del, s');
                                const imgEl = card.querySelector('.ProductCard__image img, .ProductCard__imageLink img, img');

                                if (!nameEl) return;
                                const name = nameEl.innerText.trim();
                                if (!name) return;

                                const url = nameEl.href || '';
                                const idMatch = url.match(/-(\d+)\.html/) || url.match(/(\d+)\.html/);
                                let productId = idMatch ? idMatch[1] : '';

                                // Try data-id attribute as fallback
                                if (!productId) {
                                    const dataIdEl = card.querySelector('[data-id]');
                                    if (dataIdEl) productId = dataIdEl.getAttribute('data-id') || '';
                                }

                                // Image extraction
                                let imgSrc = '';
                                if (imgEl) {
                                    imgSrc = imgEl.getAttribute('data-src') || imgEl.src || '';
                                }
                                if (!imgSrc || imgSrc.includes('data:image')) {
                                    const source = card.querySelector('picture source[srcset]');
                                    if (source && source.srcset) imgSrc = source.srcset.split(' ')[0];
                                }
                                if (!imgSrc || imgSrc.includes('data:image')) {
                                    const bgEl = card.querySelector('.ProductCard__imageLink, .ProductCard__image');
                                    if (bgEl) {
                                        const bg = window.getComputedStyle(bgEl).backgroundImage;
                                        if (bg && bg !== 'none' && bg.startsWith('url')) {
                                            imgSrc = bg.replace(/^url\(['"]?/, '').replace(/['"]?\)$/, '');
                                        }
                                    }
                                }
                                if (imgSrc && (imgSrc.includes('no-image.svg') || imgSrc.includes('data:image') || imgSrc.includes('spacer.gif'))) {
                                    imgSrc = '';
                                }

                                // Price extraction
                                let currentPrice = priceEl ? priceEl.innerText.trim() : '0';
                                let oldPrice = oldPriceEl ? oldPriceEl.innerText.trim() : '0';

                                // data-max for stock
                                let dataMax = '';
                                const addBtn = card.querySelector('.js-delivery__basket--add, [data-max], button[class*="Cart"]');
                                if (addBtn && addBtn.getAttribute('data-max')) {
                                    dataMax = addBtn.getAttribute('data-max');
                                }
                                if (!dataMax) {
                                    const qtyCtrl = card.querySelector('[data-max]');
                                    if (qtyCtrl) dataMax = qtyCtrl.getAttribute('data-max') || '';
                                }

                                // Unit detection
                                const isWeightItem = name.includes('ВЕС') ||
                                    name.toLowerCase().includes('/кг') ||
                                    (priceEl && priceEl.innerText.includes('/кг'));

                                products.push({
                                    id: productId,
                                    name: name,
                                    url: url,
                                    currentPrice: currentPrice,
                                    oldPrice: oldPrice,
                                    image: imgSrc,
                                    dataMax: dataMax,
                                    unit: isWeightItem ? 'кг' : 'шт',
                                    category: 'Зелёные ценники',
                                    type: 'green'
                                });
                            });
                            return products;
                        })()
                    """) or []
                    if not isinstance(modal_products, list):
                        modal_products = []
                    print(f"  [{TAG}] Scraped {len(modal_products)} products from modal DOM")

                    # Save modal products to JSON — scrape_green_data.py will use this
                    if modal_products:
                        modal_path = os.path.join(DATA_DIR, 'green_modal_products.json')
                        try:
                            os.makedirs(DATA_DIR, exist_ok=True)
                            with open(modal_path, 'w', encoding='utf-8') as f:
                                json.dump({
                                    'products': modal_products,
                                    'total_in_modal': total_in_modal,
                                    'timestamp': time.time(),
                                }, f, ensure_ascii=False, indent=2)
                            print(f"  [{TAG}] ✅ Saved {len(modal_products)} modal products → {modal_path}")
                        except Exception as e:
                            print(f"  [{TAG}] ⚠️ Failed to save modal products: {e}")

                # ── Add all to cart ──
                if total_in_modal > 0:
                    print(f"  [{TAG}] Adding {total_in_modal} items to cart...")
                    results_summary, added = await _add_green_cards_to_cart(page, 'modal', total_in_modal)
                    print(f"  [{TAG}] Modal add-to-cart: {results_summary}")
                    print(f"  [{TAG}] Added {added}/{total_in_modal} items to cart")
                    total_added = added

                await close_green_modal(page)
                print(f"  [{TAG}] Closed green modal")
            else:
                print(f"  [{TAG}] Modal didn't open")

        elif green_button.startswith('hidden:'):
            # ── Button hidden → add inline items ──
            inline_count = int(green_button.split(':')[1] or 0)
            print(f"  [{TAG}] Button hidden — {inline_count} inline items")
            if inline_count > 0:
                results_summary, added = await _add_green_cards_to_cart(page, 'inline', inline_count)
                print(f"  [{TAG}] Inline add-to-cart: {results_summary}")
                total_added = added

        else:
            # ── Button not in DOM ──
            if inline_count > 0:
                print(f"  [{TAG}] Button not in DOM but {inline_count} green items found — adding inline...")
                await js(page, """
                    (() => {
                        const gs = document.getElementById('js-Delivery__Order-green-state-not-empty');
                        if (gs) gs.scrollIntoView({behavior: 'instant', block: 'center'});
                    })()
                """)
                await asyncio.sleep(3)
                results_summary, added = await _add_green_cards_to_cart(page, 'inline', inline_count)
                print(f"  [{TAG}] Inline add-to-cart: {results_summary}")
                total_added = added
            else:
                print(f"  [{TAG}] No green items to add")

        print(f"✅ [{TAG}] Complete. Added {total_added} green items to cart.")
        return True

    except Exception as e:
        print(f"❌ [{TAG}] Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        cleanup_browser(browser, proc, tmp_profile)


def add_green_to_cart():
    """Sync wrapper."""
    if not check_vkusvill_available():
        return False
    return asyncio.run(add_green_to_cart_async())


if __name__ == "__main__":
    raise SystemExit(0 if add_green_to_cart() else 1)
