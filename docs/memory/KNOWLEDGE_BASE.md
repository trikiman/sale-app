# Knowledge Base

## VkusVill API Specs

### Add to Cart
**Endpoint**: `POST https://vkusvill.ru/ajax/delivery_order/basket_add.php`
**Headers**:
-   `Content-Type`: `application/x-www-form-urlencoded; charset=UTF-8`
-   `X-Requested-With`: `XMLHttpRequest`
-   `Referer`: `https://vkusvill.ru/`
-   `User-Agent`: (Valid Chrome UA)

**Payload (16 fields required)**:
```json
{
    "id": 106769,           // Product ID
    "xmlid": 106769,        // Same as id
    "max": 1,               // Quantity
    "delivery_no_set": "N",
    "koef": 1,
    "step": 1,
    "coupon": "",
    "isExperiment": "N",
    "isOnlyOnline": "",
    "isGreen": 0,           // 1 if green price item
    "user_id": 6443332,     // Must match authenticated user
    "skip_analogs": "",
    "is_app": "",
    "is_default_button": "Y",
    "cssInited": "N",
    "price_type": 222       // 1=Regular, 222=Red/Sale/Green
}
```

### Session Requirements
-   Must execute a GET request to `https://vkusvill.ru/` first to initialize server-side session.
-   Requires full set of cookies (exported from browser login) including `PHPSESSID` and `__Host-PHPSESSID`.

## Key Identifiers
-   **Green Price**: `isGreen=1`, `price_type=222` (usually).
-   **Regular Price**: `isGreen=0`, `price_type=1`.
