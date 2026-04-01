"""Research: inspect VkusVill green modal — fast version."""
import asyncio, json, sys
sys.path.insert(0, '/home/ubuntu/saleapp')
from green_common import launch_browser, load_cookies, js, navigate, close_delivery_modal, inspect_green_section, cleanup_browser

async def main():
    browser, proc, tmp = await launch_browser(tag="R")
    page = await browser.get('about:blank')
    await asyncio.sleep(0.5)
    await load_cookies(page, tag="R")
    # Navigate with shorter wait
    import nodriver.cdp.page as cdp_page
    try:
        await page.send(cdp_page.navigate(url='https://www.vkusvill.ru/cart/'))
    except: pass
    await asyncio.sleep(8)
    print("PAGE LOADED")

    await close_delivery_modal(page)
    await asyncio.sleep(1)

    found, items, live_count = await inspect_green_section(page)
    print(f'GREEN: found={found}, items={items}, live_count={live_count}')

    # Click green modal
    r = await js(page, """(() => {
        const btn = document.getElementById('js-Delivery__Order-green-show-all');
        if (!btn) return 'NO_BUTTON';
        btn.click();
        return 'CLICKED:' + btn.innerText.trim().substring(0, 40);
    })()""")
    print(f'BTN: {r}')
    await asyncio.sleep(3)

    # Initial modal state
    r = await js(page, """(() => {
        const m = document.getElementById('js-modal-cart-prods-scroll');
        if (!m) return JSON.stringify({modal: false});
        const cards = m.querySelectorAll('.ProductCard');
        // Find load-more buttons
        const btns = [];
        for (const el of m.querySelectorAll('*')) {
            const t = (el.innerText || '').trim().toLowerCase();
            if (t.length > 2 && t.length < 50 && el.offsetParent !== null) {
                if (t.includes('показать') || t.includes('загрузить') || t.includes('ещё') || t.includes('еще')) {
                    btns.push({tag: el.tagName, cls: (el.className||'').substring(0,50), text: t.substring(0,30)});
                }
            }
        }
        return JSON.stringify({cards: cards.length, scrollH: m.scrollHeight, clientH: m.clientHeight, btns: btns});
    })()""")
    print(f'MODAL INIT: {r}')

    # Now iterate: scroll + click "показать ещё" until gone
    for i in range(15):
        r = await js(page, """(() => {
            const m = document.getElementById('js-modal-cart-prods-scroll');
            if (!m) return JSON.stringify({err: 'no_modal'});
            // Scroll to bottom
            const cards = m.querySelectorAll('.ProductCard');
            if (cards.length > 0) cards[cards.length-1].scrollIntoView({behavior:'instant',block:'end'});
            m.scrollTop = m.scrollHeight;
            m.dispatchEvent(new Event('scroll', {bubbles: true}));
            // Find and click load-more
            let clicked = false;
            let btnText = '';
            let btnTag = '';
            let btnCls = '';
            for (const el of m.querySelectorAll('button, a, span, div')) {
                const t = (el.innerText || '').trim().toLowerCase();
                if (t.length > 2 && t.length < 50 && el.offsetParent !== null) {
                    if (t.includes('показать ещ') || t.includes('показать еще') ||
                        t.includes('загрузить ещ') || t.includes('загрузить еще') ||
                        t.includes('ещё товар') || t.includes('еще товар')) {
                        el.click();
                        clicked = true;
                        btnText = t;
                        btnTag = el.tagName;
                        btnCls = (el.className||'').substring(0,50);
                        break;
                    }
                }
            }
            return JSON.stringify({cards: cards.length, scrollH: m.scrollHeight, clicked, btnText, btnTag, btnCls});
        })()""")
        data = json.loads(r) if isinstance(r, str) else (r or {})
        print(f'  iter {i+1}: cards={data.get("cards")}, clicked={data.get("clicked")}, btn="{data.get("btnText","")}", scrollH={data.get("scrollH")}')
        if not data.get('clicked'):
            # No button found. Scroll once more and check if cards increase
            await asyncio.sleep(1)
            r2 = await js(page, """(() => {
                const m = document.getElementById('js-modal-cart-prods-scroll');
                if (!m) return 0;
                m.scrollTop = m.scrollHeight;
                return m.querySelectorAll('.ProductCard').length;
            })()""")
            print(f'  FINAL CHECK: {r2} cards, no more button => DONE')
            break
        await asyncio.sleep(3)

    await cleanup_browser(browser, proc, tmp)
    print("DONE")

asyncio.run(main())
