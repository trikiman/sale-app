# Roadmap (Master Plan)

## Milestone 1: Automated Scrapers ✅
-   [x] Initial product parsing (Yellow/Red price tags).
-   [x] Database integration (`salebot.db`).
-   [x] Telegram notifications.

## Milestone 2: Cart API Integration (In Progress) 🚧
-   [x] Reverse engineer `basket_add.php` API.
-   [x] Create `cart/vkusvill_api.py`.
-   [ ] Verify error handling (out of stock, max quantity).
-   [ ] **Integrate to Bot**: Add "🛒 В корзину" button to product cards.

## Milestone 3: Authentication & Multi-user Support
-   [ ] **Per-User Sessions**: Store unique cookies for each Telegram user.
-   [ ] **Auth Flow**: `/login` command prompting for phone -> SMS code -> Cookie capture.
-   [ ] **Session Refresh**: Handle expired sessions gracefully.

## Milestone 4: Maintenance & Reliability
-   [ ] Clean up Selenium dependencies where possible.
-   [ ] Improve logging and monitoring.
-   [ ] Containerize with Docker.
