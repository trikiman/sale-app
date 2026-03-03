# Knowledge Base

## VkusVill Cart API

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
1. **Playwright sessions lack address**: Playwright login creates a new PHPSESSID with no delivery address → cart API fails. Use `undetected_chromedriver` instead.
2. **Cookie expiry**: PHPSESSID expires after ~24h of inactivity. User must re-login.
3. **Address binding**: Selecting address in the browser UI binds it server-side. No known API endpoint to set address programmatically.
4. **VkusVill anti-bot on login click**: `undetected_chromedriver` can load VkusVill homepage (424K page) but clicking the login button (`button.js-header-login-`) crashes the Chrome session. The anti-bot detects automation and kills DevTools connection. Headless mode (`--headless=new`) also crashes Chrome v145 on Windows 11 — use offscreen window (`--window-position=-2400,-2400`) as workaround.

## Chrome on Windows 11 Notes
- Chrome v145.0.7632.117 installed (after Win10→Win11 reinstall)
- `undetected_chromedriver` 3.5.5
- `--headless=new` crashes — use `--window-position=-2400,-2400` instead
- `version_main=145` required (was 144 before Chrome update)
- `WinError 6: The handle is invalid` on `driver.quit()` is harmless cleanup warning
- Non-headless mode works fine for page loading/scraping

## VkusVill Login Page Selectors (as of 2026-03-02)
- Login button: `button.js-header-login-` (class `VV_ResetStyleBtn UniversMainIcBtn js-header-login-`)
- Also exists: `button.VV_ResetStyleBtn.VV_FFXMenuNav__ListLink._auth._btn` in side menu
- Phone input (after login form opens): `input.js-user-form-getcode-api-phone`, `input[type="tel"]`
- SMS code input: `input.js-user-form-checksms-api-sms`
- Get code button: button with text "Получить код"
