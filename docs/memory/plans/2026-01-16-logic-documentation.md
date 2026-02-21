# App Logic & Data Flow Documentation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Create a comprehensive, non-technical documentation file explaining how the application collects, stores, and displays data.

**Architecture:** Documentation only. No code changes.

**Tech Stack:** Markdown.

---

### Task 1: Create Logic Documentation

**Files:**
- Create: `docs/LOGIC_FLOW.md`

**Step 1: Write the Logic Documentation**

Create `docs/LOGIC_FLOW.md` with the following structure:

1.  **The Ecosystem**: High-level overview of the 3 main parts (The Scraper, The Data, The MiniApp).
2.  **Part 1: The Scraper (Data Collection)**
    *   **Goal**: Emulate a real user to see personalized and public discounts.
    *   **Green Prices**: Explaining that these are personalized, require login, and are found in the "Cart".
    *   **Red & Yellow Prices**: Explaining these are public catalog items.
    *   **The "Browser"**: Mention it uses a real browser (Chrome) with a persistent profile to stay logged in.
3.  **Part 2: The Data Flow (Storage)**
    *   **Unified Format**: How all 3 types are merged into one list.
    *   **The "File Database"**: Explaining `proposals.json` as the central truth.
    *   **Public Access**: Copying to `miniapp/public/data.json` for the web app.
4.  **Part 3: The MiniApp (User Interface)**
    *   **Platform**: Telegram MiniApp (embedded website).
    *   **Instant Loading**: Reads the static JSON file directly.
    *   **Features**: Filtering (Green/Red/Yellow), Categories, Stock Levels.
5.  **Part 4: Automation (The Pulse)**
    *   **The Heartbeat**: Cron/Scheduler running every 5/15 minutes.
    *   **Self-Healing**: How it restarts if it crashes (basic concept).

**Step 2: Commit**

```bash
git add docs/LOGIC_FLOW.md
git commit -m "docs: add high-level app logic and data flow documentation"
```
