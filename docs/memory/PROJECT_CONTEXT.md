# Project Context

## Overview
This project is a personal Telegram bot assistant for monitoring sales and adding products to the cart at **VkusVill** (ВкусВилл) grocery chain.

## Core Goals
1.  **Monitor Sales**: Scrape VkusVill products (Yellow/Red tags) and notify the user when favorite items are discounted.
2.  **Add to Cart via API**: Allow users to add discounted products directly to their VkusVill cart via Telegram command.
3.  **Per-User Authentication**: Each user authenticates with their own VkusVill account (using phone/SMS).
4.  **No Selenium Dependency**: Use direct HTTP API for reliability and speed (successfully reverse-engineered).

## Architecture
-   **Bot**: Python `python-telegram-bot`
-   **Database**: SQLite (`salebot.db`) via SQLAlchemy
-   **Scrapers**: `requests` + `BeautifulSoup` (for catalog) / custom scripts (legacy Selenium for scraping, migrating to API where possible)
-   **Cart API**: `cart/vkusvill_api.py` (pure HTTP client using `requests.Session`)
-   **Environment**: Windows, MINGW64

## Key Decisions
-   **Move away from Selenium for Cart**: Selenium is slow and unstable for transactional actions. We use the internal API `basket_add.php` instead for reliability.
-   **Session Management**: Cookies are stored in `data/cookies/{user_id}.json`. Users must re-login periodically (session expiration handling pending).
-   **GitHub Methodology**: Using this directory as project memory.
