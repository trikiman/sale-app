# Current Task: VkusVill Cart API

**Objective**: Allow users to add products to the VkusVill cart via Telegram command.

## Context
VkusVill's website uses an AJAX API (`basket_add.php`) to modify the cart. We reversed engineered this endpoint.

## Implementation Details
-   **API Endpoint**: `POST https://vkusvill.ru/ajax/delivery_order/basket_add.php`
-   **Method**: Pure HTTP request (no Selenium).
-   **Requirements**:
    -   Valid `User-Agent` and `Referer`.
    -   Complete cookie set (exported via Selenium initially).
    -   **Critical**: Initial GET request to warm up the session before POST.
    -   **Critical**: All 16 form data fields must be present.

## Progress
-   [x] Reverse engineered API payload (id, xmlid, etc.).
-   [x] Implemented `cart/vkusvill_api.py` module.
-   [x] Verified adding item 42530 (Borsch) works.

## Next Steps
1.  **Error Handling**: Handle cases where product is out of stock or max quantity reached.
2.  **Get Cart**: Implement `get_cart()` to view current items.
3.  **Bot Integration**: Add the button to the Telegram interface.
