# SOCKS5 Proxy Manager (Legacy)

This is the v1.0–v1.14 proxy implementation. It fetched free SOCKS5 proxies
from public lists (primarily `proxifly/free-proxy-list`), tested them against
vkusvill.ru, and served working ones to the scraper and cart clients.

## Why It Was Retired

- Free SOCKS5 pool reliability collapsed — 0% alive on 2026-04-22 across
  269 tested nodes (see `.cache/alive_ru_proxies.json`).
- Add-to-cart and green-scraper failures were traced to pool exhaustion,
  not to cart or scraper logic bugs.
- Replacement: VLESS+Reality pool with daily refresh, tunneled through a
  local xray-core SOCKS5 bridge (`vless/manager.py`).

## Public API (preserved by VLESS replacement)

See `proxy_manager.py` for the full method list. The VLESS replacement in
`vless/manager.py` reproduces every public method with compatible
signatures — callers do not need changes.

## Data Files Used (no longer read)

- `data/working_proxies.json` — SOCKS5 pool cache (unused after migration)
- `data/proxy_events.jsonl` — event log (schema preserved; VLESS manager
  writes to the same file)
- `.cache/vkusvill_cooldowns.json` — 4h cooldown cache (schema and file
  path preserved; VLESS manager uses the same cache)

## Running the Archived Tests

The archived test suite (`tests/test_proxy_manager.py`) verifies the SOCKS5
internals (`_socks5_preflight`, `_test_proxy`, refresh timeout handling).
A local `conftest.py` inserts this directory on ``sys.path`` so the tests
import the archived ``proxy_manager`` module, not the production shim:

    pytest legacy/proxy-socks5/tests -v

## If You Need This Code Back

Use `git revert` on the archive commit — do not copy-paste back. See
`../README.md` for the exact rollback procedure.
