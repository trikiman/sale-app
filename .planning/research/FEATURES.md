# Features Research: Bug Fix Scope

## Table Stakes (Must Fix — Security/Data Integrity)

| Bug | Category | Impact | Complexity |
|-----|----------|--------|------------|
| BUG-038 | IDOR favorites | Any user can read/modify any other user's favorites | Medium — add initData validation middleware |
| BUG-039 | IDOR cart | Any user can manipulate any other user's cart | Medium — same middleware as BUG-038 |
| BUG-044 | Notifications | Only first user gets notified of new products | Low — change "seen" marking to per-user |
| BUG-067 | Green scraper | Missing ~18 green items vs live site | High — VkusVill hides items, DOM vs API mismatch |
| BUG-068 | Stock data | Product shows stock=99 instead of real value | Medium — fix stock lookup condition |

## Important (Reliability/UX)

| Bug | Category | Impact | Complexity |
|-----|----------|--------|------------|
| BUG-046 | Merge race | "Run All" doesn't merge after scrapers finish | Low — add merge to run-all queue |
| BUG-053 | Category data | Product categories randomly flip between runs | Low — use first-write-wins |
| BUG-056 | Bot matching | Wrong category notifications sent | Medium — switch to exact match |
| UX-01 | Theme toggle | Light mode completely broken | Medium — audit all CSS variables |
| UX-02 | React keys | Console warnings, potential render bugs | Low — composite keys + dedup |

## Nice to Have (Polish)

| Bug | Category | Impact | Complexity |
|-----|----------|--------|------------|
| UX-03 | Cart UI | 0-quantity items stuck in list | Low — filter items with qty=0 |
| UX-04 | Admin UI | Scraper trigger stuck on 403 | Low — handle null response |
| UX-05 | Animations | Ghost empty state during transitions | Low — delay empty state render |

## Anti-Features (Don't Build)
- Full OAuth/SSO system — VkusVill only supports phone+SMS, overengineering
- Encrypted cookie storage — family app, adds complexity without proportional security gain
- Real-time collaborative features — single-family use case
