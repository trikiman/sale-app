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
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Query, Body, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse, StreamingResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import hashlib
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
from bot.auth import get_user_cookies_path, normalize_phone as _bot_normalize_phone
import config

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

app = FastAPI(title="VkusVill Mini App API", version="1.0.0")

# CORS for mini app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
        "https://web.telegram.org",
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
    import tempfile, shutil
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
    if not ADMIN_TOKEN or not token or token != ADMIN_TOKEN:
        logger.warning("Admin auth failed: token mismatch")
        raise HTTPException(status_code=403, detail="Invalid admin token")


def _validate_user_header(request: Request, expected_user_id: str):
    """BUG-038/039: Lightweight IDOR protection.
    Requires X-Telegram-User-Id header to match the user_id in URL/body.
    Prevents casual IDOR where attacker guesses another user's Telegram ID."""
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
    try:
        import httpx
        async with httpx.AsyncClient(
            proxy="socks5://127.0.0.1:10811",
            timeout=10,
            follow_redirects=True,
        ) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept": "text/html",
            })
            if resp.status_code == 200 and len(resp.text) > 500:
                html = resp.text
                logger.info(f"Product {product_id}: fetched {len(html)} bytes via HTTP in {resp.elapsed.total_seconds():.1f}s")
    except Exception as e:
        logger.warning(f"Product {product_id}: HTTP fetch failed ({e}), trying Chrome fallback")

    # Fallback to Chrome worker if HTTP failed
    if not html:
        try:
            html = await detail_service.fetch_product_html(url)
        except Exception as e:
            logger.warning(f"Product details Chrome fetch failed for {product_id}: {e}")
            return _fallback_product_details(product_id, product, str(e))

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


@app.get("/api/img")
async def proxy_image(url: str = ""):
    """Proxy VkusVill images to bypass CDN hotlink/ORB blocking."""
    import httpx
    from urllib.parse import urlparse
    if not url:
        raise HTTPException(status_code=400, detail="Missing url parameter")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.hostname != "img.vkusvill.ru":
        raise HTTPException(status_code=400, detail="Invalid image URL")
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(url, headers={
                "Referer": "https://vkusvill.ru/",
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            })
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="Image fetch failed")
            ct = resp.headers.get("content-type", "image/webp")
            return Response(
                content=resp.content,
                media_type=ct,
                headers={"Cache-Control": "public, max-age=86400"},
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
                    import time; time.sleep(0.5)  # Retry once after brief pause
                else:
                    raise HTTPException(status_code=500, detail="Invalid JSON data")
        # Live staleness: check source file ages at request time (not baked merge-time value)
        STALE_MINUTES = 10
        stale_files = []
        for color in ('green', 'red', 'yellow'):
            src = os.path.join(DATA_DIR, f"{color}_products.json")
            if os.path.exists(src):
                age_min = (_time.time() - os.path.getmtime(src)) / 60
                if age_min > STALE_MINUTES:
                    stale_files.append(f"{color} ({age_min:.0f}m)")
        data["dataStale"] = len(stale_files) > 0
        data["staleInfo"] = stale_files if stale_files else None
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
    import nodriver as uc
    result = await tab.evaluate(js_code)
    # Check for ExceptionDetails in the result (nodriver/CDP specific)
    if isinstance(result, dict) and 'exceptionDetails' in result:
        ex = result['exceptionDetails']['exception']
        msg = ex.get('description', 'Unknown JS error')
        logger.error(f"JS Eval Error: {msg}\nCode: {js_code}")
        raise Exception(f"JavaScript error: {msg}")
    return result


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
    """Start login via nodriver: navigate to /personal/, fill phone, wait for SMS."""
    import nodriver as uc
    import asyncio
    import time as _time
    import sys

    # R2-4: Cleanup old debug screenshots (older than 1 hour)
    _cleanup_debug_screenshots()

    # Patch nodriver Config to include LocalNetworkAccessChecks in --disable-features
    # R2-45: Guard patch to apply only once
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

    # Check if this phone already has valid cookies (or .bak from logout) + PIN (skip browser!)
    _cookies_path = _phone_cookies_path(phone_raw)
    _has_cookies_or_bak = os.path.exists(_cookies_path) or os.path.exists(_cookies_path + ".bak")
    if not req.force_sms and _has_cookies_or_bak:
        pin_data = _load_pin_data(phone_raw)
        if pin_data and pin_data.get("pin_hash"):
            # Save user→phone mapping
            _save_user_phone_mapping(user_id, phone_raw)
            return {"success": True, "need_pin": True, "message": "Введите PIN-код"}

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
    _chrome_proc = None  # Only set on Windows
    _user_data_dir = None
    try:
        import tempfile, subprocess as _subp, socket as _socket

        # Launch a SEPARATE temporary Chrome for login (don't touch scraper Chrome)
        # Fresh profile = no cookies = VkusVill login form shown directly
        def _find_free_port():
            with _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM) as s:
                s.bind(('127.0.0.1', 0))
                return s.getsockname()[1]

        _debug_port = _find_free_port()
        _user_data_dir = tempfile.mkdtemp(prefix='uc_login_')

        if sys.platform != 'win32':
            from chrome_stealth import find_chrome
            _chrome_path = find_chrome()
            if not _chrome_path:
                raise RuntimeError("Chrome not found")
            _chrome_proc = _subp.Popen([
                _chrome_path,
                f'--remote-debugging-port={_debug_port}',
                f'--user-data-dir={_user_data_dir}',
                '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                '--headless=new', '--disable-software-rasterizer',
                '--disable-blink-features=AutomationControlled',
                '--disable-features=IsolateOrigins,site-per-process',
                '--window-size=1280,720', '--lang=ru-RU,ru',
                '--no-first-run', '--no-default-browser-check',
                'about:blank',
            ], stdout=_subp.DEVNULL, stderr=_subp.DEVNULL)
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

        await asyncio.sleep(3)
        browser = await uc.Browser.create(host='127.0.0.1', port=_debug_port)
        browser._process_pid = _chrome_proc.pid

        # Fresh profile — no cookies needed to clear, go straight to /personal/
        tab = await browser.get('https://vkusvill.ru/personal/')
        await asyncio.sleep(5)  # Wait for page load

        # DEBUG: Initial state
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_1_init.png"))
        except: pass

        # BUG-026: Bypass the strict phone mask physically
        # React aggressive masks often block JS focus or `.value` setters.

        # 1. Get coordinates of the input box and click it to focus
        input_box = await tab.select('input.js-user-form-checksms-api-phone1', timeout=2)
        if not input_box:
            input_box = await tab.select('input[name="USER_PHONE"]', timeout=2)
            
        if input_box:
            # Physically click the center of the element to trigger React focus events
            await input_box.mouse_click()
            await asyncio.sleep(0.5)

            # 2. Type cleanly using raw CDP to guarantee realistic typing speed
            for digit in phone_raw:
                await tab.send(uc.cdp.input_.dispatch_key_event(
                    type_='keyDown',
                    key=digit,
                    text=digit,
                    code=f'Digit{digit}',
                    windows_virtual_key_code=ord(digit),
                    native_virtual_key_code=ord(digit),
                ))
                await asyncio.sleep(0.05)
                await tab.send(uc.cdp.input_.dispatch_key_event(
                    type_='keyUp',
                    key=digit,
                    code=f'Digit{digit}',
                    windows_virtual_key_code=ord(digit),
                    native_virtual_key_code=ord(digit),
                ))
                await asyncio.sleep(0.2)  # Give mask time to format the number
            await asyncio.sleep(1.0)
        else:
            logger.error("Could not find phone input box on VkusVill login page")

        # DEBUG: After phone entry
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_2_phone.png"))
        except: pass

        # 3. Locate the submit button and click it naturally
        # If the mask accepted the input, this button should be enabled.
        submit_btn = await tab.select('button.js-user-form-submit-btn', timeout=2)
        if submit_btn:
            # Force enable just in case React is lagging
            await tab.evaluate("document.querySelector('button.js-user-form-submit-btn').disabled = false;")
            await tab.evaluate("document.querySelector('button.js-user-form-submit-btn').classList.remove('disabled');")
            await submit_btn.click()
        else:
            logger.error("Could not find submit button on VkusVill login page")

        await asyncio.sleep(5)  # Wait for SMS trigger or captcha
        
        # DEBUG: After click
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_3_after_click.png"))
        except: pass

        # Check for CAPTCHA (Yandex SmartCaptcha) — appears as overlay popup
        captcha_detected = False
        try:
            captcha_result = await safe_evaluate(tab, """
                (function() {
                    var html = document.documentElement.outerHTML.toLowerCase();
                    // Check if page HTML contains captcha-related content
                    if (html.includes('smartcaptcha') || html.includes('captcha__image') ||
                        html.includes('enter the code from the image') ||
                        html.includes('введите код с картинки')) {
                        return 'CAPTCHA_HTML';
                    }
                    // Check for captcha iframe
                    var iframes = document.querySelectorAll('iframe');
                    for (var i = 0; i < iframes.length; i++) {
                        if (iframes[i].src && iframes[i].src.includes('captcha')) return 'CAPTCHA_IFRAME';
                    }
                    // Check body text
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
            # Take full page screenshot for captcha
            try:
                captcha_path = os.path.join(DATA_DIR, f"login_{user_id}_captcha.png")
                await tab.save_screenshot(captcha_path)
                with open(captcha_path, 'rb') as f:
                    captcha_b64 = base64.b64encode(f.read()).decode('utf-8')
            except Exception as _e:
                logger.error(f"Captcha screenshot failed: {_e}")
                captcha_b64 = None

            if captcha_b64:
                # Save session for captcha submission — don't close Chrome!
                _login_sessions[user_id] = {
                    "browser": browser,
                    "tab": tab,
                    "phone": phone_raw,
                    "force_sms": req.force_sms,
                    "created_at": _time.time(),
                    "proc": _chrome_proc,
                    "profile_dir": _user_data_dir,
                    "awaiting_captcha": True,
                }
                return {
                    "success": True,
                    "need_captcha": True,
                    "captcha_image": f"data:image/jpeg;base64,{captcha_b64}",
                    "message": "Решите капчу для продолжения",
                }
            # If screenshot failed, continue to SMS polling (might work without captcha)

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
                    raise HTTPException(status_code=429, detail="Ваш номер заблокирован для отправки SMS. Исчерпан суточный лимит (4 запроса). Попробуйте завтра.")
                if 'Превышено количество попыток' in page_text:
                    try:
                        await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_4_rate_limit.png"))
                    except: pass
                    try: browser.stop()
                    except Exception: pass
                    raise HTTPException(status_code=429, detail="Превышено количество попыток. Запросите новую СМС через 3 минуты.")
        except HTTPException:
            raise
        except Exception:
            pass  # If early check fails, continue to polling loop

        # Wait up to 30s for ACTUAL page transition to SMS code input
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
                if 'DAILY' in result:
                    raise HTTPException(status_code=429, detail="Ваш номер заблокирован для отправки SMS. Исчерпан суточный лимит (4 запроса). Попробуйте завтра.")
                raise HTTPException(status_code=429, detail="Превышено количество попыток. Запросите новую СМС через 3 минуты.")
            if result == 'OK':
                sms_found = True
                break

        if not sms_found:
            # Take failure screenshot
            try:
                await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_4_no_sms.png"))
            except: pass
            try: browser.stop()
            except Exception: pass
            raise HTTPException(status_code=500, detail="Не удалось отправить SMS. Попробуйте позже.")

        # Take success screenshot showing SMS code input screen
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_4_sms_ok.png"))
        except: pass

        _login_sessions[user_id] = {
            "browser": browser,
            "tab": tab,
            "phone": phone_raw,
            "force_sms": req.force_sms,
            "created_at": _time.time(),
            "proc": _chrome_proc,
            "profile_dir": _user_data_dir,
        }
        return {"success": True, "need_pin": False, "message": "SMS отправлено. Введите код из SMS."}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Login error: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        # Kill the separate login Chrome and clean up temp profile
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
        raise HTTPException(status_code=500, detail="Ошибка при попытке входа")


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
        # Type captcha answer into the input field
        captcha_input = await tab.select('input[placeholder*="letters"], input[placeholder*="букв"], input.captcha__text-input, [class*="captcha"] input[type="text"]', timeout=3)
        if not captcha_input:
            # Fallback: try any text input in the captcha area
            captcha_input = await tab.select('.smartcaptcha input, [class*="Captcha"] input', timeout=2)

        if captcha_input:
            await captcha_input.mouse_click()
            await asyncio.sleep(0.3)
            # Clear any existing value
            await tab.send(uc.cdp.input_.dispatch_key_event(type_='keyDown', key='a', code='KeyA', modifiers=2))  # Ctrl+A
            await tab.send(uc.cdp.input_.dispatch_key_event(type_='keyUp', key='a', code='KeyA'))
            await asyncio.sleep(0.1)
            # Type the answer character by character
            for ch in answer:
                await tab.send(uc.cdp.input_.dispatch_key_event(
                    type_='keyDown', key=ch, text=ch,
                ))
                await asyncio.sleep(0.03)
                await tab.send(uc.cdp.input_.dispatch_key_event(
                    type_='keyUp', key=ch,
                ))
                await asyncio.sleep(0.05)
            await asyncio.sleep(0.5)
        else:
            logger.error("Could not find captcha input field")
            raise HTTPException(status_code=500, detail="Не найдено поле ввода капчи. Попробуйте заново.")

        # Click Submit button
        submit_btn = await tab.select('button:has-text("Submit"), button:has-text("Подтвердить"), .captcha__submit, [class*="captcha"] button', timeout=2)
        if not submit_btn:
            # Fallback: try clicking by evaluating
            await safe_evaluate(tab, """
                var btns = document.querySelectorAll('button');
                for (var b of btns) {
                    if (b.textContent.trim() === 'Submit' || b.textContent.trim() === 'Подтвердить') {
                        b.click(); break;
                    }
                }
            """)
        else:
            await submit_btn.click()

        await asyncio.sleep(5)  # Wait for captcha validation + SMS trigger

        # DEBUG screenshot
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_5_after_captcha.png"))
        except: pass

        # Check if captcha was wrong (captcha still visible)
        try:
            still_captcha = await safe_evaluate(tab, """
                (function() {
                    var t = document.body.innerText;
                    return t.includes('SmartCaptcha') || t.includes('Enter the code from the image') || t.includes('Введите код с картинки');
                })()
            """)
            if still_captcha:
                # Captcha still showing — wrong answer. Take new screenshot
                import base64
                captcha_path = os.path.join(DATA_DIR, f"login_{user_id}_captcha.png")
                await tab.save_screenshot(captcha_path)
                with open(captcha_path, 'rb') as f:
                    captcha_b64 = base64.b64encode(f.read()).decode('utf-8')
                return {
                    "success": True,
                    "need_captcha": True,
                    "captcha_image": f"data:image/jpeg;base64,{captcha_b64}",
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
    """Submit SMS code via nodriver, navigate to /cart/, save full cookies."""
    import asyncio

    user_id = req.user_id
    entry = _login_sessions.get(user_id)
    if not entry:
        raise HTTPException(status_code=400, detail="Сессия истекла. Начните заново.")

    browser = entry["browser"]
    tab = entry["tab"]
    try:
        code = req.code.strip()
        if not code.isdigit() or not (4 <= len(code) <= 8):
            raise HTTPException(status_code=400, detail="Некорректный код")

        # Fill SMS code using CDP key events (same method as phone — VkusVill validates via JS events)
        import nodriver as uc
        sms_input = await tab.find('input[name="SMS"]', best_match=True)
        if sms_input:
            await sms_input.mouse_click()
            await asyncio.sleep(0.3)
            for digit in code:
                await tab.send(uc.cdp.input_.dispatch_key_event(
                    type_='keyDown', key=digit, text=digit,
                    code=f'Digit{digit}',
                    windows_virtual_key_code=ord(digit),
                    native_virtual_key_code=ord(digit),
                ))
                await asyncio.sleep(0.05)
                await tab.send(uc.cdp.input_.dispatch_key_event(
                    type_='keyUp', key=digit,
                    code=f'Digit{digit}',
                    windows_virtual_key_code=ord(digit),
                    native_virtual_key_code=ord(digit),
                ))
                await asyncio.sleep(0.15)
            await asyncio.sleep(0.5)
        else:
            raise HTTPException(status_code=500, detail="SMS input not found")

        # Click submit button (may say "Войти" or "Подтвердить")
        submit_clicked = False
        btns = await tab.select_all('button')
        for b in btns:
            txt = (b.text or '').strip() if hasattr(b, 'text') else ''
            if any(kw in txt for kw in ['Войти', 'Подтвердить', 'Далее']):
                await b.mouse_click()
                submit_clicked = True
                logger.info(f"Clicked submit button: '{txt}'")
                break
        if not submit_clicked:
            # Try JS click on any visible submit button
            await tab.evaluate('document.querySelector("button[type=submit], .js-VkIdButton, .LoginForm__btn")?.click()')
            logger.info("Fallback: JS click on submit button")
        await asyncio.sleep(10)  # Wait for VkusVill to process login

        # Navigate to /personal/ to confirm auth (sets UF_USER_AUTH=Y)
        await tab.get('https://vkusvill.ru/personal/')
        await asyncio.sleep(5)

        # Navigate to cart to bind delivery address cookies
        await tab.get('https://vkusvill.ru/cart/')
        await asyncio.sleep(5)

        # If UF_USER_AUTH still N, try refreshing /personal/ once more (VkusVill can be slow)
        cdp_cookies_check = await browser.cookies.get_all()
        auth_check = {c.name: c.value for c in cdp_cookies_check}
        if auth_check.get("UF_USER_AUTH") != "Y":
            logger.info("UF_USER_AUTH not Y yet, retrying /personal/...")
            await tab.get('https://vkusvill.ru/personal/')
            await asyncio.sleep(8)

        # Get ALL cookies via CDP (includes httpOnly — not accessible via document.cookie)
        cdp_cookies = await browser.cookies.get_all()
        cookies_list = [
            {
                "name": c.name,
                "value": c.value,
                "domain": c.domain,
                "path": c.path,
                "secure": c.secure,
                "httpOnly": c.http_only,
                "expiry": int(c.expires) if getattr(c, "expires", None) else None,
            }
            for c in cdp_cookies
        ]

        # Verify login actually succeeded before saving cookies
        # UF_USER_AUTH=Y is the definitive proof of authentication
        cookie_map = {c["name"]: c["value"] for c in cookies_list}
        is_authenticated = cookie_map.get("UF_USER_AUTH") == "Y"

        if not is_authenticated:
            logger.warning(f"Login failed for {entry.get('phone', user_id)}: UF_USER_AUTH={cookie_map.get('UF_USER_AUTH', 'missing')} — NOT saving cookies")
            return {"success": False, "message": "Не удалось подтвердить вход. VkusVill не принял код — попробуйте ещё раз."}

        # Save cookies by PHONE (not user_id)
        phone_10 = entry.get("phone", "")
        if phone_10:
            cookies_path = _phone_cookies_path(phone_10)
            # If force_sms ("Новый вход"), delete old cookies first
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
            # Fallback: save by user_id (legacy)
            cookies_path = get_user_cookies_path(int(user_id) if user_id.isdigit() else user_id)
            os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
            with open(cookies_path, 'w', encoding='utf-8') as f:
                json.dump(cookies_list, f, indent=2)
            logger.info(f"Saved {len(cookies_list)} cookies for user {user_id} (UF_USER_AUTH=Y)")

        return {
            "success": True,
            "need_set_pin": bool(phone_10),
            "phone": phone_10,
            "message": "Авторизация успешна. Установите PIN.",
            "profile_dir": entry.get("profile_dir"),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Verify error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при проверке кода")
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
        for name in ["green", "red", "yellow"]:
            background_tasks.add_task(_run_script, name, script_map[name])
        return {"started": ["green", "red", "yellow"], "message": "All scrapers queued"}

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
    """Return last N log lines."""
    _require_token(token)
    lines = list(log_buffer)[-n:]
    return {"lines": lines, "total": len(log_buffer)}


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
