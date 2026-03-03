"""
FastAPI Backend for VkusVill Mini App
Serves product data, handles favorites, and provides admin panel
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
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
# uvicorn --reload spawns a worker subprocess with SelectorEventLoop (Windows default)
# which doesn't implement _make_subprocess_transport → NotImplementedError.
# Setting the policy at module level ensures the correct loop is used everywhere.
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
from scraper.vkusvill import PlaywrightScraper
from cart.vkusvill_api import VkusVillCart
from bot.auth import get_user_cookies_path, normalize_phone as _bot_normalize_phone
import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Load admin token from config / env
try:
    from config import ADMIN_TOKEN
except Exception:
    ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "")

app = FastAPI(title="VkusVill Mini App API", version="1.0.0")

# CORS for mini app
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:8000",
        os.environ.get("WEB_APP_ORIGIN", "https://t.me"),
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize database
db = Database()

# Data paths
BASE_PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_PROJECT_DIR, "data")
PROPOSALS_PATH = os.path.join(DATA_DIR, "proposals.json")
MINIAPP_DIST = os.path.join(BASE_PROJECT_DIR, "miniapp", "dist")

# Mount assets directory if it exists
assets_dir = os.path.join(MINIAPP_DIST, "assets")
if os.path.exists(assets_dir):
    app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")

# ─── Scraper State ────────────────────────────────────────────────────────────

scraper_status: dict = {
    "green":  {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "red":    {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "yellow": {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "merge":  {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "login":  {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
}

log_buffer: deque = deque(maxlen=300)
_scraper_processes: dict = {}

# Per-name locks — prevent two simultaneous requests launching the same scraper twice
_run_locks: dict = {
    name: threading.Lock()
    for name in ["green", "red", "yellow", "merge", "login"]
}

# Per-user login sessions: {user_id: {"driver": uc.Chrome, "created_at": float}}
_login_sessions: dict = {}
_LOGIN_TTL_SECONDS = 600  # 10 minutes max for login flow


def _run_script(name: str, script_path: str):
    """Run a Python script in a background thread, capturing output.
    Uses a per-name lock so the check+set of 'running' is atomic.
    """
    lock = _run_locks.get(name, threading.Lock())
    with lock:
        if scraper_status[name]["running"]:
            log_buffer.append(f"[{name}] Already running, skipping.")
            return
        # Atomic: mark running while still holding the lock
        scraper_status[name]["running"] = True
        scraper_status[name]["last_run"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        scraper_status[name]["last_output"] = ""

    lines: list = []

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

    threading.Thread(target=worker, daemon=True).start()


def _require_token(token: Optional[str]):
    if not ADMIN_TOKEN or not token or token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")


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
    is_green: int
    price_type: int


# ─── Public Endpoints ─────────────────────────────────────────────────────────

@app.get("/")
def root():
    index_path = os.path.join(MINIAPP_DIST, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return {"status": "ok", "message": "VkusVill Mini App API (Frontend not built yet)"}

@app.get("/favicon.ico", include_in_schema=False)
def favicon():
    vite_svg = os.path.join(MINIAPP_DIST, "vite.svg")
    if os.path.exists(vite_svg):
        return FileResponse(vite_svg)
    return HTMLResponse(status_code=404)

@app.get("/api/products", response_model=ProductsResponse)
def get_products():
    """Get all products from proposals.json"""
    try:
        if not os.path.exists(PROPOSALS_PATH):
            raise HTTPException(status_code=404, detail="Products data not found")
        with open(PROPOSALS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Invalid JSON data")


@app.get("/api/favorites/{user_id}")
def get_favorites(user_id: str):
    favorites = db.get_user_favorite_products(user_id)
    return {
        "user_id": user_id,
        "favorites": [{"product_id": f.product_id, "product_name": f.product_name} for f in favorites],
    }


@app.post("/api/favorites/{user_id}", response_model=FavoriteResponse)
def toggle_favorite(user_id: str, request: FavoriteRequest):
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
def remove_favorite(user_id: str, product_id: str):
    success = db.remove_favorite_product(user_id, product_id)
    return {"success": success, "product_id": product_id}


@app.post("/api/sync")
def sync_products():
    try:
        if not os.path.exists(PROPOSALS_PATH):
            return {"success": False, "message": "No products file found"}
        with open(PROPOSALS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        products = data.get("products", [])
        new_count = sum(1 for p in products if db.mark_product_seen(p["id"]))
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
        "pin_hash": hashlib.sha256(pin.encode()).hexdigest(),
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
    return {"authenticated": True, "phone": phone}


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
    import time as _time
    now = _time.time()
    stale = [k for k, v in _login_sessions.items() if now - v.get("created_at", 0) > _LOGIN_TTL_SECONDS]
    for k in stale:
        entry = _login_sessions.pop(k, None)
        if entry and entry.get("browser"):
            try:
                entry["browser"].stop()
            except Exception:
                pass


@app.post("/api/auth/login")
async def auth_login(req: AuthPhoneRequest):
    """Start login via nodriver: navigate to /personal/, fill phone, wait for SMS."""
    import nodriver as uc
    import asyncio
    import time as _time

    # Patch nodriver Config to include LocalNetworkAccessChecks in --disable-features
    # (nodriver builds its own --disable-features, overriding any browser_args)
    _orig_config_call = uc.Config.__call__
    def _patched_call(self):
        args = _orig_config_call(self)
        return [
            (a + ',LocalNetworkAccessChecks,BlockInsecurePrivateNetworkRequests,PrivateNetworkAccessForWorkers,PrivateNetworkAccessForNavigations'
             if a.startswith('--disable-features=') else a)
            for a in args
        ]
    uc.Config.__call__ = _patched_call

    user_id = req.user_id
    phone_raw = _normalize_phone(req.phone)
    if not phone_raw:
        raise HTTPException(status_code=400, detail="Некорректный формат телефона. Примеры: 9166076650, +79166076650, 89166076650")

    # Check if this phone already has valid cookies + PIN (skip browser!)
    if not req.force_sms and _phone_has_valid_cookies(phone_raw):
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

    _evict_stale_login_sessions()

    browser = None
    try:
        browser = await uc.start(
            browser_args=[
                '--window-position=-2400,-2400',
                '--window-size=1280,720',
                '--disable-gpu',
            ],
            sandbox=False,
        )

        tab = await browser.get('https://vkusvill.ru/personal/')
        await asyncio.sleep(5)  # More time for initial load

        # DEBUG: Initial state
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_1_init.png"))
        except: pass

        # BUG-026: Use CDP Input.dispatchKeyEvent for real keyboard simulation
        # The masked input only updates its internal state from real keyboard events
        
        # 1. Focus the phone input via JS
        await tab.evaluate("""
            (function() {
                var input = document.querySelector('input.js-user-form-checksms-api-phone1') ||
                            document.querySelector('input[name="USER_PHONE"]');
                if (input) { input.focus(); input.click(); }
            })()
        """)
        await asyncio.sleep(0.5)

        # 2. Type each digit using CDP Input.dispatchKeyEvent (real keyboard simulation)
        for digit in phone_raw:
            # keyDown
            await tab.send(uc.cdp.input_.dispatch_key_event(
                type_='keyDown',
                key=digit,
                text=digit,
                code=f'Digit{digit}',
                windows_virtual_key_code=ord(digit),
                native_virtual_key_code=ord(digit),
            ))
            # keyUp
            await tab.send(uc.cdp.input_.dispatch_key_event(
                type_='keyUp',
                key=digit,
                code=f'Digit{digit}',
                windows_virtual_key_code=ord(digit),
                native_virtual_key_code=ord(digit),
            ))
            await asyncio.sleep(0.12)  # Give mask time to process each keystroke

        await asyncio.sleep(1.5)  # Let mask process the phone number
        
        # DEBUG: After phone entry
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_2_phone.png"))
        except: pass

        # 3. Force-enable the button (mask's onChange doesn't fire from CDP events)
        #    then click it via JS (safe since we enabled it)
        await tab.evaluate("""
            (function() {
                var btn = document.querySelector('button.js-user-form-submit-btn');
                if (!btn) return "no_btn";
                // Force-enable the button 
                btn.disabled = false;
                btn.classList.remove('disabled');
                btn.removeAttribute('disabled');
                // Click it
                btn.click();
                return "clicked";
            })()
        """)

        await asyncio.sleep(5)  # Wait for SMS trigger
        
        # DEBUG: After click
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_3_after_click.png"))
        except: pass

        # Wait up to 30s for ACTUAL page transition to SMS code input
        # (NOT just checking input[name="SMS"] existence — it's a false positive,
        #  it exists on page load. Check for VISIBLE SMS input or "Введите код" text)
        sms_found = False
        for _ in range(30):
            await asyncio.sleep(1)
            result = await tab.evaluate("""
                (function() {
                    var sms = document.querySelector('input[name="SMS"]');
                    var smsVisible = sms ? (sms.offsetParent !== null && 
                                            sms.getBoundingClientRect().height > 0) : false;
                    var codeText = document.body.innerText.includes('Введите код');
                    // Check for rate limit error popup
                    var rateLimit = document.body.innerText.includes('Превышено количество попыток');
                    var dailyBlock = document.body.innerText.includes('заблокирован');
                    if (rateLimit || dailyBlock) return 'RATE_LIMIT:' + (dailyBlock ? 'DAILY' : 'SESSION');
                    return smsVisible || codeText ? 'OK' : false;
                })()
            """)
            if isinstance(result, str) and result.startswith('RATE_LIMIT'):
                try:
                    await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_4_rate_limit.png"))
                except: pass
                browser.stop()
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
            browser.stop()
            raise HTTPException(status_code=500, detail="Не удалось отправить SMS. Попробуйте позже.")

        # Take success screenshot showing SMS code input screen
        try:
            await tab.save_screenshot(os.path.join(DATA_DIR, f"login_{user_id}_4_sms_ok.png"))
        except: pass

        _login_sessions[user_id] = {"browser": browser, "tab": tab, "phone": phone_raw, "force_sms": req.force_sms, "created_at": _time.time()}
        return {"success": True, "need_pin": False, "message": "SMS отправлено. Введите код из SMS."}

    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"Login error: {type(e).__name__}: {e}\n{traceback.format_exc()}")
        if browser:
            try:
                browser.stop()
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Ошибка при попытке входа")


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

        # Fill SMS code using native send_keys
        sms_input = await tab.find('input[name="SMS"]', best_match=True)
        if sms_input:
            await sms_input.click()
            await sms_input.send_keys(code)
        else:
            raise HTTPException(status_code=500, detail="SMS input not found")
        await asyncio.sleep(0.3)

        # Click "Войти"
        login_btn = await tab.find('button', best_match=True)
        btns = await tab.select_all('button')
        for b in btns:
            if hasattr(b, 'text') and 'Войти' in (b.text or ''):
                login_btn = b
                break
        
        if login_btn:
            await login_btn.click()
        else:
            raise HTTPException(status_code=500, detail="Login button not found")
        await asyncio.sleep(8)  # Wait for VkusVill to process login

        # Navigate to /personal/ first to confirm auth (sets UF_USER_AUTH=Y)
        await tab.get('https://vkusvill.ru/personal/')
        await asyncio.sleep(5)

        # Navigate to cart to bind delivery address cookies
        await tab.get('https://vkusvill.ru/cart/')
        await asyncio.sleep(5)

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
            logger.info(f"Saved {len(cookies_list)} cookies for phone {phone_10}")
        else:
            # Fallback: save by user_id (legacy)
            cookies_path = get_user_cookies_path(int(user_id) if user_id.isdigit() else user_id)
            os.makedirs(os.path.dirname(cookies_path), exist_ok=True)
            with open(cookies_path, 'w', encoding='utf-8') as f:
                json.dump(cookies_list, f, indent=2)
            logger.info(f"Saved {len(cookies_list)} cookies for user {user_id}")

        cookie_names = {c["name"] for c in cookies_list}
        if any(n in cookie_names for n in ('__Host-PHPSESSID', 'BXVV_SALE_UID', 'PHPSESSID')):
            return {"success": True, "need_set_pin": bool(phone_10), "phone": phone_10, "message": "Авторизация успешна. Установите PIN."}
        return {"success": False, "message": "Не удалось подтвердить вход. Попробуйте ещё раз."}

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
        _login_sessions.pop(user_id, None)


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

    # Verify PIN
    pin_hash = hashlib.sha256(req.pin.encode()).hexdigest()
    if pin_hash != pin_data["pin_hash"]:
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


@app.post("/api/auth/logout")
def auth_logout(req: AuthLogoutRequest):
    """Logout: rename cookies to .bak (preserve for PIN re-login)."""
    phone = _get_phone_for_user(req.user_id)
    if phone:
        cp = _phone_cookies_path(phone)
        if os.path.exists(cp):
            os.rename(cp, cp + ".bak")
    return {"success": True, "message": "Вы вышли из аккаунта"}


# ─── Cart Endpoints ───────────────────────────────────────────────────────────

@app.post("/api/cart/add")
def cart_add_endpoint(req: CartAddRequest):
    """Add a product to the user's VkusVill cart."""
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
def cart_items_endpoint(user_id: str):
    """Get current VkusVill cart items for a user."""
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
            result = cart.get_cart()
        finally:
            cart.close()

        if not result.get("success"):
            raise HTTPException(status_code=502, detail=result.get("error", "Cart fetch failed"))

        # Parse basket items from raw response
        raw = result.get("raw", {})
        basket_items = []
        basket = raw.get("basket", {})
        if isinstance(basket, dict):
            for key, item in basket.items():
                if isinstance(item, dict) and item.get("NAME"):
                    basket_items.append({
                        "id": item.get("PRODUCT_ID", key),
                        "name": item.get("NAME", ""),
                        "price": item.get("PRICE", 0),
                        "quantity": item.get("Q", 1),
                        "can_buy": item.get("CAN_BUY") == "Y" or item.get("CAN_BUY") is True,
                        "max_q": item.get("MAX_Q", 0),
                        "image": item.get("PICTURE", ""),
                    })

        totals = raw.get("totals", {})
        return {
            "success": True,
            "items": basket_items,
            "items_count": totals.get("Q_ITEMS", len(basket_items)),
            "total_price": totals.get("PRICE_FINAL", 0),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Cart items error: {e}")
        raise HTTPException(status_code=500, detail="Ошибка загрузки корзины")


@app.post("/api/cart/remove")
def cart_remove_endpoint(req: CartAddRequest):
    """Remove a product from the user's VkusVill cart."""
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


@app.post("/api/cart/clear")
def cart_clear_endpoint(req: dict):
    """Clear all items from the user's VkusVill cart."""
    user_id = str(req.get("user_id", ""))
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
    return {"scrapers": scraper_status, "data": counts}


@app.post("/admin/run/{scraper}")
def admin_run_scraper(
    scraper: str,
    background_tasks: BackgroundTasks,
    token: Optional[str] = Header(None, alias="X-Admin-Token"),
):
    """Run a specific scraper: green | red | yellow | merge | login | all"""
    _require_token(token)

    script_map = {
        "green":  os.path.join(BASE_PROJECT_DIR, "scrape_green.py"),
        "red":    os.path.join(BASE_PROJECT_DIR, "scrape_red.py"),
        "yellow": os.path.join(BASE_PROJECT_DIR, "scrape_yellow.py"),
        "merge":  os.path.join(BASE_PROJECT_DIR, "scrape_merge.py"),
        "login":  os.path.join(BASE_PROJECT_DIR, "login.py"),
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

    background_tasks.add_task(_run_script, scraper, script_map[scraper])
    return {"started": scraper, "message": f"{scraper} scraper started in background"}


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
        return FileResponse(ADMIN_HTML_PATH, media_type="text/html; charset=utf-8")
    return HTMLResponse("<h2>admin.html not found next to main.py</h2>", status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
