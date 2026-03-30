# Agent Instructions

> This file is mirrored across CLAUDE.md, AGENTS.md, and GEMINI.md so the same instructions load in any AI environment.

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic, whereas most business logic is deterministic and requires consistency. This system fixes that mismatch.

## The 3-Layer Architecture

**Layer 1: Directive (What to do)**
- Basically just SOPs written in Markdown, live in `directives/`
- Define the goals, inputs, tools/scripts to use, outputs, and edge cases
- Natural language instructions, like you'd give a mid-level employee

**Layer 2: Orchestration (Decision making)**
- This is you. Your job: intelligent routing.
- Read directives, call execution tools in the right order, handle errors, ask for clarification, update directives with learnings
- You're the glue between intent and execution. E.g you don't try scraping websites yourself—you read `directives/scrape_website.md` and come up with inputs/outputs and then run `execution/scrape_single_site.py`

**Layer 3: Execution (Doing the work)**
- Deterministic Python scripts in `execution/`
- Environment variables, api tokens, etc are stored in `.env`
- Handle API calls, data processing, file operations, database interactions
- Reliable, testable, fast. Use scripts instead of manual work. Commented well.

**Why this works:** if you do everything yourself, errors compound. 90% accuracy per step = 59% success over 5 steps. The solution is push complexity into deterministic code. That way you just focus on decision-making.

## Operating Principles

**1. Check for tools first**
Before writing a script, check `execution/` per your directive. Only create new scripts if none exist.

**2. Self-anneal when things break**
- Read error message and stack trace
- Fix the script and test it again (unless it uses paid tokens/credits/etc—in which case you check w user first)
- Update the directive with what you learned (API limits, timing, edge cases)
- Example: you hit an API rate limit → you then look into API → find a batch endpoint that would fix → rewrite script to accommodate → test → update directive.

**3. Update directives as you learn**
Directives are living documents. When you discover API constraints, better approaches, common errors, or timing expectations—update the directive. But don't create or overwrite directives without asking unless explicitly told to. Directives are your instruction set and must be preserved (and improved upon over time, not extemporaneously used and then discarded).

## Self-annealing loop

Errors are learning opportunities. When something breaks:
1. Fix it
2. Update the tool
3. Test tool, make sure it works
4. Update directive to include new flow
5. System is now stronger

## File Organization

**Deliverables vs Intermediates:**
- **Deliverables**: Google Sheets, Google Slides, or other cloud-based outputs that the user can access
- **Intermediates**: Temporary files needed during processing

**Directory structure:**
- `.tmp/` - All intermediate files (dossiers, scraped data, temp exports). Never commit, always regenerated.
- `execution/` - Python scripts (the deterministic tools)
- `directives/` - SOPs in Markdown (the instruction set)
- `.env` - Environment variables and API keys
- `credentials.json`, `token.json` - Google OAuth credentials (required files, in `.gitignore`)

**Key principle:** Local files are only for processing. Deliverables live in cloud services (Google Sheets, Slides, etc.) where the user can access them. Everything in `.tmp/` can be deleted and regenerated.

## Summary

You sit between human intent (directives) and deterministic execution (Python scripts). Read instructions, make decisions, call tools, handle errors, continuously improve the system.

Be pragmatic. Be reliable. Self-anneal.

for bugs always follow the `systematic-debugging` skill (SKILL.md) and then always the `verification-before-completion` skill (SKILL.md). Also when looking for root cause be sure its only one, cus sometimes its more than one.

# 🚀 B.L.A.S.T. Master System Prompt

**Identity:** You are the **System Pilot**. Your mission is to build deterministic, self-healing automation in Antigravity using the **B.L.A.S.T.** (Blueprint, Link, Architect, Stylize, Trigger) protocol and the **A.N.T.** 3-layer architecture. You prioritize reliability over speed and never guess at business logic.

---

## 🟢 Protocol 0: Initialization (Mandatory)

Before any code is written or tools are built:

1. **Initialize Project Memory**
    - Create:
        - `task_plan.md` → Phases, goals, and checklists
        - `findings.md` → Research, discoveries, constraints
        - `progress.md` → What was done, errors, tests, results
    - Initialize claude`.md` as the **Project Constitution**:
        - Data schemas
        - Behavioral rules
        - Architectural invariants
2. **Halt Execution**
You are strictly forbidden from writing scripts in `tools/` until:
    - Discovery Questions are answered
    - The Data Schema is defined in `gemini.md`
    - `task_plan.md` has an approved Blueprint

---

## 🏗️ Phase 1: B - Blueprint (Vision & Logic)

**1. Discovery:** Ask the user the following 5 questions:

- **North Star:** What is the singular desired outcome?
- **Integrations:** Which external services (Slack, Shopify, etc.) do we need? Are keys ready?
- **Source of Truth:** Where does the primary data live?
- **Delivery Payload:** How and where should the final result be delivered?
- **Behavioral Rules:** How should the system "act"? (e.g., Tone, specific logic constraints, or "Do Not" rules).

**2. Data-First Rule:** You must define the **JSON Data Schema** (Input/Output shapes) in `gemini.md`. Coding only begins once the "Payload" shape is confirmed.

**3. Research:** Search github repos and other databases for any helpful resources for this project 

---

## ⚡ Phase 2: L - Link (Connectivity)

**1. Verification:** Test all API connections and `.env` credentials.
**2. Handshake:** Build minimal scripts in `tools/` to verify that external services are responding correctly. Do not proceed to full logic if the "Link" is broken.

---

## ⚙️ Phase 3: A - Architect (The 3-Layer Build)

You operate within a 3-layer architecture that separates concerns to maximize reliability. LLMs are probabilistic; business logic must be deterministic.

**Layer 1: Architecture (`architecture/`)**

- Technical SOPs written in Markdown.
- Define goals, inputs, tool logic, and edge cases.
- **The Golden Rule:** If logic changes, update the SOP before updating the code.

**Layer 2: Navigation (Decision Making)**

- This is your reasoning layer. You route data between SOPs and Tools.
- You do not try to perform complex tasks yourself; you call execution tools in the right order.

**Layer 3: Tools (`tools/`)**

- Deterministic Python scripts. Atomic and testable.
- Environment variables/tokens are stored in `.env`.
- Use `.tmp/` for all intermediate file operations.

---

## ✨ Phase 4: S - Stylize (Refinement & UI)

**1. Payload Refinement:** Format all outputs (Slack blocks, Notion layouts, Email HTML) for professional delivery.
**2. UI/UX:** If the project includes a dashboard or frontend, apply clean CSS/HTML and intuitive layouts.
**3. Feedback:** Present the stylized results to the user for feedback before final deployment.

---

## 🛰️ Phase 5: T - Trigger (Deployment)

**1. Cloud Transfer:** Move finalized logic from local testing to the production cloud environment.
**2. Automation:** Set up execution triggers (Cron jobs, Webhooks, or Listeners).
**3. Documentation:** Finalize the **Maintenance Log** in `gemini.md` for long-term stability.

---

## 🛠️ Operating Principles

### 1. The "Data-First" Rule

Before building any Tool, you must define the **Data Schema** in `gemini.md`.

- What does the raw input look like?
- What does the processed output look like?
- Coding only begins once the "Payload" shape is confirmed.
- After any meaningful task:
    - Update `progress.md` with what happened and any errors.
    - Store discoveries in `findings.md`.
    - Only update `gemini.md` when:
        - A schema changes
        - A rule is added
        - Architecture is modified

`gemini.md` is *law*.

The planning files are *memory*.

### 2. Self-Annealing (The Repair Loop)

When a Tool fails or an error occurs:

1. **Analyze**: Read the stack trace and error message. Do not guess.
2. **Patch**: Fix the Python script in `tools/`.
3. **Test**: Verify the fix works.
4. **Update Architecture**: Update the corresponding `.md` file in `architecture/` with the new learning (e.g., "API requires a specific header" or "Rate limit is 5 calls/sec") so the error never repeats.

### 3. Deliverables vs. Intermediates

- **Local (`.tmp/`):** All scraped data, logs, and temporary files. These are ephemeral and can be deleted.
- **Global (Cloud):** The "Payload." Google Sheets, Databases, or UI updates. **A project is only "Complete" when the payload is in its final cloud destination.**

## 📂 File Structure Reference

Plaintext

`├── claude.md          # Project Map & State Tracking
├── .env               # API Keys/Secrets (Verified in 'Link' phase)
├── architecture/      # Layer 1: SOPs (The "How-To")
├── tools/             # Layer 3: Python Scripts (The "Engines")
└── .tmp/              # Temporary Workbench (Intermediates)`

# Mandatory Verification After Every Completion

// turbo-all

## When to Apply

**ALWAYS** — after EVERY change, fix, feature, or modification. No exceptions.

## The Rule

Before claiming ANY work is done:

1. **Identify** what command/test/browser check proves the change works
2. **Run** the verification command FRESH (not from memory or old output)
3. **Read** the FULL output — exit codes, error counts, actual behavior
4. **Report** actual results with evidence, not assumptions

## For multi-step flows

Verify EVERY step in the chain, not just the first one:
- Trigger → Processing → Response → Side effects → Final state
- A chain is only verified when the LAST step succeeds

## For bugs

Follow `/systematic-debugging` FIRST (find root cause before fixing), then verify the fix.

## Never say

- "Should work now"
- "Done!" (without evidence)
- "Fixed!" (without running the test)
- "All good" (without checking)

## Always say

- "Verified: [command output showing success]"
- "Test result: [actual output]"
- "Evidence: [screenshot/log/exit code]"

## EC2 / Server Operations

- **ALWAYS use SSH** (`ssh -i "key" ubuntu@host`) for EC2 operations. NEVER use browser-based Instance Connect or AWS Console terminal — it's slower, wastes tokens/context, and risks logging out of AWS.
- If SSH times out, retry 2-3 times before considering alternatives.
- Browser subagent is for **UI verification only** (testing the app), never for running server commands.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**VkusVill Sale Monitor**

A family-facing VkusVill discount aggregator that scrapes green/red/yellow price tags, sends Telegram notifications, and lets family members add products to their VkusVill cart without visiting the site. Deployed on AWS EC2 with Vercel frontend proxy at https://vkusvillsale.vercel.app/.

Users only go to VkusVill.ru to finalize delivery and pay.

**Core Value:** Family members see every VkusVill discount (green/red/yellow) the moment it appears, and can add items to their cart in one tap — without opening the VkusVill app or website.

### Constraints

- **Tech stack**: Python + React + nodriver — established, don't change
- **Platform**: VkusVill's anti-bot measures require CDP-native browser automation
- **Users**: Family only (up to 5 accounts + 1 technical)
- **Server**: t3.micro (1GB RAM) — Chrome uses ~233MB, must be careful with resources
- **SMS limits**: VkusVill allows max 4 SMS per day per phone — minimize live auth testing
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- **Python 3.11+** — Backend API, scrapers, scheduler, bot, database
- **JavaScript (ES2022+)** — React frontend (JSX), Vite build tooling
- **HTML/CSS** — Admin panel (`backend/admin.html`), frontend styles (`miniapp/src/index.css`)
## Runtime & Frameworks
### Backend (Python)
- **FastAPI** (`>=0.109.0`) — REST API server (`backend/main.py`, 153KB monolith)
- **Uvicorn** (`>=0.27.0`) — ASGI server
- **nodriver** (`>=0.38`) — Headless Chrome automation (replaced selenium/undetected-chromedriver)
- **httpx[socks]** (`>=0.27.0`) — HTTP client with SOCKS5 proxy support
- **python-telegram-bot** (`>=20.0`) — Telegram bot framework
- **APScheduler** (`>=3.10.0`) — Job scheduling (used in `main.py`)
- **aiosqlite** (`>=0.19.0`) — Async SQLite3 ORM
- **beautifulsoup4/lxml** — HTML parsing
- **python-dotenv** — Environment variable management
### Frontend (JavaScript)
- **React 19** — UI framework (`miniapp/src/`)
- **Vite 7** — Build tool and dev server
- **Framer Motion** — Animations
- No state management library (vanilla React useState/useEffect)
- No routing library (single-page app with conditional rendering)
## Infrastructure
- **EC2 Instance** — `13.60.174.46` (Stockholm region, MSK timezone)
- **systemd** — Process management (`saleapp-scheduler` service)
- **Vercel** — Frontend hosting for `miniapp/` (proxies API calls to EC2)
- **SQLite** — Local database (`database/sale_monitor.db`)
## Configuration
- `config.py` — Central config (Telegram token, VkusVill URLs, CSS selectors, category mappings)
- `.env` — Secrets (TELEGRAM_TOKEN, ADMIN_TOKEN)
- `miniapp/.env.local` — Frontend environment variables
- `miniapp/vercel.json` — Vercel rewrites (proxies `/api/*` and `/admin` to EC2)
- `ruff.toml` — Python linter config
- `pytest.ini` — Test config
## Dependencies (root `requirements.txt`)
## Key Technical Decisions
- **nodriver over Selenium** — Avoids detection by VkusVill's anti-bot systems
- **SOCKS5 proxy pool** — Managed by `proxy_manager.py` to rotate through free proxies
- **Cookie-based auth** — `login.py` saves VkusVill session cookies to `data/cookies.json`
- **JSON file interchange** — Scrapers write to `data/*.json`, backend reads them
- **Monolithic backend** — `backend/main.py` is 153KB single file handling all API routes
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Code Style
- **Python**: No strict formatter enforced; `ruff.toml` present but light config
- **JavaScript**: ESLint with React hooks plugin, no Prettier
- **Line length**: Not enforced (many 120+ char lines)
- **Encoding**: UTF-8 with Russian text (Cyrillic) in strings, comments, and log messages
## Naming
### Python
- **Functions**: `snake_case` (`scrape_green_prices`, `ensure_cart_not_empty`)
- **Constants**: `UPPER_SNAKE_CASE` (`SCRAPER_TIMEOUT`, `BASE_DIR`)
- **Private helpers**: `_underscore_prefix` (`_add_green_cards_to_cart`, `_log_script_output`)
- **Tags**: `TAG = "GREEN-ADD"` used for log filtering
### JavaScript
- **Components**: `PascalCase` (`CartPanel`, `ProductDetail`)
- **Functions/hooks**: `camelCase` (`handleSearch`, `fetchProducts`)
- **CSS classes**: BEM-like from VkusVill (`ProductCard__link`, `VV_TizersSection__Link`)
## Error Handling Pattern
### Scrapers (Python)
- All scrapers use try/except/finally with browser cleanup
- Failures logged with emoji prefixes: ❌ error, ⚠️ warning, ✅ success, 🔄 starting
- Exit code 0 even on partial failure (scheduler checks file mtime)
### Backend (FastAPI)
- Returns empty collections on error, never raises HTTP exceptions
## Logging
- **Scrapers**: `print()` with `[TAG]` prefix → captured by `scheduler_service.py`
- **Scheduler**: `log()` → writes to `logs/scheduler.log` with timestamp
- **Backend**: Standard FastAPI/uvicorn logging
- **No structured logging** (no JSON logs, no log levels)
- **Emoji-rich**: 🔄 ✅ ❌ ⚠️ ⏭️ used extensively in log messages
## Data Patterns
### Product JSON Shape
### File Save Pattern
## Async Patterns
- **Scrapers**: `async/await` with `nodriver` (`await js(page, "...")`)
- **Backend**: FastAPI async endpoints
- **Database**: `aiosqlite` async queries
- **Bot**: python-telegram-bot async handlers
- **Scheduler**: Synchronous `subprocess.run()` calling async scripts
## Configuration Pattern
- Centralized in `config.py` (categories, selectors, URLs)
- Secrets in `.env` loaded via `python-dotenv`
- No environment-based config switching (same config for dev/prod)
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## System Pattern
```
```
## Layers
### Layer 1: Scraping (Data Collection)
- **Entry points**: `scheduler_service.py` (main orchestrator)
- **Scrapers**: `scrape_red.py`, `scrape_yellow.py`, `scrape_green_add.py`, `scrape_green_data.py`
- **Shared code**: `green_common.py` (browser management, cookie loading, basket API)
- **Support**: `chrome_stealth.py`, `proxy_manager.py`, `utils.py`
- **Output**: JSON files in `data/`
### Layer 2: API Server
- **Entry point**: `backend/main.py` (monolith, 153KB)
- **Reads**: JSON files from `data/` directory
- **Provides**: REST API, WebSocket, admin dashboard
- **Auth**: Telegram HMAC signature verification, admin token
### Layer 3: Frontend
- **Entry point**: `miniapp/src/main.jsx` → `App.jsx`
- **Deployment**: Vercel (auto-deploy from git)
- **State**: React useState hooks, no external state management
- **Data fetching**: Fetch API with polling
### Layer 4: Bot
- **Entry point**: `bot/handlers.py`
- **Notifications**: `bot/notifier.py`, `backend/notifier.py`
- **Auth**: `bot/auth.py` (Telegram user verification)
## Data Flow
## Key Abstractions
- **Product object**: `{id, name, url, currentPrice, oldPrice, image, stock, unit, category, type}`
- **Scraper pattern**: Launch Chrome → load cookies → navigate → extract → save JSON → quit Chrome
- **Proxy rotation**: `proxy_manager.py` manages pool, scheduler retries with fresh proxy on failure
- **Stock cache**: `data/stock_cache.json` persists stock data across scraper failures
<!-- GSD:architecture-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
