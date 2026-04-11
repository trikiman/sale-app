# Architecture Research: Bug Fix Integration Points

## Component Map (Where Bugs Live)

```
┌─────────────────────────────────────────────────────────────┐
│                     FRONTEND (React/Vite)                    │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ App.jsx  │  │CartPanel │  │Login.jsx │  │index.css │   │
│  │ UX-02,05 │  │ UX-03    │  │          │  │ UX-01    │   │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘   │
└─────────────────────────┬───────────────────────────────────┘
                          │ /api/*
┌─────────────────────────▼───────────────────────────────────┐
│                  BACKEND (FastAPI)                            │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │  Favorites API   │  │   Cart API       │                 │
│  │  BUG-038 (IDOR)  │  │   BUG-039 (IDOR) │                 │
│  └──────────────────┘  └──────────────────┘                 │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │  Admin API       │  │  Auth API        │                 │
│  │  UX-04 (403 UI)  │  │                  │                 │
│  │  BUG-046 (merge) │  │                  │                 │
│  └──────────────────┘  └──────────────────┘                 │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    SCRAPERS                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │scrape_green  │  │scrape_red    │  │scrape_yellow │      │
│  │ BUG-067,068  │  │              │  │              │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │scrape_cats   │  │scrape_merge  │                         │
│  │ BUG-053      │  │              │                         │
│  └──────────────┘  └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                    TELEGRAM BOT                              │
│  ┌──────────────┐  ┌──────────────┐                         │
│  │ notifier.py  │  │ handlers.py  │                         │
│  │ BUG-044      │  │ BUG-056      │                         │
│  └──────────────┘  └──────────────┘                         │
└─────────────────────────────────────────────────────────────┘
```

## Dependency Graph (Build Order)

```
Phase 1: Security (IDOR) ──► No dependencies, can start immediately
  BUG-038, BUG-039 → Add initData validation middleware
  
Phase 2: Scraper fixes ──► Independent of Phase 1
  BUG-067, BUG-068 → Green scraper logic
  BUG-053 → Category scraper logic
  
Phase 3: Bot fixes ──► Independent
  BUG-044 → Notifier per-user seen tracking
  BUG-056 → Handler category matching
  
Phase 4: Frontend UX ──► Can run after IDOR fix (frontend may need header changes)
  UX-01 → CSS variables audit
  UX-02 → React key dedup
  UX-03, UX-04, UX-05 → Minor UI fixes

Phase 5: Backend logic ──► Independent
  BUG-046 → Merge race condition
```

## Data Flow Implications

### IDOR Fix (BUG-038/039) — Cross-Cutting
- Backend: New middleware/dependency for Telegram auth
- Frontend: Must send `initData` in request headers (currently sends `X-Telegram-User-Id`)
- Telegram MiniApp SDK provides `Telegram.WebApp.initData`
- Non-Telegram access (direct browser) falls back to existing guest ID system

### Green Scraper Fix (BUG-067) — Isolated
- Only touches `scrape_green.py`
- No API or frontend changes needed
- Output format stays the same (`green_products.json`)

### Theme Toggle Fix (UX-01) — Frontend Only
- Only CSS changes in `index.css` 
- No backend or data flow changes
- Need to audit every component for hardcoded colors
