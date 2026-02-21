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
