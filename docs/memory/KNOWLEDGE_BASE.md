# Knowledge Base

## VkusVill Cart API

### Endpoints (all confirmed working as of 2026-03-05)

| Purpose | Endpoint | Method |
|---------|----------|--------|
| Add item | `basket_add.php` | POST |
| Remove/modify item | `basket_update.php` | POST |
| Read cart (no side effects) | `basket_recalc.php` | POST |
| ~~Remove item~~ | ~~`basket_remove.php`~~ | ~~POST~~ — **404, does not exist** |

### Add to Cart
**Endpoint**: `POST https://vkusvill.ru/ajax/delivery_order/basket_add.php`

**Headers**:
- `Content-Type`: `application/x-www-form-urlencoded; charset=UTF-8`
- `X-Requested-With`: `XMLHttpRequest`
- `Origin`: `https://vkusvill.ru`
- `Referer`: Product page URL

**Full Payload (16 fields)**:
```
id: 106769              # Product ID
xmlid: 106769           # Same as id
max: 1                  # Quantity
delivery_no_set: N
koef: 1
step: 1
coupon:
isExperiment: N
isOnlyOnline:
isGreen: 0              # 1 if green price
user_id: 6443332        # Must match authenticated user!
skip_analogs:
is_app:
is_default_button: Y
cssInited: N
price_type: 222         # 1=Regular, 222=Red/Sale/Green
```

> **CRITICAL**: The `user_id` field must match the authenticated user. Without it, VkusVill may reject the request.

### Session Requirements
1. Must GET `https://vkusvill.ru/` first to initialize server session (warmup)
2. Requires full cookie set including `__Host-PHPSESSID`
3. **Delivery address must be bound server-side** to the session — VkusVill stores address per PHPSESSID, not in cookies
4. Missing address → all cart adds fail with `POPUP_ANALOGS` (out of stock for unknown location)

### Key Cookie Names
| Cookie | Purpose |
|--------|---------|
| `__Host-PHPSESSID` | Server session ID (httpOnly) |
| `BXVV_SALE_UID` | Bitrix user account ID |
| `BXVV_SALE_UID_KEY` | Auth key |
| `MLD_LAT` / `MLD_LON` | Delivery coordinates (frontend only) |
| `HTB_S` / `HTB_ID` | Store IDs |
| `UF_USER_AUTH` | Client-side auth flag (set by JS) |
| `DeliverySelectLast` | Last delivery type (`d`=delivery) |

## Product Types
- **Green Price**: `isGreen=1`, `price_type=222`
- **Regular Price**: `isGreen=0`, `price_type=1`
- **Red/Sale Price**: `isGreen=0`, `price_type=222`

## Known Issues
1. **Playwright sessions lack address**: Playwright login creates a new PHPSESSID with no delivery address → cart API fails. Use `nodriver` instead.
2. **Cookie expiry**: PHPSESSID expires after ~24h of inactivity. User must re-login.
3. **Address binding**: Selecting address in the browser UI binds it server-side. No known API endpoint to set address programmatically.
4. **VkusVill anti-bot on login click**: `undetected_chromedriver` was fingerprinted. All auth and scrapers now use `nodriver` (CDP-native). Chrome launched via `subprocess.Popen` + `nodriver.Browser.create(host, port)`.

## Chrome on Windows 11 Notes
- Chrome v145.0.7632.117 installed
- **All scrapers use `nodriver`** — `undetected_chromedriver` is no longer used anywhere
- `--headless=new` crashes — use `--window-position=-2400,-2400` (offscreen) for auth login
- Scrapers use `--start-maximized` (visible) which works fine on Windows
- Chrome launched via `subprocess.Popen(args)` + `nodriver.Browser.create(host='127.0.0.1', port=port)`
- Temp profiles: `tempfile.mkdtemp(prefix='uc_XXX_')` — cleaned up by `shutil.rmtree()` in finally blocks
- Chrome process must be killed via `proc.kill()` after `browser.stop()` — graceful CDP close alone leaves zombie processes

## nodriver SMS/Phone Input Pattern
VkusVill uses masked inputs that only respond to real keyboard events:
```python
for digit in code:
    await tab.send(uc.cdp.input_.dispatch_key_event(
        type_='keyDown', key=digit, text=digit,
        code=f'Digit{digit}',
        windows_virtual_key_code=ord(digit),
        native_virtual_key_code=ord(digit),
    ))
    await asyncio.sleep(0.05)
    await tab.send(uc.cdp.input_.dispatch_key_event(
        type_='keyUp', key=digit,
        code=f'Digit{digit}',
        windows_virtual_key_code=ord(digit),
        native_virtual_key_code=ord(digit),
    ))
    await asyncio.sleep(0.15)
```
`send_keys()` and JS value setters do NOT work on VkusVill's masked inputs.

### Read Cart (no side effects)
**Endpoint**: `POST https://vkusvill.ru/ajax/delivery_order/basket_recalc.php`
**Referer**: `https://vkusvill.ru/cart/` (required)
**Payload**: `{COUPON: '', BONUS: '', sessid: '<sessid>'}`
**Response**: Same structure as `basket_add.php` — `{success:'Y', basket:{...}, totals:{Q_ITEMS, PRICE_FINAL}}`
**Basket key format**: `{PRODUCT_ID}_{INDEX}` e.g. `731_0`, `731_1` — NOT `{product_id}_{price_type}`

### Remove/Delete Cart Item
**Endpoint**: `POST https://vkusvill.ru/ajax/delivery_order/basket_update.php`
**Referer**: `https://vkusvill.ru/cart/` (required)
**Payload for delete**:
```
id: 731_0           # basket key (from get_cart response)
productId: 731      # product ID
isGreen: 0          # 1 if green item
q: 0                # target quantity (0 = delete)
q_old: 1            # previous quantity
koef: 1
step: 1
coupon:
bonus:
type: del           # 'del' for delete, 'basket_up'/'basket_down' for qty change
typeBtn:
sessid: <sessid>
```

## VkusVill Login Page Selectors (as of 2026-03-02)
- Login button: `button.js-header-login-` (class `VV_ResetStyleBtn UniversMainIcBtn js-header-login-`)
- Also exists: `button.VV_ResetStyleBtn.VV_FFXMenuNav__ListLink._auth._btn` in side menu
- Phone input (after login form opens): `input.js-user-form-getcode-api-phone`, `input[type="tel"]`
- SMS code input: `input.js-user-form-checksms-api-sms`
- Get code button: button with text "Получить код"
