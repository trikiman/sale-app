"""
FastAPI Backend for VkusVill Mini App
Serves product data, handles favorites, and provides admin panel
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from typing import List, Optional
from collections import deque
from datetime import datetime
import json
import os
import sys
import subprocess
import threading

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db import Database

# Load admin token from config / env
try:
    from config import ADMIN_TOKEN
except Exception:
    ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "vv-admin-2026")

app = FastAPI(title="VkusVill Mini App API", version="1.0.0")

# CORS for mini app
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
    if token != ADMIN_TOKEN:
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
    products: List[Product]


class FavoriteRequest(BaseModel):
    product_id: str
    product_name: str


class FavoriteResponse(BaseModel):
    product_id: str
    product_name: str
    is_favorite: bool


# ─── Public Endpoints ─────────────────────────────────────────────────────────

@app.get("/")
def root():
    return {"status": "ok", "message": "VkusVill Mini App API"}


@app.get("/products", response_model=ProductsResponse)
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


@app.get("/favorites/{user_id}")
def get_favorites(user_id: str):
    favorites = db.get_user_favorite_products(user_id)
    return {
        "user_id": user_id,
        "favorites": [{"product_id": f.product_id, "product_name": f.product_name} for f in favorites],
    }


@app.post("/favorites/{user_id}", response_model=FavoriteResponse)
def toggle_favorite(user_id: str, request: FavoriteRequest):
    db.upsert_user(user_id)
    favorites = db.get_user_favorite_products(user_id)
    is_favorited = any(f.product_id == request.product_id for f in favorites)
    if is_favorited:
        db.remove_favorite_product(user_id, request.product_id)
        return FavoriteResponse(product_id=request.product_id, product_name=request.product_name, is_favorite=False)
    else:
        db.add_favorite_product(user_id, request.product_id, request.product_name)
        return FavoriteResponse(product_id=request.product_id, product_name=request.product_name, is_favorite=True)


@app.delete("/favorites/{user_id}/{product_id}")
def remove_favorite(user_id: str, product_id: str):
    success = db.remove_favorite_product(user_id, product_id)
    return {"success": success, "product_id": product_id}


@app.post("/sync")
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


@app.get("/new-products")
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
