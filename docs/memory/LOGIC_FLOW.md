# Application Logic & Data Flow

This document explains how the VkusVill Scraper and MiniApp work together to bring you the best discounts and personalized offers.

## The Ecosystem

The application consists of three main components that work in harmony:

1.  **The Scraper**: An automated bot that visits the VkusVill website to gather price information.
2.  **The Data Storage**: A central repository where all gathered information is cleaned, merged, and stored.
3.  **The MiniApp**: A user-friendly interface inside Telegram that lets you browse and filter the collected deals.

---

## Part 1: The Scraper (Data Collection)

### Parallel Execution
The system uses a multi-process architecture to maximize speed. Instead of one long sequential run, it launches three scrapers simultaneously:
1.  **Green Scraper**: Focuses on personalized 40% discounts by accessing the user's cart and personal sections.
2.  **Red Scraper**: Scans the catalog for public direct discounts available to all customers.
3.  **Yellow Scraper**: Identifies "6 or more" multi-buy deals across the store.

### Goal: Emulate a Real User
The scraper doesn't just download a list of items; it acts like a real person using a web browser. This is necessary because VkusVill displays different prices based on whether you are logged in and what is in your cart.

### The "Browser"
Each parallel scraper uses a real Chrome browser controlled by software (Selenium/Playwright). They use **persistent profiles**, which means they stay logged into the VkusVill account just like your personal browser remembers your passwords.

---

## Part 2: The Data Flow (Storage)

### The Merge Process
After the parallel scrapers complete their tasks, a dedicated **Merge Step** takes over. This step is responsible for:
1.  **Consolidation**: Reading the individual outputs from the Green, Red, and Yellow scrapers.
2.  **Deduplication**: Ensuring that if an item appears in multiple categories, it is handled correctly.
3.  **Standardization**: Converting all data into a single, unified format that the MiniApp understands.

### Performance Reporting
Upon completion, the system generates a summary in the logs:
*   **Total Counts**: The final number of unique deals available.
*   **Colored Summary**: A breakdown of the number of items found for each price type (Green/Red/Yellow).

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
