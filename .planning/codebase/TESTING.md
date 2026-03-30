# Testing

## Framework
- **Python**: `pytest` (with `pytest.ini` config)
- **JavaScript**: Vitest-compatible `.test.mjs` files (no explicit test runner config)
- **E2E/Browser**: None (manual verification via admin panel)

## Test Locations

### Backend (`backend/`)
| File | Coverage |
|------|----------|
| `test_api.py` | API endpoint responses |
| `test_admin_routes.py` | Admin dashboard routes |
| `test_auth.py` | Authentication logic |
| `test_categories.py` | Category normalization (most thorough, 11KB) |
| `test_cart_items_fallback.py` | Cart API fallback behavior |
| `test_login.py` | Login flow |
| `test_models.py` | Database models |
| `test_notifier.py` | Notification service |
| `test_product_details_fallback.py` | Product detail fallback |
| `test_validation.py` | Input validation |
| `test_lens.py` | Parse lens utility |

### Frontend (`miniapp/src/`)
| File | Coverage |
|------|----------|
| `categoryRunStatus.test.mjs` | Category status helpers |
| `productMeta.test.mjs` | Product metadata helpers |
| `detailDrawerStyles.test.mjs` | Detail drawer styling |

### Browser Tests (`miniapp/`)
| File | Coverage |
|------|----------|
| `test_ui.py` | Playwright-based UI tests |
| `test_verified_bugs.py` | Regression tests for fixed bugs |

## Test Commands
```bash
# Backend tests
cd backend && pytest -v

# Frontend tests (Vitest implied by .test.mjs)
cd miniapp && npx vitest run

# All Python tests from root
pytest
```

## Testing Patterns
- **No mocking framework** — tests use inline fixtures and fake data
- **No CI integration** — `.github/workflows/scrape.yml.disabled` (disabled)
- **Manual verification** — Admin panel at `/admin` shows scraper status, proxy health
- **Live verification** — Checking `vkusvillsale.vercel.app` after deployments

## Coverage Gaps
- No scraper tests (scrapers are integration-dependent on VkusVill live site)
- No scheduler tests
- No proxy manager tests
- No green_common.py tests
- No utils.py tests (despite being critical shared code)
- Frontend tests are minimal (3 small unit test files)
