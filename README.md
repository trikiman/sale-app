# VkusVill Sale Monitor Bot

A Telegram bot to monitor VkusVill product prices and add them to cart.

## Features
-   **Price Monitoring**: Checks Yellow/Red price tags.
-   **Add to Cart**: Adds items to VkusVill cart via API.
-   **Authentication**: Supports per-user VkusVill accounts.

## Documentation
This project uses "GitHub Projects as Memory" methodology for documentation.
See **[docs/memory](./docs/memory/README.md)** for:
-   [Project Context](./docs/memory/PROJECT_CONTEXT.md)
-   [Roadmap](./docs/memory/ROADMAP.md)
-   [Current Task](./docs/memory/CURRENT_TASK.md)
-   [Knowledge Base](./docs/memory/KNOWLEDGE_BASE.md)

## Current Status
- Green scraper automation is currently blocked on a browser-profile-state mismatch. The live VkusVill cart can show green items that the automatic scraper still fails to reproduce from `data/cookies.json` or `data/tech_profile` alone.
- See [Current Task](./docs/memory/CURRENT_TASK.md) for the March 8, 2026 handoff details and exact next debugging step.

## Setup
1.  Install dependencies: `pip install -r requirements.txt`
2.  Configure `config.py`.
3.  Run: `python main.py`
