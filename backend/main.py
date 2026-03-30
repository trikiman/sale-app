"""
FastAPI Backend for VkusVill Mini App
Serves product data, handles favorites, and provides admin panel
"""
# CRITICAL: Set ProactorEventLoop BEFORE any async code.
# uvicorn --reload spawns child processes that need this policy to
# spawn Chrome subprocess via nodriver. Must be in main.py, NOT just run.py.
import sys as _sys
if _sys.platform == 'win32':
    import asyncio as _asyncio
    _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())

# CRITICAL FIX: Monkey-patch nodriver's Cookie.from_json() to handle Chrome removing
# the 'sameParty' field from CDP responses. Without this, browser.cookies.get_all()
# hangs forever because nodriver's internal KeyError is swallowed by its event listener.
try:
    import nodriver.cdp.network as _cdn
    _original_cookie_from_json = _cdn.Cookie.from_json

    @classmethod
    def _patched_cookie_from_json(cls, json_data):
        if 'sameParty' not in json_data:
            json_data['sameParty'] = False
        return _original_cookie_from_json.__func__(cls, json_data)

    _cdn.Cookie.from_json = _patched_cookie_from_json
except Exception:
    pass  # nodriver not installed or different version
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import hashlib
import hmac
import time as _time
from collections import deque
from datetime import datetime
import json
import os
import sys

# Windows: asyncio.create_subprocess_exec() requires ProactorEventLoop.
# uvicorn --reload forces SelectorEventLoop which can't spawn subprocesses.
if sys.platform == 'win32':
    import asyncio as _asyncio
    _asyncio.set_event_loop_policy(_asyncio.WindowsProactorEventLoopPolicy())
    # BUG-027: Fix UnicodeEncodeError on Windows console
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except (AttributeError, Exception):
        pass

import subprocess
import threading
import logging

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database
# PlaywrightScraper removed — migrated to nodriver
from cart.vkusvill_api import VkusVillCart
from bot.auth import get_user_cookies_path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(os.path.join(os.path.dirname(__file__), "backend_test.log"), encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Load admin token from config / env
# Load admin token from config / env
try:
    from config import ADMIN_TOKEN
except Exception:
    ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")
if not ADMIN_TOKEN:
    logger.warning("ADMIN_TOKEN not set! Admin endpoints will reject all requests.")

# Load Telegram bot token for initData HMAC validation (BUG-038/039)
try:
    from config import TELEGRAM_TOKEN
except Exception:
    TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
if not TELEGRAM_TOKEN:
    logger.warning("TELEGRAM_TOKEN not set! Telegram initData validation will be disabled.")

app = FastAPI(title="VkusVill Mini App API", version="1.0.0")

# CORS for mini app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
        "https://web.telegram.org",
        "https://vkusvill-proxy.vercel.app",
        "https://vkusvillsale.vercel.app",
        os.environ.get("WEB_APP_ORIGIN", "https://t.me"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["Content-Type", "X-Admin-Token", "Authorization"],
)

# Initialize database
db = Database()

# Data paths
BASE_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_PROJECT_DIR, "data")
PROPOSALS_PATH = os.path.join(DATA_DIR, "proposals.json")
MINIAPP_DIST = os.path.join(BASE_PROJECT_DIR, "miniapp", "dist")
TECH_PROFILE_DIR = os.path.join(DATA_DIR, "tech_profile")
VKUSVILL_BACKOFF_SECONDS = 60
_vkusvill_backoff_until = 0.0

# Mount assets directory if it exists
assets_dir = os.path.join(MINIAPP_DIST, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# ─── Scraper State ────────────────────────────────────────────────────────────

scraper_status: dict = {
    "green":      {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "red":        {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "yellow":     {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "merge":      {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "login":      {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "categories": {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
}

log_buffer: deque = deque(maxlen=1000)
_scraper_processes: dict = {}

# Per-name locks — prevent two simultaneous requests launching the same scraper twice
_run_locks: dict = {
    name: threading.Lock()
    for name in ["green", "red", "yellow", "merge", "login", "categories"]
}
_phone_map_lock = threading.Lock()  # R2-9: File lock for user_phone_map.json

# Per-user login sessions: {user_id: {"driver": uc.Chrome, "created_at": float}}
_login_sessions: dict = {}
_LOGIN_TTL_SECONDS = 600  # 10 minutes max for login flow

# Async login jobs: {job_id: {status, message, result, user_id, created_at}}
_login_jobs: dict = {}
_LOGIN_JOB_TTL = 600  # 10 minutes

# Async verify jobs: {job_id: {status, message, result, user_id, created_at}}
_verify_jobs: dict = {}
_VERIFY_JOB_TTL = 300  # 5 minutes

# R2-3: In-memory login rate limiter: {phone_10: [timestamps]}
_login_attempts: dict = {}
_LOGIN_RATE_LIMIT = 3  # max attempts per phone
_LOGIN_RATE_WINDOW = 600  # within 10 minutes


def _run_script(name: str, script_path: str):
    """Run a Python script in a background thread, capturing output.
    Uses a per-name lock so the check+set of 'running' is atomic.
    """
    lock = _run_locks.get(name)
    if lock is None:
        logger.warning(f"No lock registered for scraper '{name}', skipping")
        return
    with lock:
        if scraper_status[name]["running"]:
            log_buffer.append(f"[{name}] Already running, skipping.")
            return
        # Atomic: mark running while still holding the lock
        scraper_status[name]["running"] = True
        scraper_status[name]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        scraper_status[name]["last_output"] = ""

    lines: list = []  # capped at 5000 lines to prevent memory issues

    def worker():
        try:
            proc = subprocess.Popen(
                [sys.executable, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                cwd=BASE_PROJECT_DIR,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONPATH": BASE_PROJECT_DIR},  # R2-17
            )
            _scraper_processes[name] = proc
            for line in proc.stdout:
                line = line.rstrip()
                lines.append(line)
                log_buffer.append(f"[{name}] {line}")
            proc.wait()
            scraper_status[name]["exit_code"] = proc.returncode
            status_emoji = "OK" if proc.returncode == 0 else "ERR"
            log_buffer.append(f"[{name}] {status_emoji} Finished (exit {proc.returncode})")
        except Exception as exc:
            log_buffer.append(f"[{name}] Exception: {exc}")
            scraper_status[name]["exit_code"] = -1
        finally:
            scraper_status[name]["running"] = False
            scraper_status[name]["last_output"] = "\n".join(lines[-40:])
            _scraper_processes.pop(name, None)
            # Cap lines to prevent unbounded memory growth
            if len(lines) > 5000:
                lines[:] = lines[-1000:]

    threading.Thread(target=worker, daemon=True).start()


def _copy_tech_profile(src_dir: str, dst_dir: str = TECH_PROFILE_DIR):
    if not src_dir or not os.path.isdir(src_dir):
        return False

    import shutil

    if os.path.exists(dst_dir):
        shutil.rmtree(dst_dir, ignore_errors=True)
    shutil.copytree(src_dir, dst_dir)
    return True


def _cleanup_debug_screenshots():
    """R2-4: Remove login debug screenshots older than 1 hour."""
    try:
        max_age = 3600  # 1 hour
        now = _time.time()
        for fname in os.listdir(DATA_DIR):
            if fname.startswith("login_") and fname.endswith(".png"):
                fpath = os.path.join(DATA_DIR, fname)
                if now - os.path.getmtime(fpath) > max_age:
                    try:
                        os.remove(fpath)
                    except Exception:
                        pass
    except Exception:
        pass


def _cleanup_temp_profile_dirs():
    """R2-5: Remove orphaned Chrome temp profile directories."""
    import tempfile
    import shutil
    try:
        tmp_dir = tempfile.gettempdir()
        now = _time.time()
        for entry in os.listdir(tmp_dir):
            if entry.startswith("uc_"):
                full = os.path.join(tmp_dir, entry)
                if os.path.isdir(full) and now - os.path.getmtime(full) > 3600:
                    try:
                        shutil.rmtree(full, ignore_errors=True)
                    except Exception:
                        pass
    except Exception:
        pass


def _periodic_cleanup():
    """R2-23/44: Background timer to clean stale login sessions and temp files."""
    while True:
        _time.sleep(300)  # Every 5 minutes
        _evict_stale_login_sessions()
        _cleanup_debug_screenshots()
        _cleanup_temp_profile_dirs()

# Start periodic cleanup on import
threading.Thread(target=_periodic_cleanup, daemon=True).start()

def _require_token(token: Optional[str]):
    if not ADMIN_TOKEN or not token or not hmac.compare_digest(token, ADMIN_TOKEN):
        logger.warning("Admin auth failed: token mismatch")
        raise HTTPException(status_code=403, detail="Invalid admin token")


def validate_telegram_init_data(init_data: str, bot_token: str) -> dict | None:
    """Validate Telegram MiniApp initData using HMAC-SHA256.
    Returns parsed user dict if valid, None if invalid.
    See: https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
    """
    from urllib.parse import parse_qsl
    try:
        params = dict(parse_qsl(init_data, keep_blank_values=True))
        received_hash = params.pop('hash', '')
        if not received_hash:
            return None

        # Check auth_date freshness (reject if > 5 min old)
        auth_date = int(params.get('auth_date', '0'))
        if abs(_time.time() - auth_date) > 300:
            return None

        # Sort and create data_check_string
        sorted_params = sorted(params.items())
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_params)

        # HMAC chain: WebAppData -> bot_token -> data_check_string
        secret_key = hmac.new(
            key=b"WebAppData",
            msg=bot_token.encode(),
            digestmod=hashlib.sha256
        ).digest()

        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode(),
            digestmod=hashlib.sha256
        ).hexdigest()

        if not hmac.compare_digest(calculated_hash, received_hash):
            return None

        # Parse user JSON from params
        user_json = params.get('user', '{}')
        user = json.loads(user_json)
        return user
    except Exception:
        return None


def _validate_user_header(request: Request, expected_user_id: str):
    """BUG-038/039: IDOR protection with dual auth paths.

    Path 1 (Telegram MiniApp): Validate initData HMAC signature.
    Path 2 (Guest/Browser): Fall back to X-Telegram-User-Id header match.

    Either path must confirm the request is from the claimed user.
    """
    # Path 1: Try Telegram initData (cryptographic proof)
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("tma "):
        init_data = auth_header[4:]  # Strip "tma " prefix
        if not TELEGRAM_TOKEN:
            logger.warning("initData received but TELEGRAM_TOKEN not configured")
            raise HTTPException(status_code=500, detail="Server auth not configured")
        user = validate_telegram_init_data(init_data, TELEGRAM_TOKEN)
        if user and str(user.get("id", "")) == str(expected_user_id):
            return  # Valid Telegram user, authorized
        # initData provided but invalid or user mismatch
        raise HTTPException(status_code=403, detail="Invalid Telegram authorization")

    # Path 2: Fallback to header check (guest/browser users)
    header_uid = request.headers.get("x-telegram-user-id", "")
    if not header_uid or str(header_uid) != str(expected_user_id):
        raise HTTPException(status_code=403, detail="User ID mismatch")


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class Product(BaseModel):
    id: str
    name: str
    url: str
    currentPrice: str
    oldPrice: str
    image: str
    stock: float
    unit: str
    category: str
    type: str  # green, red, yellow


class ProductsResponse(BaseModel):
    updatedAt: str
    greenLiveCount: Optional[int] = 0
    greenMissing: Optional[bool] = False
    dataStale: Optional[bool] = False
    staleInfo: Optional[List[str]] = None
    products: List[Product]


class FavoriteRequest(BaseModel):
    product_id: str
    product_name: str


class FavoriteResponse(BaseModel):
    product_id: str
    product_name: str
    is_favorite: bool

class CartAddRequest(BaseModel):
    user_id: str
    product_id: int
    is_green: int = 0
    price_type: int = 1


# ─── Public Endpoints ─────────────────────────────────────────────────────────

@app.get("/")
def root():
    index_path = os.path.join(MINIAPP_DIST, "index.html")
    if os.path.exists(index_path):
        return FileResponse(
            index_path,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    return {"status": "ok", "message": "VkusVill Mini App API (Frontend not built yet)"}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    vite_svg = os.path.join(MINIAPP_DIST, "vite.svg")
    if os.path.exists(vite_svg):
        return FileResponse(vite_svg)
    return HTMLResponse(status_code=404)


def _load_product_record(product_id: str) -> Optional[dict]:
    proposals_path = os.path.join(DATA_DIR, "proposals.json")
    try:
        with open(proposals_path, encoding='utf-8') as f:
            data = json.load(f)
    except Exception:
        return None

    for product in data.get('products', []):
        if str(product.get('id')) == str(product_id):
            return product
    return None


def _fallback_product_details(product_id: str, product: Optional[dict], reason: str = "") -> dict:
    image = ""
    weight = ""
    if product:
        image = str(product.get("image") or "").strip()
        weight = str(product.get("weight") or "").strip()

    images = [image] if image else []
    return {
        "id": product_id,
        "weight": weight,
        "description": "",
        "shelf_life": "",
        "storage": "",
        "composition": "",
        "nutrition": "",
        "images": images,
        "source_unavailable": True,
        "source_error": reason,
    }


def _fallback_cart_items(reason: str = "") -> dict:
    return {
        "items_count": 0,
        "total_price": 0,
        "items": [],
        "source_unavailable": True,
        "source_error": reason,
    }


def _mark_vkusvill_backoff():
    global _vkusvill_backoff_until
    _vkusvill_backoff_until = _time.time() + VKUSVILL_BACKOFF_SECONDS


def _vkusvill_backoff_active() -> bool:
    return _time.time() < _vkusvill_backoff_until

@app.get("/api/product/{product_id}/details")
async def product_details(product_id: str):
    """Fetch full product details from VkusVill product page (on-demand)."""
    import re
    from backend import detail_service

    product = _load_product_record(product_id)
    url = product.get('url', '') if product else ''

    if not url:
        raise HTTPException(status_code=404, detail="Product not found")

    # Check cache first — instant return
    cached = detail_service.read_cache(product_id)
    if cached:
        return cached

    # Fetch HTML via direct HTTP (fast: ~2-3s) — VkusVill pages are server-rendered
    html = None
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"

    # Try direct connection first
    try:
        import httpx
        async with httpx.AsyncClient(timeout=4, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml",
            })
            if resp.status_code == 200 and len(resp.text) > 500:
                html = resp.text
                logger.info(f"Product {product_id}: fetched {len(html)} bytes via direct in {resp.elapsed.total_seconds():.1f}s")
    except Exception as e:
        logger.warning(f"Product {product_id}: direct HTTP failed ({e})")

    # If direct failed, use ProxyManager with smart retry
    # Strategy: 1s HEAD check per proxy → first that passes → full fetch (5s)
    # ConnectError → proxy dead → remove. Timeout → VkusVill slow → keep proxy.
    if not html:
        try:
            import sys, httpx
            if os.path.dirname(os.path.dirname(__file__)) not in sys.path:
                sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
            from proxy_manager import ProxyManager
            pm = ProxyManager(log_func=lambda msg: logger.info(f"[PROXY] {msg}"))

            # Get all proxies in pool
            pool = pm._cache.get("proxies", [])
            if not pool:
                pm.ensure_pool()
                pool = pm._cache.get("proxies", [])

            dead_proxies = []
            working_proxy = None

            # Phase 1: Quick 1s HEAD check to find a live proxy
            for entry in pool:
                addr = entry["addr"]
                proxy_url = f"socks5://{addr}"
                try:
                    async with httpx.AsyncClient(
                        timeout=httpx.Timeout(connect=1.0, read=1.0, write=1.0, pool=1.0),
                        proxy=proxy_url
                    ) as client:
                        await client.head("https://vkusvill.ru/", headers={"User-Agent": ua})
                    # HEAD succeeded — this proxy is alive
                    working_proxy = addr
                    logger.info(f"Product {product_id}: proxy {addr} passed 1s health check")
                    break
                except httpx.ConnectError:
                    # Proxy is dead — can't even connect
                    logger.info(f"Product {product_id}: proxy {addr} dead (ConnectError)")
                    dead_proxies.append(addr)
                except httpx.TimeoutException:
                    # Connected but VkusVill slow — proxy might be fine, skip to next
                    logger.info(f"Product {product_id}: proxy {addr} timeout (VkusVill slow?), trying next")
                except Exception:
                    # Other error — skip but don't remove
                    logger.info(f"Product {product_id}: proxy {addr} check failed, trying next")

            # Remove confirmed dead proxies
            for addr in dead_proxies:
                pm.remove_proxy(addr)

            # Phase 2: If we found a working proxy, do the full page fetch
            if working_proxy:
                proxy_url = f"socks5://{working_proxy}"
                try:
                    async with httpx.AsyncClient(
                        timeout=httpx.Timeout(connect=3.0, read=5.0, write=3.0, pool=3.0),
                        follow_redirects=True, proxy=proxy_url
                    ) as client:
                        resp = await client.get(url, headers={
                            "User-Agent": ua,
                            "Accept": "text/html,application/xhtml+xml",
                        })
                        if resp.status_code == 200 and len(resp.text) > 500:
                            html = resp.text
                            logger.info(f"Product {product_id}: fetched {len(html)} bytes via proxy {working_proxy} in {resp.elapsed.total_seconds():.1f}s")
                        else:
                            logger.warning(f"Product {product_id}: proxy {working_proxy} returned status {resp.status_code}")
                except httpx.ConnectError:
                    pm.remove_proxy(working_proxy)
                    logger.warning(f"Product {product_id}: proxy {working_proxy} died during fetch")
                except Exception as e:
                    logger.warning(f"Product {product_id}: fetch via {working_proxy} failed ({e})")
            else:
                if dead_proxies:
                    logger.info(f"Product {product_id}: removed {len(dead_proxies)} dead proxies, none working")
                else:
                    logger.info(f"Product {product_id}: all proxies timed out — VkusVill may be down")
        except ImportError:
            logger.warning(f"Product {product_id}: proxy_manager not available")

    if not html:
        logger.info(f"Product {product_id}: all attempts failed, returning fallback")
        return _fallback_product_details(product_id, product, "HTTP fetch failed (direct blocked, proxy unavailable)")

    if not html or len(html) < 500:
        return _fallback_product_details(product_id, product, "Empty HTML response")

    def strip_tags(s):
        return re.sub(r'<[^>]+>', ' ', s or '').replace('&nbsp;', ' ').replace('&amp;', '&').strip()
    def clean(s):
        return re.sub(r'\s+', ' ', strip_tags(s)).strip()

    # Weight
    m = re.search(r'ProductCard__weight[^>]*>([^<]+)', html)
    weight = m.group(1).strip() if m else ''

    # Description
    m = re.search(r'VV23_DetailProdPageInfoDescItem__Desc[^>]*>([\s\S]{10,2000}?)</div>', html)
    description = clean(m.group(1)) if m else ''

    # Shelf life
    m = re.search(r'Годен\s*</[^>]+>\s*<[^>]+>([^<]+)', html)
    shelf_life = m.group(1).strip() if m else ''

    # Storage
    m = re.search(r'Условия хранения\s*</[^>]+>\s*<[^>]+>([^<]{5,150})', html)
    storage = clean(m.group(1)) if m else ''

    # Accordion sections (Состав, Питание и энергетическая ценность, etc.)
    sections = {}
    for title, body in re.findall(
        r'Accordion__Title[^>]*>([\s\S]{1,120}?)</[a-z]+>[\s\S]{0,400}?Accordion__BodyInner[^>]*>([\s\S]{10,1500}?)</div>\s*</div>\s*</div>\s*</div>',
        html
    ):
        t = clean(title)
        b = clean(body)
        if t and b:
            sections[t] = b

    composition = sections.get('Состав', '')
    nutrition = sections.get('Пищевая и энергетическая ценность', '') or sections.get('Питание', '')

    # Full-size gallery images — extract unique images from HTML, keep EXACT URLs
    # Do NOT construct URLs (e.g. force site_BigWebP) because many UUIDs don't exist
    # in that format (confirmed: 2/3 tested UUIDs return 404 on site_BigWebP)
    all_img_urls = re.findall(
        r'https://img\.vkusvill\.ru/pim/images/[^\s"\'?]+',
        html
    )
    seen_uuids = set()
    imgs = []
    for img_url in all_img_urls:
        m = re.search(r'([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.\w+)', img_url)
        if not m:
            continue
        uuid_file = m.group(1)
        uuid_part = uuid_file.split('.')[0]
        if uuid_part in seen_uuids:
            continue
        seen_uuids.add(uuid_part)
        # Keep the original URL as-is (strip query params only)
        clean_url = img_url.split('?')[0]
        imgs.append(clean_url)

    result = {
        "id": product_id,
        "weight": weight,
        "description": description,
        "shelf_life": shelf_life,
        "storage": storage,
        "composition": composition,
        "nutrition": nutrition,
        "images": imgs,
    }

    # Cache for next time
    detail_service.write_cache(product_id, result)

    return result


# In-memory image cache: {url: (content_bytes, content_type, timestamp)}
_img_cache: dict = {}
_IMG_CACHE_MAX = 200
_IMG_CACHE_TTL = 3600  # 1 hour


@app.get("/api/img")
async def proxy_image(url: str = ""):
    """Proxy VkusVill images with in-memory caching."""
    import httpx
    from urllib.parse import urlparse
    if not url:
        raise HTTPException(status_code=400, detail="Missing url parameter")
    parsed = urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith("vkusvill.ru"):
        raise HTTPException(status_code=400, detail="Invalid image URL")
    # Check in-memory cache
    now = _time.time()
    cached = _img_cache.get(url)
    if cached and (now - cached[2]) < _IMG_CACHE_TTL:
        return Response(
            content=cached[0],
            media_type=cached[1],
            headers={"Cache-Control": "public, max-age=86400", "X-Cache": "HIT"},
        )
    try:
        _proxy = os.environ.get("SOCKS_PROXY", "")
        client_kwargs: dict = {"timeout": 10}
        if _proxy:
            client_kwargs["proxy"] = _proxy
        async with httpx.AsyncClient(**client_kwargs) as client:
            resp = await client.get(url, headers={
                "Referer": "https://vkusvill.ru/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="Image fetch failed")
            ct = resp.headers.get("content-type", "image/webp")
            content = resp.content
            # Store in cache (evict oldest if full)
            if len(_img_cache) >= _IMG_CACHE_MAX:
                oldest_key = min(_img_cache, key=lambda k: _img_cache[k][2])
                del _img_cache[oldest_key]
            _img_cache[url] = (content, ct, now)
            return Response(
                content=content,
                media_type=ct,
                headers={"Cache-Control": "public, max-age=86400", "X-Cache": "MISS"},
            )
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Image fetch timeout")
    except Exception as e:
        raise HTTPException(status_code=502, detail=str(e))


# BUG-S02: Basic client log rate limiter
_client_log_counts: dict = {}  # ip -> (count, window_start)
_CLIENT_LOG_LIMIT = 30  # max logs per minute per IP

@app.post("/api/log")
def client_log(request: Request, payload: dict = Body(default={})):
    """Receive client-side error logs from the miniapp."""
    client_ip = request.client.host if request.client else "unknown"
    now = _time.time()
    entry = _client_log_counts.get(client_ip, (0, now))
    if now - entry[1] > 60:
        _client_log_counts[client_ip] = (1, now)
    else:
        if entry[0] >= _CLIENT_LOG_LIMIT:
            return {"ok": False, "throttled": True}
        _client_log_counts[client_ip] = (entry[0] + 1, entry[1])
    ua = payload.get("ua", "")[:120]
    msg = payload.get("msg", "")[:500]
    level = payload.get("level", "info")[:10]
    logger.info(f"[CLIENT-{level.upper()}] {msg} | UA: {ua}")
    return {"ok": True}

@app.get("/api/products", response_model=ProductsResponse)
def get_products():
    """Get all products from proposals.json, with live staleness check."""
    try:
        if not os.path.exists(PROPOSALS_PATH):
            raise HTTPException(status_code=404, detail="Products data not found")
        # R2-38: Catch partial reads from concurrent writes
        for attempt in range(2):
            try:
                with open(PROPOSALS_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                break
            except json.JSONDecodeError:
                if attempt == 0:
                    import time
                    time.sleep(0.5)  # Retry once after brief pause
                else:
                    raise HTTPException(status_code=500, detail="Invalid JSON data")
        # Live staleness: check source file ages at request time (not baked merge-time value)
        STALE_MINUTES = 10
        stale_files = []
        latest_mtime = 0
        for color in ('green', 'red', 'yellow'):
            src = os.path.join(DATA_DIR, f"{color}_products.json")
            if os.path.exists(src):
                mtime = os.path.getmtime(src)
                latest_mtime = max(latest_mtime, mtime)
                age_min = (_time.time() - mtime) / 60
                if age_min > STALE_MINUTES:
                    stale_files.append(f"{color} ({age_min:.0f}m)")
        data["dataStale"] = len(stale_files) > 0
        data["staleInfo"] = stale_files if stale_files else None
        # Override baked updatedAt with the most recent source file mtime
        if latest_mtime > 0:
            from datetime import datetime, timezone, timedelta
            _msk = timezone(timedelta(hours=3))  # Moscow timezone
            data["updatedAt"] = datetime.fromtimestamp(latest_mtime, tz=_msk).strftime("%Y-%m-%d %H:%M:%S")
        # Live greenMissing check (BUG-066: also check empty products, not just file existence)
        green_path = os.path.join(DATA_DIR, "green_products.json")
        if not os.path.exists(green_path):
            data["greenMissing"] = True
        else:
            try:
                with open(green_path, "r", encoding="utf-8") as _gf:
                    _gdata = json.load(_gf)
                _gprods = _gdata.get("products", _gdata) if isinstance(_gdata, dict) else _gdata
                data["greenMissing"] = len(_gprods) == 0
            except Exception:
                data["greenMissing"] = True
        return data
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON data")


@app.get("/api/stream")
async def stream_updates():
    """SSE endpoint for live UI updates. Broadcasts 'update' when proposals.json changes."""
    import asyncio
    async def event_generator():
        last_mtime = 0
        ping_counter = 0
        if os.path.exists(PROPOSALS_PATH):
            last_mtime = os.path.getmtime(PROPOSALS_PATH)
            
        try:
            while True:
                await asyncio.sleep(2)  # Check every 2 seconds
                ping_counter += 1
                if os.path.exists(PROPOSALS_PATH):
                    current_mtime = os.path.getmtime(PROPOSALS_PATH)
                    if current_mtime > last_mtime:
                        last_mtime = current_mtime
                        yield "event: update\ndata: {}\n\n"
                        ping_counter = 0
                # BUG-L10: Send keepalive every ~30s to prevent proxy/ALB timeout
                if ping_counter >= 15:
                    yield ": keepalive\n\n"
                    ping_counter = 0
        except asyncio.CancelledError:
            pass  # Client disconnected, clean exit
        except GeneratorExit:
            pass  # Client disconnected, clean exit

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/favorites/{user_id}")
def get_favorites(user_id: str, request: Request):
    _validate_user_header(request, user_id)
    favorites = db.get_user_favorite_products(user_id)
    return {
        "user_id": user_id,
        "favorites": [{"product_id": f.product_id, "product_name": f.product_name} for f in favorites],
    }


@app.post("/api/favorites/{user_id}", response_model=FavoriteResponse)
def toggle_favorite(user_id: str, request: FavoriteRequest, raw_request: Request):
    _validate_user_header(raw_request, user_id)
    # Only upsert for numeric Telegram IDs, not guest string IDs
    if user_id.isdigit():
        db.upsert_user(int(user_id))
    favorites = db.get_user_favorite_products(user_id)
    is_favorited = any(f.product_id == request.product_id for f in favorites)
    if is_favorited:
        db.remove_favorite_product(user_id, request.product_id)
        return FavoriteResponse(product_id=request.product_id, product_name=request.product_name, is_favorite=False)
    else:
        db.add_favorite_product(user_id, request.product_id, request.product_name)
        return FavoriteResponse(product_id=request.product_id, product_name=request.product_name, is_favorite=True)


@app.delete("/api/favorites/{user_id}/{product_id}")
def remove_favorite(user_id: str, product_id: str, request: Request):
    _validate_user_header(request, user_id)
    success = db.remove_favorite_product(user_id, product_id)
    return {"success": success, "product_id": product_id}


# ── Telegram Account Linking ──────────────────────────────────────

BOT_USERNAME = "green_price_monitor_bot"

class LinkRequest(BaseModel):
    guest_id: str

@app.post("/api/link/generate")
def generate_link(req: LinkRequest):
    """Generate a Telegram deep link token for account linking."""
    if not req.guest_id or not req.guest_id.startswith("guest_"):
        raise HTTPException(400, "Invalid guest ID")
    token = db.store_link_token(req.guest_id)
    link = f"https://t.me/{BOT_USERNAME}?start=link_{token}"
    return {"token": token, "link": link}

@app.get("/api/link/status/{guest_id}")
def link_status(guest_id: str):
    """Check if a guest account has been linked to Telegram."""
    telegram_id = db.get_linked_telegram_id(guest_id)
    return {"linked": telegram_id is not None, "telegram_id": telegram_id}


@app.post("/api/sync")
def sync_products():
    try:
        if not os.path.exists(PROPOSALS_PATH):
            return {"success": False, "message": "No products file found"}
        with open(PROPOSALS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        products = data.get("products", [])
        new_count = sum(1 for p in products if p.get("id") and db.mark_product_seen(p["id"]))
        return {"success": True, "total_products": len(products), "new_products": new_count}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/api/new-products")
def get_new_products():
    try:
        if not os.path.exists(PROPOSALS_PATH):
            return {"new_products": []}
        with open(PROPOSALS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        products = data.get("products", [])
        new_ids = db.get_new_products([p["id"] for p in products])
        new_products = [p for p in products if p["id"] in new_ids]
        return {"new_products": new_products, "count": len(new_products)}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ─── Auth Endpoints ───────────────────────────────────────────────────────────

# ─── Phone-keyed Auth Storage ─────────────────────────────────────────────────

def _phone_auth_dir(phone_10: str) -> str:
    """Return `data/auth/{phone}/` directory path."""
    d = os.path.join(DATA_DIR, "auth", phone_10)
    os.makedirs(d, exist_ok=True)
    return d

def _load_pin_data(phone_10: str) -> dict | None:
    """Load PIN data for a phone, or None."""
    p = os.path.join(_phone_auth_dir(phone_10), "pin.json")
    if not os.path.exists(p):
        return None
    try:
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return None

def _save_pin_data(phone_10: str, pin: str, user_id: str):
    """Save PIN data for a phone."""
    p = os.path.join(_phone_auth_dir(phone_10), "pin.json")
    data = {
        "pin_hash": hashlib.sha256((pin + phone_10).encode()).hexdigest(),  # R2-6: Salted with phone
        "user_id": user_id,
        "created_at": _time.time(),
        "attempts": 0,
        "locked_until": 0,
    }
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

def _phone_cookies_path(phone_10: str) -> str:
    return os.path.join(_phone_auth_dir(phone_10), "cookies.json")

def _phone_has_valid_cookies(phone_10: str) -> bool:
    cp = _phone_cookies_path(phone_10)
    return os.path.exists(cp)

def _save_user_phone_mapping(user_id: str, phone_10: str):
    """Map user_id → phone so cart can find cookies."""
    p = os.path.join(DATA_DIR, "auth", "user_phone_map.json")
    with _phone_map_lock:
        mapping = {}
        if os.path.exists(p):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    mapping = json.load(f)
            except Exception:
                pass
        mapping[str(user_id)] = phone_10
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(mapping, f, indent=2)

def _get_phone_for_user(user_id: str) -> str | None:
    """Get phone for a user_id from the mapping."""
    p = os.path.join(DATA_DIR, "auth", "user_phone_map.json")
    with _phone_map_lock:  # BUG-L09: prevent TOCTOU race with writer
        if not os.path.exists(p):
            return None
        try:
            with open(p, 'r', encoding='utf-8') as f:
                mapping = json.load(f)
            return mapping.get(str(user_id))
        except Exception:
            return None

def _normalize_phone(phone: str) -> str | None:
    """Normalize phone to 10-digit format."""
    phone = phone.strip()
    for ch in (' ', '-', '(', ')'):
        phone = phone.replace(ch, '')
    if phone.startswith('+7') and len(phone) == 12:
        phone = phone[2:]
    elif phone.startswith('8') and len(phone) == 11:
        phone = phone[1:]
    elif phone.startswith('7') and len(phone) == 11:
        phone = phone[1:]
    if len(phone) == 10 and phone.isdigit():
        return phone
    return None


@app.get("/api/auth/status/{user_id}")
def auth_status(user_id: str):
    """Check if the user is authenticated (has cookies via phone mapping)."""
    phone = _get_phone_for_user(user_id)
    if not phone or not _phone_has_valid_cookies(phone):
        return {"authenticated": False}
    masked = f"***-***-{phone[-4:-2]}-{phone[-2:]}" if len(phone) >= 4 else "***"
    has_pin = _load_pin_data(phone) is not None  # BUG-L08: report PIN state
    return {"authenticated": True, "phone": masked, "has_pin": has_pin}


class AuthPhoneRequest(BaseModel):
    user_id: str
    phone: str
    force_sms: bool = False  # "Новый вход" checkbox


class AuthCodeRequest(BaseModel):
    user_id: str
    code: str


class AuthPinRequest(BaseModel):
    user_id: str
    phone: str
    pin: str


class AuthSetPinRequest(BaseModel):
    user_id: str
    phone: str
    pin: str


class AuthLogoutRequest(BaseModel):
    user_id: str


class AuthCaptchaRequest(BaseModel):
    user_id: str
    captcha_answer: str


class TechLoginRequest(BaseModel):
    phone: str


class TechCodeRequest(BaseModel):
    code: str


async def safe_evaluate(tab, js_code):
    """Helper to catch JS errors in tab.evaluate() which nodriver otherwise swallows."""
    result = await tab.evaluate(js_code)
    # Check for ExceptionDetails in the result (nodriver/CDP specific)
    if isinstance(result, dict) and 'exceptionDetails' in result:
        ex = result['exceptionDetails']['exception']
        msg = ex.get('description', 'Unknown JS error')
        logger.error(f"JS Eval Error: {msg}\nCode: {js_code}")
        raise Exception(f"JavaScript error: {msg}")
    return result


async def solve_captcha_with_gemini(captcha_b64: str, max_retries: int = 1) -> str | None:
    """Try to read captcha text. Tries Groq Vision first, then Gemini, Vision API, Tesseract.
    
    Args:
        captcha_b64: Base64-encoded PNG image of the captcha
        max_retries: Number of retries on failure
        
    Returns:
        Recognized captcha text, or None if all methods failed
    """
    import re as _re
    
    # === Method 0: Groq Vision API (Llama 4 Scout — best for captchas) ===
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if groq_key:
        try:
            import aiohttp
            headers = {
                'Authorization': f'Bearer {groq_key}',
                'Content-Type': 'application/json',
            }
            payload = {
                'model': 'meta-llama/llama-4-scout-17b-16e-instruct',
                'messages': [{
                    'role': 'user',
                    'content': [
                        {'type': 'text', 'text': 'Read the distorted text in this captcha image. Return ONLY the text words, nothing else. No quotes, no explanation.'},
                        {'type': 'image_url', 'image_url': {'url': f'data:image/png;base64,{captcha_b64}'}}
                    ]
                }],
                'max_tokens': 50,
                'temperature': 0,
            }
            async with aiohttp.ClientSession() as session:
                async with session.post('https://api.groq.com/openai/v1/chat/completions',
                                        json=payload, headers=headers,
                                        timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        text = data['choices'][0]['message']['content'].strip().strip('"\'').strip()
                        # Clean: keep only alpha + spaces
                        text = _re.sub(r'[^a-zA-Z\s]', '', text).strip()
                        text = ' '.join(text.split())
                        if len(text) >= 3:
                            logger.info(f"Groq Vision OCR result: '{text}'")
                            return text
                    else:
                        err = await resp.text()
                        logger.warning(f"Groq API error {resp.status}: {err[:150]}")
        except Exception as e:
            logger.warning(f"Groq Vision failed: {e}")
    else:
        logger.info("No GROQ_API_KEY, skipping Groq Vision")
    
    # === Method 1: Gemini Vision API ===
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if api_key:
        try:
            import aiohttp
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={api_key}"
            payload = {
                "contents": [{"parts": [
                    {"inline_data": {"mime_type": "image/png", "data": captcha_b64}},
                    {"text": "Read the distorted text in this CAPTCHA image. Return ONLY the exact text you see, nothing else. The text consists of English words. Do not add quotes or explanation."}
                ]}],
                "generationConfig": {"temperature": 0.1, "maxOutputTokens": 50}
            }
            for attempt in range(max_retries + 1):
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                            if resp.status == 429:
                                logger.warning("Gemini API quota exceeded, falling back to Tesseract")
                                break  # Don't retry on quota — go to Tesseract
                            if resp.status != 200:
                                error_text = await resp.text()
                                logger.warning(f"Gemini API error {resp.status}: {error_text[:200]}")
                                continue
                            data = await resp.json()
                            candidates = data.get("candidates", [])
                            if candidates:
                                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
                                if text:
                                    text = text.strip('"\'').strip()
                                    logger.info(f"Gemini captcha OCR result: '{text}'")
                                    return text
                except Exception as e:
                    logger.warning(f"Gemini attempt {attempt + 1} failed: {e}")
        except ImportError:
            logger.warning("aiohttp not available for Gemini")
    else:
        logger.info("No GEMINI_API_KEY, skipping Gemini OCR")
    
    # === Method 2: Google Cloud Vision API (separate quota from Gemini) ===
    if api_key:
        try:
            import aiohttp
            vision_url = f"https://vision.googleapis.com/v1/images:annotate?key={api_key}"
            vision_payload = {
                "requests": [{
                    "image": {"content": captcha_b64},
                    "features": [{"type": "TEXT_DETECTION", "maxResults": 5}]
                }]
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(vision_url, json=vision_payload, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        annotations = data.get("responses", [{}])[0].get("textAnnotations", [])
                        if annotations:
                            text = annotations[0].get("description", "").strip()
                            if text:
                                # Clean: keep only alpha + spaces
                                import re
                                text = re.sub(r'[^a-zA-Z\s]', '', text).strip()
                                text = ' '.join(text.split())
                                if len(text) >= 3:
                                    logger.info(f"Google Vision OCR result: '{text}'")
                                    return text
                    else:
                        err = await resp.text()
                        logger.warning(f"Vision API error {resp.status}: {err[:150]}")
        except Exception as e:
            logger.warning(f"Vision API failed: {e}")
    
    # === Method 3: Tesseract OCR with tight captcha-only crop ===
    try:
        import pytesseract
        from PIL import Image, ImageFilter, ImageEnhance
        import base64
        from io import BytesIO
        
        logger.info("Trying Tesseract OCR for captcha...")
        
        img_data = base64.b64decode(captcha_b64)
        img = Image.open(BytesIO(img_data))
        orig_w, orig_h = img.size
        
        # Tight crop: just the captcha IMAGE rectangle within the popup
        # The popup has: captcha image at top, then label, input, buttons, footer
        # The captcha image is at ~30-73% width, 16-36% height of the center-crop
        text_crop = img.crop((
            int(orig_w * 0.28),   # Left edge of captcha image
            int(orig_h * 0.12),   # Top edge
            int(orig_w * 0.75),   # Right edge
            int(orig_h * 0.38)    # Bottom edge
        ))
        logger.info(f"Tesseract: tight-cropped captcha image to {text_crop.size} from {img.size}")
        
        # Save debug
        try:
            text_crop.save(os.path.join(DATA_DIR, "tesseract_debug_crop.png"), 'PNG')
        except: pass
        
        # Preprocess: grayscale, sharpen, contrast, scale up
        text_crop = text_crop.convert('L')
        text_crop = text_crop.filter(ImageFilter.SHARPEN)
        enhancer = ImageEnhance.Contrast(text_crop)
        text_crop = enhancer.enhance(1.5)
        text_crop = text_crop.resize((text_crop.width * 2, text_crop.height * 2), Image.LANCZOS)
        
        best_text = ""
        for psm in [7, 6, 13]:
            try:
                raw = pytesseract.image_to_string(text_crop, config=f'--psm {psm} -l eng').strip()
                if raw:
                    import re
                    cleaned = re.sub(r'[^a-zA-Z\s]', '', raw).strip()
                    cleaned = ' '.join(cleaned.split())
                    if len(cleaned) > len(best_text):
                        best_text = cleaned
                        logger.info(f"Tesseract PSM {psm}: '{cleaned}'")
            except: pass
        
        if best_text and len(best_text) >= 3:
            logger.info(f"Tesseract captcha OCR result: '{best_text}'")
            return best_text
        else:
            logger.warning(f"Tesseract: no good result (best: '{best_text}')")
    except ImportError:
        logger.warning("pytesseract not installed")
    except Exception as e:
        logger.warning(f"Tesseract OCR failed: {e}")
    
    return None


async def _keepalive_login_chrome(user_id: str):
    """Background task: ping Chrome JS context every 10s to prevent idle exit."""
    import asyncio as _async
    _fail_count = 0
    logger.info(f"Keepalive started for {user_id}")
    while True:
        await _async.sleep(10)
        entry = _login_sessions.get(user_id)
        if not entry or not entry.get("tab"):
            logger.info(f"Keepalive stopping for {user_id}: session removed")
            return
        try:
            await entry["tab"].evaluate("1+1")
            _fail_count = 0
        except Exception as e:
            _fail_count += 1
            logger.warning(f"Keepalive ping {_fail_count}/3 failed for {user_id}: {e}")
            if _fail_count >= 3:
                logger.error(f"Keepalive giving up for {user_id} after 3 failures")
                return


def _evict_stale_login_sessions():
    """Remove login sessions older than TTL."""
    now = _time.time()
    stale = [k for k, v in _login_sessions.items() if now - v.get("created_at", 0) > _LOGIN_TTL_SECONDS]
    for k in stale:
        entry = _login_sessions.pop(k, None)
        if entry and entry.get("browser"):
            try:
                entry["browser"].stop()
            except Exception:
                pass
        if entry and entry.get("proc"):
            try:
                entry["proc"].kill()
            except Exception:
                pass


@app.post("/api/auth/login")
async def auth_login(req: AuthPhoneRequest):
    """Start login: validate inputs, then launch Chrome in background. Returns job_id immediately."""
    import asyncio
    import time as _time
    import uuid

    user_id = req.user_id
    phone_raw = _normalize_phone(req.phone)
    if not phone_raw:
        raise HTTPException(status_code=400, detail="Некорректный формат телефона. Примеры: 9166076650, +79166076650, 89166076650")

    # R2-3: Rate limit login attempts per phone
    now = _time.time()
    attempts = _login_attempts.get(phone_raw, [])
    attempts = [t for t in attempts if now - t < _LOGIN_RATE_WINDOW]
    if len(attempts) >= _LOGIN_RATE_LIMIT:
        raise HTTPException(status_code=429, detail=f"Слишком много попыток входа. Подождите {int(_LOGIN_RATE_WINDOW / 60)} минут.")
    attempts.append(now)
    _login_attempts[phone_raw] = attempts

    # Check if this phone already has valid cookies + PIN (skip browser!)
    _cookies_path = _phone_cookies_path(phone_raw)
    _has_cookies_or_bak = os.path.exists(_cookies_path) or os.path.exists(_cookies_path + ".bak")
    if not req.force_sms and _has_cookies_or_bak:
        pin_data = _load_pin_data(phone_raw)
        if pin_data and pin_data.get("pin_hash"):
            _save_user_phone_mapping(user_id, phone_raw)
            return {"success": True, "need_pin": True, "message": "Введите PIN-код"}

    # Generate job ID and start background task
    job_id = str(uuid.uuid4())[:8]
    _login_jobs[job_id] = {
        "status": "starting",
        "message": "Запускаем...",
        "result": None,
        "user_id": user_id,
        "phone": phone_raw,
        "created_at": _time.time(),
    }

    # Evict old jobs
    stale_jobs = [k for k, v in _login_jobs.items() if now - v.get("created_at", 0) > _LOGIN_JOB_TTL]
    for k in stale_jobs:
        _login_jobs.pop(k, None)

    asyncio.create_task(_run_login_job(job_id, user_id, phone_raw, req.force_sms))
    return {"success": True, "job_id": job_id, "message": "Запущен вход..."}


@app.get("/api/auth/login/status/{job_id}")
async def auth_login_status(job_id: str):
    """Poll login job progress. Returns current status and message."""
    job = _login_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job["status"],
        "message": job["message"],
        "result": job.get("result"),
    }


async def _run_login_job(job_id: str, user_id: str, phone_raw: str, force_sms: bool):
    """Background task: launch Chrome, fill phone, solve captcha, wait for SMS.
    Updates _login_jobs[job_id] with progress. On success, stores browser in _login_sessions."""
    import nodriver as uc
    import asyncio
    import time as _time
    import sys

    def _update(status: str, message: str):
        _login_jobs[job_id]["status"] = status
        _login_jobs[job_id]["message"] = message

    # R2-4: Cleanup old debug screenshots
    _cleanup_debug_screenshots()

    # Patch nodriver Config (once)
    if not getattr(uc.Config, '_saleapp_patched', False):
        _orig_config_call = uc.Config.__call__
        def _patched_call(self):
            args = _orig_config_call(self)
            return [
                (a + ',LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessForWorkers,PrivateNetworkAccessForNavigations'
                 if a.startswith('--disable-features=') else a)
                for a in args
            ]
        uc.Config.__call__ = _patched_call
        uc.Config._saleapp_patched = True

    # Cleanup existing session for this user
    old_entry = _login_sessions.pop(user_id, None)
    if old_entry and old_entry.get("browser"):
        try:
            old_entry["browser"].stop()
        except Exception:
            pass
    if old_entry and old_entry.get("proc"):
        try:
            old_entry["proc"].kill()
        except Exception:
            pass
    _evict_stale_login_sessions()

    browser = None
    _chrome_proc = None
    _user_data_dir = None
    try:
        import tempfile
        import subprocess as _subp
        import socket as _socket

        _update("launching", "Запускаем браузер...")

        def _find_free_port():
            with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', 0))
                return s.getsockname()[1]

        _debug_port = _find_free_port()
        _user_data_dir = tempfile.mkdtemp(prefix='uc_login_')

        if sys.platform != 'win32':
            browser = await uc.start(
                headless=True,
                user_data_dir=_user_data_dir,
                browser_args=[
                    '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                    '--disable-software-rasterizer',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--window-size=1280,720', '--lang=ru-RU,ru',
                ],
            )
            _chrome_proc = None
        else:
            _chrome_path = None
            for p in [
                r'C:\Program Files\Google\Chrome\Application\chrome.exe',
                r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
                os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
            ]:
                if os.path.exists(p):
                    _chrome_path = p
                    break
            if not _chrome_path:
                raise RuntimeError("Chrome not found")
            _chrome_proc = _subp.Popen([
                _chrome_path,
                f'--remote-debugging-port={_debug_port}',
                f'--user-data-dir={_user_data_dir}',
                '--window-position=-2400,-2400',
                '--window-size=1280,720',
                '--disable-gpu',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--no-sandbox',
                '--lang=ru-RU,ru',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-features=IsolateOrigins,site-per-process,LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessForWorkers,PrivateNetworkAccessForNavigations',
                'about:blank',
            ], creationflags=_subp.CREATE_NO_WINDOW if sys.platform == 'win32' else 0)

        _update("navigating", "Открываем ВкусВилл...")
        tab = await browser.get('https://vkusvill.ru/personal/')
        await asyncio.sleep(5)

        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_1_init.png"))
        except: pass

        _update("entering_phone", "Вводим номер телефона...")

        input_box = await tab.select('input.js-user-form-checksms-api-phone1', timeout=2)
        if not input_box:
            input_box = await tab.select('input[name="USER_PHONE"]', timeout=2)

        if input_box:
            await input_box.mouse_click()
            await asyncio.sleep(0.5)
            for digit in phone_raw:
                await tab.send(uc.cdp.input_.dispatch_key_event(
                    type_='keyDown', key=digit, text=digit,
                    code=f'Digit{digit}',
                    windows_virtual_key_code=ord(digit),
                    native_virtual_key_code=ord(digit),
                ))
                await asyncio.sleep(0.05)
                await tab.send(uc.cdp.input_.dispatch_key_event(
                    type_='keyUp', key=digit, code=f'Digit{digit}',
                    windows_virtual_key_code=ord(digit),
                    native_virtual_key_code=ord(digit),
                ))
                await asyncio.sleep(0.2)
            await asyncio.sleep(1.0)
        else:
            logger.error("Could not find phone input box on VkusVill login page")

        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_2_phone.png"))
        except: pass

        _update("submitting", "Отправляем форму...")

        submit_btn = await tab.select('button.js-user-form-submit-btn', timeout=2)
        if submit_btn:
            await tab.evaluate("document.querySelector('button.js-user-form-submit-btn').disabled = false;")
            await tab.evaluate("document.querySelector('button.js-user-form-submit-btn').classList.remove('disabled');")
            await submit_btn.click()
        else:
            logger.error("Could not find submit button on VkusVill login page")

        await asyncio.sleep(5)
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_3_after_click.png"))
        except: pass

        # Check for CAPTCHA
        captcha_detected = False
        try:
            captcha_result = await safe_evaluate(tab, """
                (function() {
                    var html = document.documentElement.outerHTML.toLowerCase();
                    if (html.includes('smartcaptcha') || html.includes('captcha__image') ||
                        html.includes('enter the code from the image') ||
                        html.includes('введите код с картинки')) {
                        return 'CAPTCHA_HTML';
                    }
                    var iframes = document.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        if (iframes[i].src && iframes[i].src.includes('captcha')) return 'CAPTCHA_IFRAME';
                    }
                    var bodyText = document.body ? document.body.innerText : '';
                    if (bodyText.includes('SmartCaptcha') || bodyText.includes('Enter the code')) return 'CAPTCHA_TEXT';
                    return 'NONE';
                })()
            """)
            logger.info(f"Captcha detection result: {captcha_result}")
            if isinstance(captcha_result, str) and captcha_result.startswith('CAPTCHA'):
                captcha_detected = True
        except Exception as _e:
            logger.warning(f"Captcha detection error: {_e}")

        if captcha_detected:
            import base64
            captcha_b64 = None

            captcha_path = os.path.join(DATA_DIR, f"login_{user_id}_captcha.png")
            try:
                await asyncio.wait_for(tab.save_screenshot(captcha_path), timeout=15)
                fsize = os.path.getsize(captcha_path) if os.path.exists(captcha_path) else 0
                logger.info(f"Captcha screenshot saved: {captcha_path}, size={fsize}")

                if fsize > 0:
                    try:
                        from PIL import Image
                        img = Image.open(captcha_path)
                        img_w, img_h = img.size
                        cx, cy = img_w // 2, img_h // 2
                        crop_half_w = min(int(img_w * 0.22), 300)
                        crop_half_h = min(int(img_h * 0.35), 220)
                        crop_x = max(0, cx - crop_half_w)
                        crop_y = max(0, cy - crop_half_h)
                        crop_r = min(img_w, cx + crop_half_w)
                        crop_b = min(img_h, cy + crop_half_h)
                        cropped = img.crop((crop_x, crop_y, crop_r, crop_b))
                        new_w = cropped.width * 3
                        new_h = cropped.height * 3
                        cropped = cropped.resize((new_w, new_h), Image.LANCZOS)
                        crop_path = os.path.join(DATA_DIR, f"login_{user_id}_captcha_crop.png")
                        cropped.save(crop_path, 'PNG')
                        logger.info(f"Center-cropped captcha: {crop_x},{crop_y} -> {crop_r},{crop_b}, scaled 3x to {new_w}x{new_h}")
                        with open(crop_path, 'rb') as f:
                            captcha_b64 = base64.b64encode(f.read()).decode('utf-8')
                    except Exception as crop_err:
                        logger.warning(f"Captcha crop failed, using full screenshot: {crop_err}")

                    if not captcha_b64:
                        with open(captcha_path, 'rb') as f:
                            captcha_b64 = base64.b64encode(f.read()).decode('utf-8')
            except asyncio.TimeoutError:
                logger.warning("save_screenshot timed out after 15s")
            except Exception as _e:
                logger.error(f"Captcha screenshot failed: {_e}")

            if captcha_b64:
                import nodriver.cdp.input_ as cdp_input
                import time as _time2
                auto_solved = False
                auto_start = _time2.monotonic()

                for auto_attempt in range(8):
                    if _time2.monotonic() - auto_start > 120:
                        logger.warning("Auto-solve timed out (>120s)")
                        break

                    _update("solving_captcha", f"Разгадываем капчу (попытка {auto_attempt + 1})...")

                    gemini_answer = await solve_captcha_with_gemini(captcha_b64)
                    if not gemini_answer:
                        logger.info(f"Auto-solve attempt {auto_attempt + 1}: OCR unavailable, retrying...")
                        await asyncio.sleep(1)
                        continue

                    logger.info(f"Auto-solve attempt {auto_attempt + 1}/8: '{gemini_answer}'")

                    try:
                        iframe_bounds = await safe_evaluate(tab, """
                            (function() {
                                var iframes = document.querySelectorAll('iframe');
                                var best = null, bestArea = 0;
                                for (var i = 0; i < iframes.length; i++) {
                                    if (iframes[i].src && iframes[i].src.indexOf('captcha') > -1) {
                                        var rect = iframes[i].getBoundingClientRect();
                                        var area = rect.width * rect.height;
                                        if (area > bestArea) {
                                            bestArea = area;
                                            best = {x: rect.x, y: rect.y, w: rect.width, h: rect.height, src: iframes[i].src.substring(0, 80)};
                                        }
                                    }
                                }
                                return best ? JSON.stringify(best) : 'NO_IFRAME';
                            })()
                        """)
                    except Exception as iframe_err:
                        logger.warning(f"Iframe detection failed: {iframe_err}")
                        iframe_bounds = 'NO_IFRAME'

                    if not iframe_bounds or iframe_bounds == 'NO_IFRAME':
                        logger.warning("No captcha iframe found for auto-solve")
                        break

                    import json as _json2
                    try:
                        bounds = _json2.loads(iframe_bounds)
                        logger.info(f"Captcha iframe for auto-solve: {iframe_bounds}")
                    except Exception as json_err:
                        logger.warning(f"Iframe bounds JSON parse failed: {json_err}, raw: {iframe_bounds[:100]}")
                        break

                    if not bounds or bounds.get('w', 0) <= 0:
                        logger.warning(f"Captcha iframe has zero size: {bounds}")
                        break

                    ix, iy, iw, ih = bounds['x'], bounds['y'], bounds['w'], bounds['h']
                    input_x = ix + iw * 0.5
                    input_y = iy + ih * 0.53

                    await tab.send(cdp_input.dispatch_mouse_event(type_='mousePressed', x=input_x, y=input_y, button=cdp_input.MouseButton.LEFT, click_count=3))
                    await asyncio.sleep(0.05)
                    await tab.send(cdp_input.dispatch_mouse_event(type_='mouseReleased', x=input_x, y=input_y, button=cdp_input.MouseButton.LEFT, click_count=3))
                    await asyncio.sleep(0.5)

                    await tab.send(cdp_input.dispatch_key_event(type_='keyDown', key='Backspace', code='Backspace'))
                    await tab.send(cdp_input.dispatch_key_event(type_='keyUp', key='Backspace', code='Backspace'))
                    await asyncio.sleep(0.1)

                    for ch in gemini_answer:
                        await tab.send(cdp_input.dispatch_key_event(type_='keyDown', key=ch))
                        await tab.send(cdp_input.dispatch_key_event(type_='char', key=ch, text=ch))
                        await tab.send(cdp_input.dispatch_key_event(type_='keyUp', key=ch))
                        await asyncio.sleep(0.03)

                    logger.info(f"Auto-typed '{gemini_answer}' into captcha")
                    await asyncio.sleep(0.3)

                    submit_x = ix + iw * 0.55
                    submit_y = iy + ih * 0.65
                    await tab.send(cdp_input.dispatch_mouse_event(type_='mousePressed', x=submit_x, y=submit_y, button=cdp_input.MouseButton.LEFT, click_count=1))
                    await asyncio.sleep(0.05)
                    await tab.send(cdp_input.dispatch_mouse_event(type_='mouseReleased', x=submit_x, y=submit_y, button=cdp_input.MouseButton.LEFT, click_count=1))

                    await asyncio.sleep(3)

                    try:
                        still_captcha = await safe_evaluate(tab, """
                            (function() {
                                var iframes = document.querySelectorAll('iframe');
                                for (var i = 0; i < iframes.length; i++) {
                                    if (iframes[i].src && iframes[i].src.indexOf('captcha') > -1) {
                                        var r = iframes[i].getBoundingClientRect();
                                        if (r.width > 100 && r.height > 100) return true;
                                    }
                                }
                                return false;
                            })()
                        """)
                    except:
                        still_captcha = True

                    if not still_captcha:
                        logger.info(f"Captcha auto-solved successfully with Gemini! Answer: '{gemini_answer}'")
                        auto_solved = True
                        break
                    else:
                        logger.info(f"Auto-solve attempt {auto_attempt + 1} failed (wrong answer: '{gemini_answer}'), retrying...")
                        try:
                            captcha_path = os.path.join(DATA_DIR, f"login_{user_id}_captcha.png")
                            await tab.save_screenshot(captcha_path)
                            captcha_b64 = None
                            from PIL import Image
                            img = Image.open(captcha_path)
                            img_w, img_h = img.size
                            cx, cy = img_w // 2, img_h // 2
                            crop_half_w = min(int(img_w * 0.22), 300)
                            crop_half_h = min(int(img_h * 0.35), 220)
                            cropped = img.crop((max(0, cx - crop_half_w), max(0, cy - crop_half_h),
                                               min(img_w, cx + crop_half_w), min(img_h, cy + crop_half_h)))
                            cropped = cropped.resize((cropped.width * 3, cropped.height * 3), Image.LANCZOS)
                            crop_path = os.path.join(DATA_DIR, f"login_{user_id}_captcha_crop.png")
                            cropped.save(crop_path, 'PNG')
                            with open(crop_path, 'rb') as f:
                                captcha_b64 = base64.b64encode(f.read()).decode('utf-8')
                        except Exception as re_err:
                            logger.warning(f"Re-crop failed: {re_err}")
                            break
                        if not captcha_b64:
                            break

                if auto_solved:
                    logger.info("Auto-solve succeeded, continuing to SMS polling...")
                else:
                    logger.warning(f"All auto-solve attempts exhausted for {user_id}")
                    try:
                        browser.stop()
                    except Exception:
                        pass
                    _login_sessions.pop(user_id, None)
                    _update("error", "Не удалось пройти капчу автоматически. Попробуйте ещё раз.")
                    _login_jobs[job_id]["result"] = {"success": False}
                    return
            # If screenshot failed, continue to SMS polling (might work without captcha)

        # === Handle VkusVill Registration dialog ===
        _update("handling_registration", "Проверяем форму...")
        await asyncio.sleep(2)
        try:
            reg_check = await safe_evaluate(tab, """
                (function() {
                    var body = document.body.innerText;
                    if (body.indexOf('Регистрация') > -1 && body.indexOf('Зарегистрироваться') > -1) {
                        return 'REGISTRATION';
                    }
                    return 'NO';
                })()
            """)
            if reg_check == 'REGISTRATION':
                logger.info("Registration form detected — filling name via CDP and submitting")
                import nodriver.cdp.input_ as cdp_input
                
                # Find the name input field position and the Register button position
                positions = await safe_evaluate(tab, """
                    (function() {
                        var result = {input: null, button: null};
                        // Find Register button first
                        var btns = document.querySelectorAll('button, [role="button"]');
                        for (var i = 0; i < btns.length; i++) {
                            if (btns[i].textContent.trim().indexOf('Зарегистрироваться') > -1) {
                                var r = btns[i].getBoundingClientRect();
                                result.button = {x: r.x + r.width/2, y: r.y + r.height/2};
                                break;
                            }
                        }
                        // Find ALL visible inputs and pick the one closest above the Register button
                        // IMPORTANT: must also be horizontally aligned with button (in same modal)
                        var inputs = document.querySelectorAll('input');
                        var bestInput = null, bestDist = 999;
                        for (var i = 0; i < inputs.length; i++) {
                            var r = inputs[i].getBoundingClientRect();
                            if (r.width < 50 || r.height < 10 || r.top < 0) continue;
                            var t = inputs[i].type || 'text';
                            if (t === 'hidden' || t === 'checkbox' || t === 'radio' || t === 'submit') continue;
                            // Must be above the button, within reasonable Y distance, AND horizontally aligned
                            if (result.button && r.y < result.button.y && (result.button.y - r.y) < 200) {
                                var inputCx = r.x + r.width/2;
                                var xDist = Math.abs(inputCx - result.button.x);
                                if (xDist > 200) continue;  // Too far horizontally = different modal/form
                                var dist = result.button.y - r.y;
                                if (dist < bestDist) {
                                    bestDist = dist;
                                    bestInput = {x: inputCx, y: r.y + r.height/2};
                                }
                            }
                        }
                        result.input = bestInput;
                        return JSON.stringify(result);
                    })()
                """)
                
                import json as _json3
                try:
                    pos = _json3.loads(positions) if isinstance(positions, str) else {}
                except:
                    pos = {}
                
                input_pos = pos.get('input')
                btn_pos = pos.get('button')
                logger.info(f"Registration positions: input={input_pos}, button={btn_pos}")
                
                if input_pos:
                    # Click the name input field
                    ix, iy = input_pos['x'], input_pos['y']
                elif btn_pos:
                    # Fallback: the name input is ~60px above the Register button
                    ix, iy = btn_pos['x'], btn_pos['y'] - 60
                    logger.info(f"Input not found via JS, using fallback position ({ix}, {iy})")
                else:
                    ix, iy = None, None
                
                if ix is not None:
                    await tab.send(cdp_input.dispatch_mouse_event(type_='mousePressed', x=ix, y=iy, button=cdp_input.MouseButton.LEFT, click_count=1))
                    await asyncio.sleep(0.05)
                    await tab.send(cdp_input.dispatch_mouse_event(type_='mouseReleased', x=ix, y=iy, button=cdp_input.MouseButton.LEFT, click_count=1))
                    await asyncio.sleep(0.3)
                    
                    # Type name using CDP key events (Cyrillic)
                    name = "Покупатель"
                    for ch in name:
                        await tab.send(cdp_input.dispatch_key_event(type_='keyDown', key=ch))
                        await tab.send(cdp_input.dispatch_key_event(type_='char', key=ch, text=ch))
                        await tab.send(cdp_input.dispatch_key_event(type_='keyUp', key=ch))
                        await asyncio.sleep(0.03)
                    
                    logger.info(f"Typed name '{name}' via CDP at ({ix}, {iy})")
                    await asyncio.sleep(0.5)
                
                if btn_pos:
                    # Click Register button
                    bx, by = btn_pos['x'], btn_pos['y']
                    await tab.send(cdp_input.dispatch_mouse_event(type_='mousePressed', x=bx, y=by, button=cdp_input.MouseButton.LEFT, click_count=1))
                    await asyncio.sleep(0.05)
                    await tab.send(cdp_input.dispatch_mouse_event(type_='mouseReleased', x=bx, y=by, button=cdp_input.MouseButton.LEFT, click_count=1))
                    logger.info("Clicked 'Зарегистрироваться' via CDP")
                    await asyncio.sleep(3)
                else:
                    logger.warning("Register button position not found")
        except Exception as reg_err:
            logger.warning(f"Registration form handling failed: {reg_err}")

        # === After registration, VkusVill returns to login form ===
        # We need to click "Продолжить" again to trigger SMS dispatch.
        await asyncio.sleep(2)
        try:
            post_reg_check = await safe_evaluate(tab, """
                (function() {
                    var body = document.body.innerText;
                    if (body.indexOf('Продолжить') > -1 && body.indexOf('номер телефона') > -1) return 'LOGIN_FORM';
                    if (body.indexOf('Получить код') > -1) return 'LOGIN_FORM';
                    if (body.indexOf('Введите код') > -1) return 'SMS_OK';
                    return 'OTHER';
                })()
            """)
            if post_reg_check == 'LOGIN_FORM':
                logger.info("Post-registration: login form detected, clicking Продолжить/Получить код again")
                # Click the submit button 
                await safe_evaluate(tab, """
                    (function() {
                        var btns = document.querySelectorAll('button, [role="button"]');
                        for (var i = 0; i < btns.length; i++) {
                            var t = btns[i].textContent.trim();
                            if (t.indexOf('Продолжить') > -1 || t.indexOf('Получить код') > -1) {
                                btns[i].click();
                                return 'CLICKED';
                            }
                        }
                        return 'NOT_FOUND';
                    })()
                """)
                logger.info("Clicked Продолжить after registration")
                await asyncio.sleep(5)  # Wait for VkusVill to process
                
                # Check if another captcha appeared
                captcha_check2 = await safe_evaluate(tab, """
                    (function() {
                        var iframes = document.querySelectorAll('iframe');
                        for (var i = 0; i < iframes.length; i++) {
                            if (iframes[i].src && iframes[i].src.indexOf('captcha') > -1) {
                                var r = iframes[i].getBoundingClientRect();
                                if (r.width > 100 && r.height > 100) return 'CAPTCHA';
                            }
                        }
                        return 'NO_CAPTCHA';
                    })()
                """)
                if captcha_check2 == 'CAPTCHA':
                    logger.info("Second captcha appeared after registration — solving (up to 3 attempts)...")
                    for _cap2_attempt in range(3):
                     # Take screenshot, crop, solve again
                     try:
                        captcha_path2 = os.path.join(DATA_DIR, f"login_{user_id}_captcha2_{_cap2_attempt}.png")
                        await tab.save_screenshot(captcha_path2)
                        from PIL import Image
                        img2 = Image.open(captcha_path2)
                        w2, h2 = img2.size
                        cx2, cy2 = w2 // 2, h2 // 2
                        chw2 = min(int(w2 * 0.22), 300)
                        chh2 = min(int(h2 * 0.35), 220)
                        crop2 = img2.crop((max(0, cx2-chw2), max(0, cy2-chh2), min(w2, cx2+chw2), min(h2, cy2+chh2)))
                        crop2 = crop2.resize((crop2.width*3, crop2.height*3), Image.LANCZOS)
                        crop2_path = os.path.join(DATA_DIR, f"login_{user_id}_captcha2_crop_{_cap2_attempt}.png")
                        crop2.save(crop2_path, 'PNG')
                        with open(crop2_path, 'rb') as f:
                            captcha_b64_2 = base64.b64encode(f.read()).decode('utf-8')
                        answer2 = await solve_captcha_with_gemini(captcha_b64_2)
                        if answer2:
                            logger.info(f"Second captcha OCR attempt {_cap2_attempt+1}: '{answer2}'")
                            import nodriver.cdp.input_ as cdp_input
                            # Find captcha iframe and type
                            ifb2 = await safe_evaluate(tab, """
                                (function() {
                                    var iframes = document.querySelectorAll('iframe');
                                    var best = null, bestArea = 0;
                                    for (var i = 0; i < iframes.length; i++) {
                                        if (iframes[i].src && iframes[i].src.indexOf('captcha') > -1) {
                                            var r = iframes[i].getBoundingClientRect();
                                            var a = r.width * r.height;
                                            if (a > bestArea) { bestArea = a; best = {x:r.x,y:r.y,w:r.width,h:r.height}; }
                                        }
                                    }
                                    return best ? JSON.stringify(best) : 'NO';
                                })()
                            """)
                            import json as _json4
                            try:
                                b2 = _json4.loads(ifb2) if isinstance(ifb2, str) and ifb2 != 'NO' else None
                            except:
                                b2 = None
                            if b2:
                                cx2 = b2['x'] + b2['w'] * 0.5
                                cy2 = b2['y'] + b2['h'] * 0.53
                                await tab.send(cdp_input.dispatch_mouse_event(type_='mousePressed', x=cx2, y=cy2, button=cdp_input.MouseButton.LEFT, click_count=3))
                                await asyncio.sleep(0.05)
                                await tab.send(cdp_input.dispatch_mouse_event(type_='mouseReleased', x=cx2, y=cy2, button=cdp_input.MouseButton.LEFT, click_count=3))
                                await asyncio.sleep(0.5)
                                for ch in answer2:
                                    await tab.send(cdp_input.dispatch_key_event(type_='keyDown', key=ch))
                                    await tab.send(cdp_input.dispatch_key_event(type_='char', key=ch, text=ch))
                                    await tab.send(cdp_input.dispatch_key_event(type_='keyUp', key=ch))
                                    await asyncio.sleep(0.03)
                                logger.info(f"Typed second captcha answer '{answer2}'")
                                await asyncio.sleep(0.3)
                                sx2 = b2['x'] + b2['w'] * 0.55
                                sy2 = b2['y'] + b2['h'] * 0.65
                                await tab.send(cdp_input.dispatch_mouse_event(type_='mousePressed', x=sx2, y=sy2, button=cdp_input.MouseButton.LEFT, click_count=1))
                                await asyncio.sleep(0.05)
                                await tab.send(cdp_input.dispatch_mouse_event(type_='mouseReleased', x=sx2, y=sy2, button=cdp_input.MouseButton.LEFT, click_count=1))
                                logger.info(f"Submitted second captcha (attempt {_cap2_attempt+1})")
                                await asyncio.sleep(5)
                                # Check if captcha is gone (solved correctly)
                                still_captcha = await safe_evaluate(tab, """
                                    (function() {
                                        var iframes = document.querySelectorAll('iframe');
                                        for (var i = 0; i < iframes.length; i++) {
                                            if (iframes[i].src && iframes[i].src.indexOf('captcha') > -1) {
                                                var r = iframes[i].getBoundingClientRect();
                                                if (r.width > 100 && r.height > 100) return 'CAPTCHA';
                                            }
                                        }
                                        return 'NO';
                                    })()
                                """)
                                if still_captcha != 'CAPTCHA':
                                    logger.info(f"Second captcha solved on attempt {_cap2_attempt+1}!")
                                    break
                                else:
                                    logger.warning(f"Second captcha attempt {_cap2_attempt+1} failed (wrong answer: '{answer2}'), refreshing...")
                                    await asyncio.sleep(2)
                                    continue
                     except Exception as cap2_err:
                        logger.warning(f"Second captcha attempt {_cap2_attempt+1} failed: {cap2_err}")
                        if _cap2_attempt < 2:
                            await asyncio.sleep(2)
                            continue
            elif post_reg_check == 'SMS_OK':
                logger.info("Post-registration: SMS input already visible!")
        except Exception as post_reg_err:
            logger.warning(f"Post-registration check failed: {post_reg_err}")
        # Immediate rate-limit check — the error dialog appears right after click
        # (don't wait 30s to tell the user their number is blocked)
        # Use safe_evaluate to handle ExceptionDetails from nodriver
        try:
            page_text = await safe_evaluate(tab, "document.body.innerText")
            if isinstance(page_text, str):
                if 'заблокирован' in page_text or 'суточный лимит' in page_text:
                    try:
                        await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_4_rate_limit.png"))
                    except: pass
                    try: browser.stop()
                    except Exception: pass
                    _update("error", "Ваш номер заблокирован для отправки SMS. Исчерпан суточный лимит (4 запроса). Попробуйте завтра.")
                    _login_jobs[job_id]["result"] = {"success": False}
                    return
                if 'Превышено количество попыток' in page_text:
                    try:
                        await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_4_rate_limit.png"))
                    except: pass
                    try: browser.stop()
                    except Exception: pass
                    _update("error", "Превышено количество попыток. Запросите новую СМС через 3 минуты.")
                    _login_jobs[job_id]["result"] = {"success": False}
                    return
        except Exception:
            pass  # If early check fails, continue to polling loop

        # Wait up to 30s for ACTUAL page transition to SMS code input
        _update("waiting_sms", "Ожидаем SMS...")
        sms_found = False
        for _ in range(30):
            await asyncio.sleep(1)
            try:
                result = await safe_evaluate(tab, """
                    (function() {
                        var sms = document.querySelector('input[name="SMS"]');
                        var smsVisible = sms ? (sms.offsetParent !== null &&
                                                sms.getBoundingClientRect().height > 0) : false;
                        var codeText = document.body.innerText.includes('Введите код');
                        // Check for rate limit error popup
                        var rateLimit = document.body.innerText.includes('Превышено количество попыток');
                        var dailyBlock = document.body.innerText.includes('заблокирован') ||
                                         document.body.innerText.includes('суточный лимит');
                        if (rateLimit || dailyBlock) return 'RATE_LIMIT:' + (dailyBlock ? 'DAILY' : 'SESSION');
                        return smsVisible || codeText ? 'OK' : false;
                    })()
                """)
            except Exception:
                result = None
            if isinstance(result, str) and result.startswith('RATE_LIMIT'):
                try:
                    await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_4_rate_limit.png"))
                except: pass
                try: browser.stop()
                except Exception: pass
                msg = "Ваш номер заблокирован для отправки SMS. Исчерпан суточный лимит (4 запроса). Попробуйте завтра." if 'DAILY' in result else "Превышено количество попыток. Запросите новую СМС через 3 минуты."
                _update("error", msg)
                _login_jobs[job_id]["result"] = {"success": False}
                return
            if result == 'OK':
                sms_found = True
                break

        if not sms_found:
            try:
                await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_4_no_sms.png"))
            except: pass
            try: browser.stop()
            except Exception: pass
            _update("error", "Не удалось отправить SMS. Попробуйте позже.")
            _login_jobs[job_id]["result"] = {"success": False}
            return

        # Take success screenshot showing SMS code input screen
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_4_sms_ok.png"))
        except: pass

        _login_sessions[user_id] = {
            "browser": browser,
            "tab": tab,
            "phone": phone_raw,
            "force_sms": force_sms,
            "created_at": _time.time(),
            "proc": _chrome_proc,
            "profile_dir": _user_data_dir,
        }
        # Start keepalive to prevent Chrome from dying while user types SMS code
        import asyncio as _ka_asyncio
        _ka_asyncio.create_task(_keepalive_login_chrome(user_id))

        _update("done", "SMS отправлено. Введите код из SMS.")
        _login_jobs[job_id]["result"] = {"success": True, "need_pin": False}
        return

    except Exception as e:
        import traceback
        logger.error(f"Login job error: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        if browser:
            try: browser.stop()
            except Exception: pass
        if _chrome_proc:
            try: _chrome_proc.kill()
            except Exception: pass
        if _user_data_dir:
            import shutil
            try: shutil.rmtree(_user_data_dir, ignore_errors=True)
            except Exception: pass
        _update("error", "Ошибка при попытке входа. Попробуйте ещё раз.")
        _login_jobs[job_id]["result"] = {"success": False}


@app.post("/api/auth/captcha")
async def auth_captcha(req: AuthCaptchaRequest):
    """Submit captcha answer to VkusVill and wait for SMS code input."""
    import asyncio

    user_id = req.user_id
    entry = _login_sessions.get(user_id)
    if not entry or not entry.get("awaiting_captcha"):
        raise HTTPException(status_code=400, detail="Нет активной капчи. Начните вход заново.")

    tab = entry["tab"]
    browser = entry["browser"]
    answer = req.captcha_answer.strip()

    if not answer:
        raise HTTPException(status_code=400, detail="Введите ответ на капчу")

    try:
        # First, dump page info for debugging
        page_info = await safe_evaluate(tab, """
            (function() {
                var iframes = document.querySelectorAll('iframe');
                var info = 'Iframes: ' + iframes.length;
                for (var i = 0; i < iframes.length; i++) {
                    info += ' | src=' + (iframes[i].src || 'none').substring(0, 100);
                }
                var inputs = document.querySelectorAll('input');
                info += ' | Inputs: ' + inputs.length;
                for (var j = 0; j < inputs.length; j++) {
                    info += ' | ' + inputs[j].type + ':' + (inputs[j].placeholder || '').substring(0, 50);
                }
                return info;
            })()
        """)
        logger.info(f"Page info for captcha: {page_info}")

        # Try main page first
        typed_ok = await safe_evaluate(tab, f"""
            (function() {{
                var inp = document.querySelector('input[placeholder*="letters"], input[placeholder*="букв"], input[placeholder*="Uppercase"], input[placeholder*="code"]');
                if (!inp) {{
                    var inputs = document.querySelectorAll('input[type="text"], input:not([type])');
                    for (var i = 0; i < inputs.length; i++) {{
                        var p = inputs[i].closest('[class*="captcha"], [class*="Captcha"], [class*="SmartCaptcha"]');
                        if (p) {{ inp = inputs[i]; break; }}
                    }}
                }}
                if (inp) {{
                    inp.focus();
                    inp.value = '';
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                    nativeInputValueSetter.call(inp, '{answer}');
                    inp.dispatchEvent(new Event('input', {{ bubbles: true }}));
                    inp.dispatchEvent(new Event('change', {{ bubbles: true }}));
                    return 'OK';
                }}
                return 'NOT_FOUND';
            }})()
        """)
        logger.info(f"Main page captcha input result: {typed_ok}")

        # If not found on main page, try clicking into the captcha iframe input via CDP Input events
        # Cross-origin iframes block JS access, but CDP Input events work at browser level
        if typed_ok != 'OK':
            logger.info("Captcha input not on main page, using CDP Input events to click/type into iframe...")
            try:
                import nodriver.cdp.input_ as cdp_input
                
                # Get the iframe bounding box from the main page
                iframe_bounds = await safe_evaluate(tab, """
                    (function() {
                        var iframes = document.querySelectorAll('iframe');
                        for (var i = 0; i < iframes.length; i++) {
                            if (iframes[i].src && iframes[i].src.indexOf('advanced') > -1 && iframes[i].src.indexOf('captcha') > -1) {
                                var rect = iframes[i].getBoundingClientRect();
                                return JSON.stringify({x: rect.x, y: rect.y, w: rect.width, h: rect.height, src: iframes[i].src.substring(0, 80)});
                            }
                        }
                        // Fallback: try any captcha iframe
                        for (var i = 0; i < iframes.length; i++) {
                            if (iframes[i].src && iframes[i].src.indexOf('captcha') > -1) {
                                var rect = iframes[i].getBoundingClientRect();
                                return JSON.stringify({x: rect.x, y: rect.y, w: rect.width, h: rect.height, src: iframes[i].src.substring(0, 80)});
                            }
                        }
                        return 'NO_CAPTCHA_IFRAME';
                    })()
                """)
                logger.info(f"Captcha iframe bounds: {iframe_bounds}")
                
                if iframe_bounds and iframe_bounds != 'NO_CAPTCHA_IFRAME':
                    import json as _json
                    try:
                        bounds = _json.loads(iframe_bounds)
                    except:
                        bounds = None
                    
                    if bounds and bounds.get('w', 0) > 0:
                        iframe_x = bounds['x']
                        iframe_y = bounds['y']
                        iframe_w = bounds['w']
                        iframe_h = bounds['h']
                        
                        # The captcha popup is centered in the iframe.
                        # Based on actual screenshots of the SmartCaptcha layout:
                        # - Captcha image: ~25-35% from top
                        # - "Enter the code" text: ~45% from top
                        # - Input field: ~53% from top (this is where we need to click!)
                        # - Submit button: ~66% from top
                        input_x = iframe_x + iframe_w * 0.5
                        input_y = iframe_y + iframe_h * 0.53
                        
                        logger.info(f"Clicking captcha input at ({input_x}, {input_y}) iframe=({iframe_x},{iframe_y},{iframe_w}x{iframe_h})")
                        
                        # Triple-click to focus and select all existing text in input
                        await tab.send(cdp_input.dispatch_mouse_event(
                            type_='mousePressed',
                            x=input_x,
                            y=input_y,
                            button=cdp_input.MouseButton.LEFT,
                            click_count=3
                        ))
                        await asyncio.sleep(0.05)
                        await tab.send(cdp_input.dispatch_mouse_event(
                            type_='mouseReleased',
                            x=input_x,
                            y=input_y,
                            button=cdp_input.MouseButton.LEFT,
                            click_count=3
                        ))
                        await asyncio.sleep(0.5)
                        
                        # Delete any selected text
                        await tab.send(cdp_input.dispatch_key_event(type_='keyDown', key='Backspace', code='Backspace'))
                        await tab.send(cdp_input.dispatch_key_event(type_='keyUp', key='Backspace', code='Backspace'))
                        await asyncio.sleep(0.1)
                        
                        # Type each character — keyDown (no text), char (inserts text), keyUp
                        for ch in answer:
                            await tab.send(cdp_input.dispatch_key_event(
                                type_='keyDown',
                                key=ch
                            ))
                            await tab.send(cdp_input.dispatch_key_event(
                                type_='char',
                                key=ch,
                                text=ch
                            ))
                            await tab.send(cdp_input.dispatch_key_event(
                                type_='keyUp',
                                key=ch
                            ))
                            await asyncio.sleep(0.03)
                        
                        logger.info(f"Typed captcha answer '{answer}' via CDP Input events")
                        await asyncio.sleep(0.3)
                        
                        # Take screenshot to verify typing worked
                        try:
                            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_5a_after_typing.png"))
                        except: pass
                        
                        # Now click submit — right-of-center (icons left, button right)
                        submit_x = iframe_x + iframe_w * 0.55
                        submit_y = iframe_y + iframe_h * 0.65
                        
                        logger.info(f"Clicking captcha submit at ({submit_x}, {submit_y})")
                        
                        await tab.send(cdp_input.dispatch_mouse_event(
                            type_='mousePressed',
                            x=submit_x,
                            y=submit_y,
                            button=cdp_input.MouseButton.LEFT,
                            click_count=1
                        ))
                        await asyncio.sleep(0.05)
                        await tab.send(cdp_input.dispatch_mouse_event(
                            type_='mouseReleased',
                            x=submit_x,
                            y=submit_y,
                            button=cdp_input.MouseButton.LEFT,
                            click_count=1
                        ))
                        
                        typed_ok = 'OK'
                        logger.info("CDP Input events: typed answer and clicked submit")

            except Exception as te:
                logger.error(f"CDP Input events failed: {te}", exc_info=True)

        if typed_ok != 'OK':
            logger.error(f"Could not find captcha input field anywhere. Last result: {typed_ok}")
            raise HTTPException(status_code=500, detail="Не найдено поле ввода капчи. Попробуйте заново.")

        await asyncio.sleep(0.5)

        # Submit was already clicked via CDP Input events above
        # No need for separate tab.select — the button is in a cross-origin iframe

        await asyncio.sleep(5)  # Wait for captcha validation + SMS trigger

        # DEBUG screenshot
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_5_after_captcha.png"))
        except: pass

        # Check if captcha was wrong (captcha still visible)
        # Note: captcha is in a cross-origin iframe, so document.body.innerText
        # won't contain SmartCaptcha text. Check for iframe presence instead.
        try:
            still_captcha = await safe_evaluate(tab, """
                (function() {
                    var iframes = document.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        if (iframes[i].src && iframes[i].src.indexOf('captcha') > -1) {
                            var r = iframes[i].getBoundingClientRect();
                            if (r.width > 100 && r.height > 100) return true;
                        }
                    }
                    var t = document.body.innerText;
                    return t.includes('SmartCaptcha') || t.includes('Enter the code from the image') || t.includes('Введите код с картинки');
                })()
            """)
            if still_captcha:
                # Captcha still showing — wrong answer or typing failed. Take new screenshot + crop
                import base64
                captcha_path = os.path.join(DATA_DIR, f"login_{user_id}_captcha.png")
                await tab.save_screenshot(captcha_path)
                captcha_b64 = None
                try:
                    from PIL import Image
                    img = Image.open(captcha_path)
                    img_w, img_h = img.size
                    cx, cy = img_w // 2, img_h // 2
                    crop_half_w = min(int(img_w * 0.22), 300)
                    crop_half_h = min(int(img_h * 0.35), 220)
                    cropped = img.crop((max(0, cx - crop_half_w), max(0, cy - crop_half_h),
                                       min(img_w, cx + crop_half_w), min(img_h, cy + crop_half_h)))
                    cropped = cropped.resize((cropped.width * 3, cropped.height * 3), Image.LANCZOS)
                    crop_path = os.path.join(DATA_DIR, f"login_{user_id}_captcha_crop.png")
                    cropped.save(crop_path, 'PNG')
                    with open(crop_path, 'rb') as f:
                        captcha_b64 = base64.b64encode(f.read()).decode('utf-8')
                except Exception:
                    pass
                if not captcha_b64:
                    with open(captcha_path, 'rb') as f:
                        captcha_b64 = base64.b64encode(f.read()).decode('utf-8')
                return {
                    "success": True,
                    "need_captcha": True,
                    "captcha_image": f"data:image/png;base64,{captcha_b64}",
                    "message": "Неверная капча. Попробуйте ещё раз.",
                }
        except Exception:
            pass

        # Check for rate limit
        try:
            page_text = await safe_evaluate(tab, "document.body.innerText")
            if isinstance(page_text, str):
                if 'заблокирован' in page_text or 'суточный лимит' in page_text:
                    try: browser.stop()
                    except: pass
                    _login_sessions.pop(user_id, None)
                    raise HTTPException(status_code=429, detail="Исчерпан суточный лимит SMS. Попробуйте завтра.")
        except HTTPException:
            raise
        except Exception:
            pass

        # Wait up to 30s for SMS code input to appear
        sms_found = False
        for _ in range(30):
            await asyncio.sleep(1)
            try:
                result = await safe_evaluate(tab, """
                    (function() {
                        var sms = document.querySelector('input[name="SMS"]');
                        var smsVisible = sms ? (sms.offsetParent !== null &&
                                                sms.getBoundingClientRect().height > 0) : false;
                        var codeText = document.body.innerText.includes('Введите код');
                        var rateLimit = document.body.innerText.includes('Превышено количество попыток');
                        var dailyBlock = document.body.innerText.includes('заблокирован');
                        if (rateLimit || dailyBlock) return 'RATE_LIMIT';
                        return smsVisible || codeText ? 'OK' : false;
                    })()
                """)
            except Exception:
                result = None
            if result == 'RATE_LIMIT':
                try: browser.stop()
                except: pass
                _login_sessions.pop(user_id, None)
                raise HTTPException(status_code=429, detail="Превышено количество попыток. Попробуйте через 3 минуты.")
            if result == 'OK':
                sms_found = True
                break

        if not sms_found:
            try:
                await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_6_no_sms.png"))
            except: pass
            try: browser.stop()
            except: pass
            _login_sessions.pop(user_id, None)
            raise HTTPException(status_code=500, detail="Не удалось отправить SMS после капчи. Попробуйте позже.")

        # Success! SMS input appeared. Update session state.
        entry["awaiting_captcha"] = False
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_6_sms_ok.png"))
        except: pass

        return {"success": True, "need_pin": False, "message": "SMS отправлено. Введите код из SMS."}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Captcha submit error: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        try: browser.stop()
        except: pass
        _login_sessions.pop(user_id, None)
        raise HTTPException(status_code=500, detail="Ошибка при отправке капчи")


@app.post("/api/auth/verify")
async def auth_verify(req: AuthCodeRequest):
    """Start SMS code verification in background. Returns job_id immediately.
    Poll GET /api/auth/verify/status/{job_id} for progress."""
    import asyncio
    import uuid
    import time as _time

    user_id = req.user_id
    entry = _login_sessions.get(user_id)
    if not entry:
        raise HTTPException(status_code=400, detail="Сессия истекла. Начните заново.")

    # Guard against duplicate calls — if already verified, return cached result
    if entry.get("_verified"):
        logger.info(f"Duplicate verify call for {user_id} — returning cached success")
        return entry["_verified"]

    # If another verify is already in-progress, return existing job_id
    if entry.get("_verify_in_progress") and entry.get("_verify_job_id"):
        logger.info(f"Verify already in-progress for {user_id} — returning existing job_id")
        return {"success": True, "job_id": entry["_verify_job_id"], "message": "Верификация уже выполняется."}

    code = req.code.strip()
    if not code.isdigit() or not (4 <= len(code) <= 8):
        raise HTTPException(status_code=400, detail="Некорректный код")

    # Generate job ID and start background task
    job_id = str(uuid.uuid4())[:8]
    now = _time.time()
    _verify_jobs[job_id] = {
        "status": "starting",
        "message": "Начинаем проверку кода...",
        "result": None,
        "user_id": user_id,
        "created_at": now,
    }

    # Mark as in-progress
    entry["_verify_in_progress"] = True
    entry["_verify_job_id"] = job_id

    # Evict old verify jobs
    stale = [k for k, v in _verify_jobs.items() if now - v.get("created_at", 0) > _VERIFY_JOB_TTL]
    for k in stale:
        _verify_jobs.pop(k, None)

    asyncio.create_task(_run_verify_job(job_id, user_id, code))
    return {"success": True, "job_id": job_id, "message": "Проверяем код..."}


@app.get("/api/auth/verify/status/{job_id}")
async def auth_verify_status(job_id: str):
    """Poll verify job progress. Returns current status and message."""
    job = _verify_jobs.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {
        "status": job["status"],
        "message": job["message"],
        "result": job.get("result"),
    }


async def _run_verify_job(job_id: str, user_id: str, code: str):
    """Background task: type SMS code into Chrome, wait for redirect, extract cookies.
    Updates _verify_jobs[job_id] with progress."""
    import asyncio

    def _update(status: str, message: str):
        _verify_jobs[job_id]["status"] = status
        _verify_jobs[job_id]["message"] = message

    entry = _login_sessions.get(user_id)
    if not entry:
        _update("error", "Сессия истекла. Начните заново.")
        _verify_jobs[job_id]["result"] = {"success": False, "error": "session_expired"}
        return

    browser = entry["browser"]
    tab = entry["tab"]
    try:
        _login_succeeded = False
        _found_error = False
        _verify_ss = None

        _update("checking_session", "Проверяем сессию браузера...")

        # Early check: is Chrome process still alive?
        try:
            await tab.evaluate("1+1")
        except (ConnectionRefusedError, OSError) as _dead_err:
            logger.error(f"Chrome process dead for {user_id}: {_dead_err}")
            _login_sessions.pop(user_id, None)
            _update("error", "Сессия браузера истекла. Нажмите 'Изменить номер' и начните заново.")
            _verify_jobs[job_id]["result"] = {"success": False, "error": "session_expired"}
            return
        except Exception:
            pass  # CDP context stale but Chrome may still be alive — continue

        for _attempt in range(3):
            if _login_succeeded or _found_error:
                break  # Don't retry if we already have a result
            try:
                # First check if the current tab's context is still alive
                try:
                    await tab.evaluate("1+1")
                except Exception as _ctx_err:
                    logger.warning(f"Attempt {_attempt+1}: CDP context dead ({_ctx_err}), refreshing tab from browser targets")
                    try:
                        targets = browser.targets
                        if targets:
                            tab = targets[0]
                            entry["tab"] = tab
                            logger.info(f"Attempt {_attempt+1}: Got fresh tab target, waiting for page to stabilize")
                            await asyncio.sleep(3)
                        else:
                            logger.warning(f"Attempt {_attempt+1}: No browser targets found")
                            await asyncio.sleep(2)
                            continue
                    except Exception as _target_err:
                        logger.warning(f"Attempt {_attempt+1}: Failed to get targets: {_target_err}")
                        await asyncio.sleep(2)
                        continue

                _update("typing_code", "Вводим код...")

                sms_input = await tab.find('input[name="SMS"]', best_match=True, timeout=5)
                if sms_input:
                    import nodriver.cdp.input_ as cdp_input
                    logger.info(f"SMS input found on attempt {_attempt+1}")

                    # Close any popup/modal first
                    await safe_evaluate(tab, """
                        var closeBtn = document.querySelector('.VV_Modal__Close, .modal-close, [class*="close"]');
                        if (closeBtn) closeBtn.click();
                        var overlay = document.querySelector('.VV_Modal__Overlay, .modal-overlay, [class*="overlay"]');
                        if (overlay) overlay.click();
                    """)
                    await asyncio.sleep(0.5)

                    # Focus and clear the SMS input
                    await safe_evaluate(tab, """
                        var inp = document.querySelector('input[name="SMS"]');
                        if (inp) { inp.focus(); inp.click(); inp.value = ''; }
                    """)
                    await asyncio.sleep(0.3)

                    # Type using CDP keyDown/keyUp
                    for digit in code:
                        await tab.send(cdp_input.dispatch_key_event(
                            type_='keyDown', key=digit, text=digit,
                            code=f'Digit{digit}',
                            windows_virtual_key_code=ord(digit),
                            native_virtual_key_code=ord(digit),
                        ))
                        await asyncio.sleep(0.05)
                        await tab.send(cdp_input.dispatch_key_event(
                            type_='keyUp', key=digit,
                            code=f'Digit{digit}',
                            windows_virtual_key_code=ord(digit),
                            native_virtual_key_code=ord(digit),
                        ))
                        await asyncio.sleep(0.15)
                    await asyncio.sleep(0.3)

                    # Also set via JS as backup for React state
                    await safe_evaluate(tab, f"""
                        (function() {{
                            var inp = document.querySelector('input[name="SMS"]');
                            if (!inp) return;
                            var ns = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                            ns.call(inp, '{code}');
                            var t = inp._valueTracker; if (t) t.setValue('');
                            inp.dispatchEvent(new Event('input', {{bubbles:true}}));
                            inp.dispatchEvent(new Event('change', {{bubbles:true}}));
                        }})()
                    """)
                    await asyncio.sleep(0.3)

                    _val = await safe_evaluate(tab, "document.querySelector('input[name=\"SMS\"]')?.value || 'EMPTY'")
                    logger.info(f"SMS input value: {_val}")

                    # Pre-submit screenshot
                    _presub = os.path.join(DATA_DIR, f"verify_presubmit_{user_id}.png")
                    try:
                        await tab.save_screenshot(_presub)
                        logger.info(f"Pre-submit screenshot: {_presub}")
                    except:
                        pass

                    _update("submitting", "Отправляем код...")

                    # Click submit - force-enable if disabled, via JS
                    _btn_state = await safe_evaluate(tab, """
                        (function() {
                            var btns = document.querySelectorAll('button');
                            for (var i = 0; i < btns.length; i++) {
                                var t = btns[i].textContent.trim();
                                if (t.indexOf('Войти') > -1 || t.indexOf('Подтвердить') > -1) {
                                    if (btns[i].disabled) {
                                        btns[i].disabled = false;
                                        btns[i].removeAttribute('disabled');
                                    }
                                    btns[i].click();
                                    return 'clicked:' + t;
                                }
                            }
                            return 'no button';
                        })()
                    """)
                    logger.info(f"Submit button: {_btn_state}")

                    _update("waiting_redirect", "Проверяем код...")

                    # Poll for error/success for 12 seconds
                    _verify_ss = os.path.join(DATA_DIR, f"verify_result_{user_id}.png")
                    for _poll in range(12):
                        await asyncio.sleep(1)
                        _pt = await safe_evaluate(tab, "document.body.innerText") or ""
                        _ptl = _pt.lower() if isinstance(_pt, str) else ""

                        if 'неверный' in _ptl or 'неверн' in _ptl:
                            logger.info(f"Wrong code on poll {_poll+1}")
                            try:
                                await tab.save_screenshot(_verify_ss)
                            except:
                                pass
                            _found_error = True
                            break

                        _url = await safe_evaluate(tab, "window.location.href") or ""
                        if '/personal/' in str(_url) and 'auth' not in str(_url).lower():
                            logger.info(f"Success redirect on poll {_poll+1}")
                            _login_succeeded = True
                            break

                        if _poll == 3:
                            try:
                                await tab.save_screenshot(_verify_ss)
                            except:
                                pass

                    if not _found_error:
                        try:
                            await tab.save_screenshot(_verify_ss)
                        except:
                            pass

                    if _found_error:
                        try:
                            browser.stop()
                        except:
                            pass
                        _login_sessions.pop(user_id, None)
                        _update("done", "Введён неверный код")
                        _verify_jobs[job_id]["result"] = {"success": False, "error": "wrong_code", "message": "Введён неверный код"}
                        return

                else:
                    logger.error(f"SMS input not found on attempt {_attempt+1}")
                    if _attempt >= 2:
                        _update("error", "Не найдено поле ввода SMS. Начните заново.")
                        _verify_jobs[job_id]["result"] = {"success": False, "error": "sms_input_not_found"}
                        return
                    await asyncio.sleep(2)
                    continue

            except Exception as _sms_err:
                logger.warning(f"SMS attempt {_attempt+1} failed: {_sms_err}")
                if _attempt >= 2:
                    err_str = str(_sms_err)
                    if 'Errno 111' in err_str or 'Connect call failed' in err_str or 'ConnectionRefused' in err_str:
                        _update("error", "Сессия браузера истекла. Нажмите 'Изменить номер' и начните заново.")
                        _verify_jobs[job_id]["result"] = {"success": False, "error": "session_expired"}
                    else:
                        _update("error", "Не удалось ввести код. Попробуйте ещё раз.")
                        _verify_jobs[job_id]["result"] = {"success": False, "error": "typing_failed"}
                    return
                await asyncio.sleep(2)

        _update("extracting_cookies", "Сохраняем авторизацию...")

        # Wait 5s for VkusVill page to fully reload and set cookies after redirect.
        await asyncio.sleep(5)
        logger.info("Waited 5s for page to settle, refreshing tab before cookie extraction...")

        # After VkusVill's success redirect, the old tab CDP target often dies.
        try:
            fresh_targets = browser.targets
            if fresh_targets:
                tab = fresh_targets[0]
                entry["tab"] = tab
                _ping = await asyncio.wait_for(tab.evaluate("1+1"), timeout=3)
                logger.info(f"Fresh tab OK (ping={_ping}), extracting cookies...")
            else:
                logger.warning("No browser targets found for cookie extraction")
        except Exception as _tab_err:
            logger.warning(f"Tab refresh failed: {_tab_err}")

        # Cookie extraction
        cdp_cookies = []
        js_parsed = []
        try:
            cdp_cookies = await asyncio.wait_for(browser.cookies.get_all(), timeout=10)
            logger.info(f"browser.cookies.get_all(): {len(cdp_cookies)} cookies")
        except Exception as _e1:
            logger.warning(f"browser.cookies failed: {type(_e1).__name__}: {_e1}")

        # JS document.cookie fallback
        if not cdp_cookies:
            try:
                js_cookies_str = await asyncio.wait_for(
                    tab.evaluate("document.cookie"),
                    timeout=5
                )
                if js_cookies_str and isinstance(js_cookies_str, str) and len(js_cookies_str) > 5:
                    logger.info(f"JS document.cookie: {len(js_cookies_str)} chars")
                    from http.cookies import SimpleCookie
                    sc = SimpleCookie()
                    sc.load(js_cookies_str)
                    js_parsed = [
                        {"name": k, "value": v.value, "domain": ".vkusvill.ru", "path": "/",
                         "secure": False, "httpOnly": False, "expiry": None}
                        for k, v in sc.items()
                    ]
                    logger.info(f"JS parsed: {len(js_parsed)} cookies")
            except Exception as _e2:
                logger.warning(f"JS document.cookie failed: {_e2}")

        # Build cookies_list
        if cdp_cookies:
            cookies_list = []
            for c in cdp_cookies:
                if isinstance(c, dict):
                    cookies_list.append({
                        "name": c.get("name", ""),
                        "value": c.get("value", ""),
                        "domain": c.get("domain", ""),
                        "path": c.get("path", "/"),
                        "secure": c.get("secure", False),
                        "httpOnly": c.get("httpOnly", False),
                        "expiry": int(c["expires"]) if c.get("expires") and c["expires"] > 0 else None,
                    })
                else:
                    cookies_list.append({
                        "name": c.name,
                        "value": c.value,
                        "domain": c.domain,
                        "path": c.path,
                        "secure": c.secure,
                        "httpOnly": getattr(c, "http_only", False),
                        "expiry": int(c.expires) if getattr(c, "expires", None) else None,
                    })
        elif js_parsed:
            cookies_list = js_parsed
        else:
            cookies_list = []

        # Verify login actually succeeded before saving cookies
        cookie_map = {c["name"]: c["value"] for c in cookies_list}
        is_authenticated = cookie_map.get("UF_USER_AUTH") == "Y"

        if not is_authenticated and not _login_succeeded:
            logger.warning(f"Login failed for {entry.get('phone', user_id)}: UF_USER_AUTH={cookie_map.get('UF_USER_AUTH', 'missing')} — NOT saving cookies")
            _update("done", "Не удалось подтвердить вход.")
            _verify_jobs[job_id]["result"] = {"success": False, "message": "Не удалось подтвердить вход. VkusVill не принял код — попробуйте ещё раз."}
            return
        if not is_authenticated and _login_succeeded:
            logger.info(f"VkusVill redirected (login OK) but cookies incomplete for {entry.get('phone', user_id)}")

        # Save cookies by PHONE
        phone_10 = entry.get("phone", "")
        if phone_10:
            cookies_path = _phone_cookies_path(phone_10)
            if entry.get("force_sms"):
                bak = cookies_path + ".bak"
                if os.path.exists(bak):
                    os.remove(bak)
            os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
            with open(cookies_path, 'w', encoding='utf-8') as f:
                json.dump(cookies_list, f, indent=2)
            _save_user_phone_mapping(user_id, phone_10)
            logger.info(f"Saved {len(cookies_list)} cookies for phone {phone_10} (UF_USER_AUTH=Y)")
        else:
            cookies_path = get_user_cookies_path(int(user_id) if user_id.isdigit() else user_id)
            os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
            with open(cookies_path, 'w', encoding='utf-8') as f:
                json.dump(cookies_list, f, indent=2)
            logger.info(f"Saved {len(cookies_list)} cookies for user {user_id} (UF_USER_AUTH=Y)")

        _result = {
            "success": True,
            "need_set_pin": bool(phone_10),
            "phone": phone_10,
            "message": "Авторизация успешна. Установите PIN.",
            "profile_dir": entry.get("profile_dir"),
        }
        entry["_verified"] = _result
        _update("done", "Авторизация успешна!")
        _verify_jobs[job_id]["result"] = _result

    except Exception as e:
        import traceback
        logger.error(f"Verify job error: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        _update("error", "Ошибка при проверке кода. Попробуйте ещё раз.")
        _verify_jobs[job_id]["result"] = {"success": False, "error": "internal_error"}
    finally:
        try:
            browser.stop()
        except Exception:
            pass
        _entry = _login_sessions.pop(user_id, None)
        if _entry and _entry.get("proc"):
            try:
                _entry["proc"].kill()
            except Exception:
                pass


# ─── Cart Endpoints ───────────────────────────────────────────────────────────

# ─── PIN Auth Endpoints ───────────────────────────────────────────────────────

@app.post("/api/auth/verify-pin")
def auth_verify_pin(req: AuthPinRequest):
    """Verify PIN for quick re-login (no browser needed!)."""
    phone = _normalize_phone(req.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Некорректный формат телефона")

    pin_data = _load_pin_data(phone)
    if not pin_data:
        raise HTTPException(status_code=404, detail="PIN не найден. Войдите через SMS.")

    # Check lockout
    if pin_data.get("locked_until", 0) > _time.time():
        remaining = int(pin_data["locked_until"] - _time.time())
        raise HTTPException(status_code=429, detail=f"Слишком много попыток. Подождите {remaining} сек.")

    # Verify PIN — R2-6: Try salted hash first, then unsalted for backward compat
    salted_hash = hashlib.sha256((req.pin + phone).encode()).hexdigest()
    unsalted_hash = hashlib.sha256(req.pin.encode()).hexdigest()
    pin_matches = (salted_hash == pin_data["pin_hash"] or unsalted_hash == pin_data["pin_hash"])
    if not pin_matches:
        # Increment attempts
        pin_data["attempts"] = pin_data.get("attempts", 0) + 1
        remaining = 3 - pin_data["attempts"]
        if remaining <= 0:
            # Lock for 5 minutes
            pin_data["locked_until"] = _time.time() + 300
            pin_data["attempts"] = 0
            p = os.path.join(_phone_auth_dir(phone), "pin.json")
            with open(p, 'w', encoding='utf-8') as f:
                json.dump(pin_data, f, indent=2)
            raise HTTPException(status_code=429, detail="PIN заблокирован на 5 минут. Попробуйте позже или войдите через SMS.")
        # Save attempts
        p = os.path.join(_phone_auth_dir(phone), "pin.json")
        with open(p, 'w', encoding='utf-8') as f:
            json.dump(pin_data, f, indent=2)
        raise HTTPException(status_code=401, detail=f"Неверный PIN. Осталось {remaining} {'попытка' if remaining == 1 else 'попытки'}")

    # PIN correct — reset attempts
    pin_data["attempts"] = 0
    pin_data["locked_until"] = 0
    p = os.path.join(_phone_auth_dir(phone), "pin.json")
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(pin_data, f, indent=2)

    # Check cookies exist
    cp = _phone_cookies_path(phone)
    if not os.path.exists(cp):
        # Try .bak
        bak = cp + ".bak"
        if os.path.exists(bak):
            os.rename(bak, cp)
        else:
            raise HTTPException(status_code=404, detail="Cookies не найдены. Войдите через SMS.")

    # Save user→phone mapping
    _save_user_phone_mapping(req.user_id, phone)
    return {"success": True, "message": "Авторизация успешна"}


@app.post("/api/auth/set-pin")
def auth_set_pin(req: AuthSetPinRequest):
    """Set a 4-digit PIN after first SMS login."""
    phone = _normalize_phone(req.phone)
    if not phone:
        raise HTTPException(status_code=400, detail="Некорректный формат телефона")

    if not req.pin or len(req.pin) != 4 or not req.pin.isdigit():
        raise HTTPException(status_code=400, detail="PIN должен быть 4 цифры")

    _save_pin_data(phone, req.pin, req.user_id)
    _save_user_phone_mapping(req.user_id, phone)
    return {"success": True, "message": "PIN установлен"}


class TransferMappingRequest(BaseModel):
    from_user_id: str
    to_user_id: str

@app.post("/api/auth/transfer-mapping")
def auth_transfer_mapping(req: TransferMappingRequest):
    """BUG-A fix: Copy user→phone mapping from guest to linked Telegram ID.
    Called during account linking so auth persists after page reload."""
    phone = _get_phone_for_user(req.from_user_id)
    if phone:
        _save_user_phone_mapping(req.to_user_id, phone)
        return {"success": True, "message": "Mapping transferred"}
    return {"success": False, "message": "No mapping found for source user"}


@app.post("/api/auth/logout")
def auth_logout(req: AuthLogoutRequest):
    """Logout: rename cookies to .bak (preserving for PIN re-login).
    NOTE (R2-10): .bak file allows quick re-auth via PIN without new SMS.
    If you need true session revocation, delete the .bak file too."""
    phone = _get_phone_for_user(req.user_id)
    if phone:
        cp = _phone_cookies_path(phone)
        bak = cp + ".bak"
        if os.path.exists(cp):
            if os.path.exists(bak):
                try:
                    os.remove(bak)
                except Exception:
                    pass
            try:
                os.rename(cp, bak)
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Logout rename error: {e}")
    return {"success": True, "message": "Вы вышли из аккаунта"}


# ─── Cart Endpoints ───────────────────────────────────────────────────────────

@app.post("/api/cart/add")
def cart_add_endpoint(req: CartAddRequest, request: Request):
    """Add a product to the user's VkusVill cart."""
    _validate_user_header(request, str(req.user_id))
    # Try phone-based cookies first, fallback to legacy user_id cookies
    phone = _get_phone_for_user(str(req.user_id))
    if phone:
        cookies_path = _phone_cookies_path(phone)
    else:
        cookies_path = get_user_cookies_path(int(req.user_id) if req.user_id.isdigit() else req.user_id)
    if not os.path.exists(cookies_path):
        raise HTTPException(status_code=401, detail="Вы не авторизованы. Войдите в аккаунт.")

    try:
        cart = VkusVillCart(cookies_path=cookies_path)
        try:
            result = cart.add(product_id=req.product_id, price_type=req.price_type, is_green=req.is_green)
        finally:
            cart.close()

        if result.get("success"):
            return {
                "success": True,
                "cart_items": result.get("cart_items"),
                "cart_total": result.get("cart_total")
            }
        else:
            error = result.get("error", "Unknown API error")
            raise HTTPException(status_code=400, detail=error)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cart add error: {e}")
        raise HTTPException(status_code=500, detail="Failed to communicate with Cart API")


@app.get("/api/cart/items/{user_id}")
def cart_items_endpoint(user_id: str, request: Request):
    """Get current VkusVill cart items for a user."""
    _validate_user_header(request, user_id)
    phone = _get_phone_for_user(user_id)
    if phone:
        cookies_path = _phone_cookies_path(phone)
    else:
        cookies_path = get_user_cookies_path(int(user_id) if user_id.isdigit() else user_id)
    if not os.path.exists(cookies_path):
        raise HTTPException(status_code=401, detail="Не авторизованы")

    if _vkusvill_backoff_active():
        return _fallback_cart_items("VkusVill temporarily unreachable")

    try:
        cart = VkusVillCart(cookies_path=cookies_path)
        try:
            data = cart.get_cart()
        finally:
            cart.close()

        if not data.get("success"):
            error = str(data.get("error", "Cart fetch failed"))
            lowered = error.lower()
            if "timeout" in lowered or "timed out" in lowered or "max retries exceeded" in lowered or "failed to fetch cart" in lowered:
                _mark_vkusvill_backoff()
                logger.warning(f"Cart items fallback for {user_id}: {error}")
                return _fallback_cart_items(error)
            raise HTTPException(status_code=502, detail=error)

        # VkusVill sometimes returns {} for empty basket, or a dict of items instead of list
        raw_items = data.get('items', [])
        if isinstance(raw_items, dict):
            items_list = list(raw_items.values())
        elif isinstance(raw_items, list):
            items_list = raw_items
        else:
            items_list = []
            
        return {
            "items_count": data.get("items_count", 0),
            "total_price": data.get("total_price", 0),
            "items": [
                {
                    "id": item.get("PRODUCT_ID") if isinstance(item, dict) else None,
                    "name": item.get("NAME") if isinstance(item, dict) else "",
                    "price": float(item.get("PRICE", 0)) if isinstance(item, dict) else 0,
                    "old_price": float(item.get("BASE_PRICE", 0)) if isinstance(item, dict) else 0,
                    "quantity": int(item.get("Q", 0)) if isinstance(item, dict) else 0,
                    "image": item.get("DETAIL_PICTURE_SRC") if isinstance(item, dict) else "",
                    "can_buy": str(item.get("CAN_BUY", "")).upper() in ['Y', 'TRUE', '1'] if isinstance(item, dict) else False,
                    "max_q": int(item.get("MAX_Q", 0)) if isinstance(item, dict) and item.get("MAX_Q") else 0,
                }
                for item in items_list if isinstance(item, dict)
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cart items error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка загрузки корзины")


class CartRemoveRequest(BaseModel):
    user_id: str
    product_id: int


@app.post("/api/cart/remove")
def cart_remove_endpoint(req: CartRemoveRequest, request: Request):
    """Remove a product from the user's VkusVill cart."""
    _validate_user_header(request, str(req.user_id))
    phone = _get_phone_for_user(str(req.user_id))
    if phone:
        cookies_path = _phone_cookies_path(phone)
    else:
        cookies_path = get_user_cookies_path(int(req.user_id) if req.user_id.isdigit() else req.user_id)
    if not os.path.exists(cookies_path):
        raise HTTPException(status_code=401, detail="Не авторизованы")

    try:
        cart = VkusVillCart(cookies_path=cookies_path)
        try:
            result = cart.remove(product_id=req.product_id)
        finally:
            cart.close()
        return result
    except Exception as e:
        logger.error(f"Cart remove error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка удаления из корзины")


class CartClearRequest(BaseModel):
    user_id: str


@app.post("/api/cart/clear")
def cart_clear_endpoint(req: CartClearRequest, request: Request):
    """Clear all items from the user's VkusVill cart."""
    _validate_user_header(request, str(req.user_id))
    user_id = req.user_id
    phone = _get_phone_for_user(user_id)
    if phone:
        cookies_path = _phone_cookies_path(phone)
    else:
        cookies_path = get_user_cookies_path(int(user_id) if user_id.isdigit() else user_id)
    if not os.path.exists(cookies_path):
        raise HTTPException(status_code=401, detail="Не авторизованы")

    try:
        cart = VkusVillCart(cookies_path=cookies_path)
        try:
            result = cart.clear_all()
        finally:
            cart.close()
        return result
    except Exception as e:
        logger.error(f"Cart clear error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка очистки корзины")


# ─── Admin Endpoints ──────────────────────────────────────────────────────────

@app.get("/admin/status")
def admin_get_status(token: Optional[str] = Header(None, alias="X-Admin-Token")):
    """Return current scraper status and product counts."""
    _require_token(token)
    counts = {"green": 0, "red": 0, "yellow": 0, "total": 0, "updatedAt": None, "greenLiveCount": 0}
    if os.path.exists(PROPOSALS_PATH):
        try:
            with open(PROPOSALS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            products = data.get("products", [])
            counts["total"] = len(products)
            counts["green"] = sum(1 for p in products if p.get("type") == "green")
            counts["red"] = sum(1 for p in products if p.get("type") == "red")
            counts["yellow"] = sum(1 for p in products if p.get("type") == "yellow")
            counts["updatedAt"] = data.get("updatedAt")
            counts["greenLiveCount"] = data.get("greenLiveCount", 0)
        except Exception:
            pass
    # Technical cookie health
    tech_cookies_path = os.path.join(DATA_DIR, "cookies.json")
    cookie_health = {"exists": False, "age_days": None, "expired": False}
    if os.path.exists(tech_cookies_path):
        cookie_health["exists"] = True
        age_days = (_time.time() - os.path.getmtime(tech_cookies_path)) / 86400
        cookie_health["age_days"] = round(age_days, 1)
        cookie_health["expired"] = age_days > 60
    cookie_health["green_missing"] = not os.path.exists(os.path.join(DATA_DIR, "green_products.json"))

    return {"scrapers": scraper_status, "data": counts, "techCookies": cookie_health}


@app.post("/api/admin/tech-login")
async def admin_tech_login(req: TechLoginRequest, token: Optional[str] = Header(None, alias="X-Admin-Token")):
    """Start tech account login via nodriver (admin-only). Saves to data/cookies.json.
    Reuses the existing auth_login flow with a synthetic user_id='__tech__'.
    """
    _require_token(token)

    phone_raw = _normalize_phone(req.phone)
    if not phone_raw:
        raise HTTPException(status_code=400, detail="Некорректный формат телефона")

    # Reuse the existing auth_login endpoint logic which already handles
    # Windows event loop, nodriver patching, rate limits, etc.
    fake_req = AuthPhoneRequest(user_id="__tech__", phone=phone_raw, force_sms=True)
    result = await auth_login(fake_req)
    return {"success": result.get("success", False), "message": result.get("message", "")}


@app.post("/api/admin/tech-verify")
async def admin_tech_verify(req: TechCodeRequest, token: Optional[str] = Header(None, alias="X-Admin-Token")):
    """Submit SMS code for tech account, save cookies to data/cookies.json.
    Reuses auth_verify with user_id='__tech__', then copies cookies to data/cookies.json.
    """
    _require_token(token)

    # Reuse existing auth_verify which handles nodriver code submission
    fake_req = AuthCodeRequest(user_id="__tech__", code=req.code)
    result = await auth_verify(fake_req)

    if result.get("success"):
        # auth_verify saved cookies to data/auth/{phone}/cookies.json
        # Copy them to data/cookies.json for the green scraper
        phone = result.get("phone") or _login_sessions.get("__tech__", {}).get("phone", "")
        if phone:
            src = _phone_cookies_path(phone)
            dst = os.path.join(DATA_DIR, "cookies.json")
            if os.path.exists(src):
                import shutil
                shutil.copy2(src, dst)
                logger.info(f"Tech verify: copied {src} -> {dst}")
        profile_dir = result.get("profile_dir")
        if profile_dir:
            try:
                if _copy_tech_profile(profile_dir):
                    logger.info(f"Tech verify: copied profile {profile_dir} -> {TECH_PROFILE_DIR}")
            except Exception as exc:
                logger.warning(f"Tech verify: failed to copy profile from {profile_dir}: {exc}")
        return {"success": True, "message": "Техническая авторизация успешна. Куки обновлены."}

    return {"success": False, "message": result.get("message", "Не удалось подтвердить вход")}


@app.post("/api/admin/run/{scraper}")
def admin_run_scraper(
    scraper: str,
    background_tasks: BackgroundTasks,
    token: Optional[str] = Header(None, alias="X-Admin-Token"),
):
    """Run a specific scraper: green | red | yellow | merge | login | all"""
    # Keep categories public even though this generic route is declared first.
    if scraper == "categories":
        return admin_run_categories(token=token)

    _require_token(token)

    script_map = {
        "green":      os.path.join(BASE_PROJECT_DIR, "scrape_green.py"),
        "red":        os.path.join(BASE_PROJECT_DIR, "scrape_red.py"),
        "yellow":     os.path.join(BASE_PROJECT_DIR, "scrape_yellow.py"),
        "merge":      os.path.join(BASE_PROJECT_DIR, "scrape_merge.py"),
        "login":      os.path.join(BASE_PROJECT_DIR, "login.py"),
    }

    if scraper == "all":
        # BACK-01 / BUG-046: Run all scrapers then merge ONCE after all complete.
        # Previously each ran independently with no merge.
        def run_all_with_merge():
            succeeded = []
            for name in ["green", "red", "yellow"]:
                _run_script(name, script_map[name])
                # Wait for completion
                while scraper_status[name]["running"]:
                    _time.sleep(0.2)
                if scraper_status[name].get("exit_code") == 0:
                    succeeded.append(name)
            # Merge if at least one scraper succeeded
            if succeeded:
                _run_script("merge", script_map["merge"])
                log_buffer.append(f"[all] Auto-merge after {len(succeeded)}/3 scrapers: {succeeded}")
            else:
                log_buffer.append("[all] Skipping merge — all scrapers failed")

        background_tasks.add_task(run_all_with_merge)
        return {"started": ["green", "red", "yellow"], "message": "All scrapers queued (auto-merge on completion)"}

    if scraper not in script_map:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown scraper '{scraper}'. Use: green, red, yellow, merge, login, all",
        )

    def worker_with_merge():
        # First run the requested script
        _run_script(scraper, script_map[scraper])
        while scraper_status[scraper]["running"]:
            _time.sleep(0.2)

        if scraper_status[scraper].get("exit_code") == 0:
            # Only merge after a successful scraper run.
            _run_script("merge", script_map["merge"])
        else:
            log_buffer.append(
                f"[{scraper}] Skipping auto-merge because scraper finished with exit {scraper_status[scraper].get('exit_code')}"
            )

    background_tasks.add_task(worker_with_merge)
    return {"started": scraper, "message": f"{scraper} scraper started in background (auto-merge on completion)"}


@app.post("/api/admin/run/categories")
def admin_run_categories(
    token: Optional[str] = Header(None, alias="X-Admin-Token"),
):
    """Run category scraper + auto-merge in sequence (background).
    Populates category_db.json then rebuilds proposals.json with new categories.
    """
    # No token required — this is a user-facing feature (button on main page)
    lock = _run_locks["categories"]
    with lock:
        if scraper_status["categories"]["running"]:
            return {"started": False, "message": "Categories scraper already running"}
        scraper_status["categories"]["running"] = True
        scraper_status["categories"]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        scraper_status["categories"]["last_output"] = ""

    categories_script = os.path.join(BASE_PROJECT_DIR, "scrape_categories.py")
    merge_script = os.path.join(BASE_PROJECT_DIR, "scrape_merge.py")

    def worker():
        lines: list = []
        try:
            # Phase 1: build category_db.json
            proc = subprocess.Popen(
                [sys.executable, categories_script],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=BASE_PROJECT_DIR, text=True, encoding="utf-8", errors="replace",
            )
            for line in proc.stdout:
                line = line.rstrip()
                lines.append(line)
                log_buffer.append(f"[categories] {line}")
                scraper_status["categories"]["last_output"] = "\n".join(lines[-40:])
            proc.wait()
            scraper_status["categories"]["exit_code"] = proc.returncode
            log_buffer.append(f"[categories] Finished (exit {proc.returncode}), auto-merging...")
            lines.append(f"[categories] Finished (exit {proc.returncode}), auto-merging...")
            scraper_status["categories"]["last_output"] = "\n".join(lines[-40:])

            # Phase 2: re-merge so proposals.json picks up new categories
            proc2 = subprocess.Popen(
                [sys.executable, merge_script],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                cwd=BASE_PROJECT_DIR, text=True, encoding="utf-8", errors="replace",
            )
            for line in proc2.stdout:
                line = line.rstrip()
                lines.append(line)
                log_buffer.append(f"[categories/merge] {line}")
                scraper_status["categories"]["last_output"] = "\n".join(lines[-40:])
            proc2.wait()
            scraper_status["categories"]["exit_code"] = proc2.returncode if proc.returncode == 0 else proc.returncode
            log_buffer.append(f"[categories] Auto-merge done (exit {proc2.returncode})")
            lines.append(f"[categories] Auto-merge done (exit {proc2.returncode})")
            scraper_status["categories"]["last_output"] = "\n".join(lines[-40:])
        except Exception as exc:
            log_buffer.append(f"[categories] Exception: {exc}")
            scraper_status["categories"]["exit_code"] = -1
            lines.append(f"[categories] Exception: {exc}")
            scraper_status["categories"]["last_output"] = "\n".join(lines[-40:])
        finally:
            scraper_status["categories"]["running"] = False
            scraper_status["categories"]["last_output"] = "\n".join(lines[-40:])

    threading.Thread(target=worker, daemon=True).start()
    return {"started": "categories", "message": "Category scraper started (auto-merge on completion)"}


@app.get("/api/admin/run/categories/status")
def admin_categories_status():
    """Return current status of the categories scraper."""
    return scraper_status["categories"]


@app.get("/admin/logs")
def admin_get_logs(
    n: int = Query(100, ge=1, le=300),
    token: Optional[str] = Header(None, alias="X-Admin-Token"),
):
    """Return last N log lines from scheduler.log + in-memory buffer."""
    _require_token(token)
    lines = []
    # Primary source: scheduler.log (where the scheduler service writes)
    scheduler_log = os.path.join(BASE_PROJECT_DIR, "logs", "scheduler.log")
    if os.path.exists(scheduler_log):
        try:
            with open(scheduler_log, "r", encoding="utf-8", errors="replace") as f:
                # Read last N lines efficiently
                all_lines = f.readlines()
                lines = [l.rstrip() for l in all_lines[-n:]]
        except Exception:
            pass
    # Supplement with in-memory buffer (from admin-triggered runs)
    buffer_lines = list(log_buffer)
    if buffer_lines:
        lines.extend(buffer_lines[-n:])
    # Return last N combined
    lines = lines[-n:]
    return {"lines": lines, "total": len(lines)}


@app.get("/admin/proxy-stats")
def admin_proxy_stats(
    token: Optional[str] = Header(None, alias="X-Admin-Token"),
):
    """Return proxy pool statistics for the admin dashboard."""
    _require_token(token)
    cache_file = os.path.join(BASE_PROJECT_DIR, "data", "working_proxies.json")
    try:
        with open(cache_file, "r") as f:
            cache = json.load(f)
    except Exception:
        return {"pool_size": 0, "proxies": [], "cache_age": None, "healthy": False}

    proxies_raw = cache.get("proxies", [])
    last_refresh = cache.get("last_refresh")

    # Calculate cache age
    cache_age_min = None
    if last_refresh:
        try:
            from datetime import datetime
            lr = datetime.fromisoformat(last_refresh)
            cache_age_min = round((datetime.now() - lr).total_seconds() / 60, 1)
        except Exception:
            pass

    # Build proxy list with stats
    proxies_out = []
    for p in proxies_raw:
        tested_ago = None
        if p.get("tested_at"):
            try:
                from datetime import datetime
                t = datetime.fromisoformat(p["tested_at"])
                tested_ago = round((datetime.now() - t).total_seconds() / 60, 1)
            except Exception:
                pass
        proxies_out.append({
            "addr": p.get("addr", "?"),
            "speed": round(p.get("speed", 0), 2),
            "protocol": p.get("protocol", p.get("proto", "socks5")),
            "alive": p.get("alive", True),
            "tested_ago_min": tested_ago,
            "tested_at": p.get("tested_at", "?"),
        })

    return {
        "pool_size": len(proxies_raw),
        "min_healthy": 7,
        "healthy": len(proxies_raw) >= 7,
        "cache_age_min": cache_age_min,
        "last_refresh": last_refresh,
        "proxies": proxies_out,
    }


@app.get("/admin/proxy-history")
def admin_proxy_history(
    token: Optional[str] = Header(None, alias="X-Admin-Token"),
):
    """Return historical proxy stats (found/removed/timeouts per day/week/month)."""
    _require_token(token)
    try:
        import sys
        sys.path.insert(0, BASE_PROJECT_DIR)
        from proxy_manager import ProxyManager
        return ProxyManager.get_event_stats()
    except Exception as e:
        return {"error": str(e), "periods": {}, "recent": []}


# ─── Admin Panel (HTML served from backend/admin.html) ───────────────────────

ADMIN_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin.html")


@app.get("/admin")
def admin_panel_page():
    """Serve the admin panel. Accessible from any URL (AWS/localhost).
    HTML lives in backend/admin.html — pure CSS/ES5, no CDN dependencies.
    """
    if os.path.exists(ADMIN_HTML_PATH):
        return FileResponse(
            ADMIN_HTML_PATH,
            media_type="text/html; charset=utf-8",
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
    return HTMLResponse("<h2>admin.html not found next to main.py</h2>", status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, loop="asyncio")
