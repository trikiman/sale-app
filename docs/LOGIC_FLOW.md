# Application Logic & Data Flow

This document explains how the VkusVill Scraper and MiniApp work together to bring you the best discounts and personalized offers.

## The Ecosystem

The application consists of three main components that work in harmony:

1.  **The Scraper**: An automated bot that visits the VkusVill website to gather price information.
2.  **The Data Storage**: A central repository where all gathered information is cleaned, merged, and stored.
3.  **The MiniApp**: A user-friendly interface inside Telegram that lets you browse and filter the collected deals.

---

## Part 1: The Scraper (Data Collection)

### Goal: Emulate a Real User
The scraper doesn't just download a list of items; it acts like a real person using a web browser. This is necessary because VkusVill displays different prices based on whether you are logged in and what is in your cart.

### The "Browser"
The scraper uses a real Chrome browser controlled by software (Selenium/Playwright). It uses a **persistent profile**, which means it stays logged into the VkusVill account just like your personal browser remembers your passwords.

### Green Prices (Personalized)
"Green Prices" are 40% discounts on specific items. These are unique to each user.
*   The scraper logs in, goes to the **Cart** or specialized personal sections.
*   It identifies which items have been marked with a green price tag for that specific account.

### Red & Yellow Prices (Public)
*   **Red Prices**: Direct discounts on specific items available to everyone.
*   **Yellow Prices**: "6 or more" discounts (buy more, pay less).
*   The scraper browses the public catalog and categories to find these deals.

---

## Part 2: The Data Flow (Storage)

### Unified Format
Once the scraper has found all the Green, Red, and Yellow prices, it merges them into a single, standardized format. This ensures that the MiniApp can treat every "deal" the same way, regardless of where it came from.

### The "File Database" (`proposals.json`)
Instead of a complex database server, the app uses a simple file called `proposals.json` located in the `data/` folder. This file is the "source of truth" for the entire system.

### Public Access
To make the data available to the MiniApp (which runs in a user's web browser), the system copies the latest results to `miniapp/public/data.json`. This makes loading the data nearly instantaneous for the end user.

---

## Part 3: The MiniApp (User Interface)

### Platform: Telegram MiniApp
The interface is a web application designed specifically to be opened inside Telegram. This allows for a seamless experience without needing to install a separate app.

### Instant Loading
Because the MiniApp reads from a static `data.json` file, it doesn't need to wait for a database to respond. The list of hundreds of items loads almost immediately.

### Key Features
*   **Filtering**: Users can quickly toggle between Green, Red, and Yellow prices.
*   **Categories**: Items are automatically grouped by their real VkusVill categories (e.g., "Dairy", "Meat", "Fruits").
*   **Stock Levels**: The app detects if an item is out of stock and marks it clearly, so you don't try to buy something that isn't there.

---

## Part 4: Automation (The Pulse)

### The Heartbeat (Scheduler)
The system doesn't just run once. A scheduler (like Cron on Linux or Task Scheduler on Windows) triggers the scraper automatically at regular intervals:
*   **Full Sync**: Every 15 minutes to refresh the entire catalog.
*   **Fast Update**: Every 5 minutes for high-priority sections like the Cart.

### Self-Healing
If the internet goes down or the browser crashes, the system is designed to simply close everything and start fresh on the next scheduled run. This "self-healing" approach ensures the data stays up-to-date without manual intervention.
