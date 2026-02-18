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
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
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

# ─── Scraper State ───────────────────────────────────────────────────────────

scraper_status: dict = {
    "green":  {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "red":    {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "yellow": {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "merge":  {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
    "login":  {"running": False, "last_run": None, "exit_code": None, "last_output": ""},
}

log_buffer: deque = deque(maxlen=300)  # keep last 300 log lines
_scraper_processes: dict = {}  # name → subprocess.Popen


def _run_script(name: str, script_path: str):
    """Run a Python script in a background thread, capturing output."""
    if scraper_status[name]["running"]:
        log_buffer.append(f"[{name}] ⚠️ Already running, skipping.")
        return

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
            status_emoji = "✅" if proc.returncode == 0 else "❌"
            log_buffer.append(f"[{name}] {status_emoji} Finished (exit {proc.returncode})")
        except Exception as exc:
            log_buffer.append(f"[{name}] ❌ Exception: {exc}")
            scraper_status[name]["exit_code"] = -1
        finally:
            scraper_status[name]["running"] = False
            scraper_status[name]["last_output"] = "\n".join(lines[-40:])
            _scraper_processes.pop(name, None)

    threading.Thread(target=worker, daemon=True).start()


def _require_token(token: Optional[str]):
    if token != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Invalid admin token")


# ─── Pydantic Models ─────────────────────────────────────────────────────────

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
    """Get all products from JSON file"""
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
    """Run a specific scraper. scraper = green | red | yellow | merge | login | all"""
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
        raise HTTPException(status_code=400, detail=f"Unknown scraper: {scraper}. Use: green, red, yellow, merge, login, all")

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


# ─── Admin Panel HTML ─────────────────────────────────────────────────────────

ADMIN_HTML = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>VkusVill Admin</title>
<script src="https://cdn.tailwindcss.com"></script>
<style>
  body { background: #0f172a; color: #e2e8f0; }
  .card { background: #1e293b; border: 1px solid #334155; border-radius: 12px; padding: 16px; }
  .btn { padding: 8px 16px; border-radius: 8px; font-weight: 600; cursor: pointer; border: none; transition: opacity .15s; }
  .btn:hover { opacity: 0.85; }
  .btn:disabled { opacity: 0.4; cursor: not-allowed; }
  .btn-green  { background: #16a34a; color: #fff; }
  .btn-red    { background: #dc2626; color: #fff; }
  .btn-yellow { background: #ca8a04; color: #fff; }
  .btn-blue   { background: #2563eb; color: #fff; }
  .btn-purple { background: #7c3aed; color: #fff; }
  .btn-gray   { background: #475569; color: #fff; }
  #log { font-family: monospace; font-size: 12px; background: #0f172a; border: 1px solid #334155;
         border-radius: 8px; padding: 12px; height: 300px; overflow-y: auto; white-space: pre-wrap; }
  .badge { padding: 2px 8px; border-radius: 99px; font-size: 11px; font-weight: 700; }
  .badge-on  { background: #166534; color: #86efac; }
  .badge-off { background: #1e293b; color: #64748b; border: 1px solid #334155; }
  .running { animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:.5} }
</style>
</head>
<body class="p-4 max-w-4xl mx-auto">

<!-- Auth Section -->
<div id="auth-section" class="mb-6">
  <h1 class="text-2xl font-bold mb-4">🛠️ VkusVill Admin Panel</h1>
  <div class="card flex gap-3 items-center">
    <input id="token-input" type="password" placeholder="Admin token" value=""
      class="flex-1 bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm focus:outline-none focus:border-blue-500">
    <button class="btn btn-blue" onclick="saveToken()">🔑 Войти</button>
  </div>
  <p id="auth-error" class="text-red-400 text-sm mt-2 hidden">❌ Неверный токен</p>
</div>

<!-- Dashboard (hidden until authed) -->
<div id="dashboard" class="hidden space-y-4">

  <!-- Header -->
  <div class="flex items-center justify-between mb-2">
    <h1 class="text-2xl font-bold">🛠️ VkusVill Admin</h1>
    <div class="flex gap-2 items-center">
      <span id="last-refresh" class="text-xs text-slate-500"></span>
      <button class="btn btn-gray text-xs py-1 px-3" onclick="logout()">Выйти</button>
    </div>
  </div>

  <!-- Stats cards -->
  <div class="grid grid-cols-2 md:grid-cols-4 gap-3">
    <div class="card text-center">
      <div class="text-3xl font-bold text-white" id="cnt-total">—</div>
      <div class="text-xs text-slate-400 mt-1">📦 Всего</div>
    </div>
    <div class="card text-center">
      <div class="text-3xl font-bold text-green-400" id="cnt-green">—</div>
      <div class="text-xs text-slate-400 mt-1">🟢 Зелёные</div>
      <div class="text-xs text-slate-500 mt-0.5">Сайт: <span id="cnt-live">—</span></div>
    </div>
    <div class="card text-center">
      <div class="text-3xl font-bold text-red-400" id="cnt-red">—</div>
      <div class="text-xs text-slate-400 mt-1">🔴 Красные</div>
    </div>
    <div class="card text-center">
      <div class="text-3xl font-bold text-yellow-400" id="cnt-yellow">—</div>
      <div class="text-xs text-slate-400 mt-1">🟡 Жёлтые</div>
    </div>
  </div>

  <!-- Updated at -->
  <div class="card py-2 text-xs text-slate-400 text-center" id="updated-at">Последнее обновление: —</div>

  <!-- Scraper Actions -->
  <div class="card">
    <h2 class="font-bold text-sm mb-3 text-slate-300">⚡ Запуск скраперов</h2>
    <div class="flex flex-wrap gap-2">
      <button class="btn btn-green"  onclick="runScraper('green')"  id="btn-green">🟢 Зелёный</button>
      <button class="btn btn-red"    onclick="runScraper('red')"    id="btn-red">🔴 Красный</button>
      <button class="btn btn-yellow" onclick="runScraper('yellow')" id="btn-yellow">🟡 Жёлтый</button>
      <button class="btn btn-blue"   onclick="runScraper('all')"    id="btn-all">🔄 Все сразу</button>
      <button class="btn btn-gray"   onclick="runScraper('merge')"  id="btn-merge">🔀 Merge</button>
      <button class="btn btn-purple" onclick="runScraper('login')"  id="btn-login">🔑 Ре-логин</button>
    </div>
  </div>

  <!-- Scraper Status -->
  <div class="card">
    <h2 class="font-bold text-sm mb-3 text-slate-300">📊 Статус скраперов</h2>
    <div class="space-y-2" id="scraper-status-list"></div>
  </div>

  <!-- Log Viewer -->
  <div class="card">
    <div class="flex items-center justify-between mb-2">
      <h2 class="font-bold text-sm text-slate-300">📋 Логи (последние 100 строк)</h2>
      <div class="flex gap-2">
        <button class="btn btn-gray text-xs py-1 px-3" onclick="loadLogs()">🔄 Обновить</button>
        <button class="btn btn-gray text-xs py-1 px-3" onclick="clearLog()">🗑️ Очистить</button>
      </div>
    </div>
    <div id="log">Нажмите «Обновить» чтобы загрузить логи...</div>
  </div>

</div>

<script>
  let token = sessionStorage.getItem('vv_admin_token') || '';
  let autoRefreshInterval = null;

  // On load: if token stored, try to authenticate
  window.onload = () => {
    document.getElementById('token-input').value = token;
    if (token) tryAuth();
  };

  function saveToken() {
    token = document.getElementById('token-input').value.trim();
    sessionStorage.setItem('vv_admin_token', token);
    tryAuth();
  }

  function tryAuth() {
    fetch('/admin/status', { headers: { 'X-Admin-Token': token } })
      .then(r => {
        if (r.status === 403) throw new Error('forbidden');
        return r.json();
      })
      .then(data => {
        document.getElementById('auth-error').classList.add('hidden');
        document.getElementById('auth-section').classList.add('hidden');
        document.getElementById('dashboard').classList.remove('hidden');
        applyStatus(data);
        startAutoRefresh();
        loadLogs();
      })
      .catch(() => {
        document.getElementById('auth-error').classList.remove('hidden');
        document.getElementById('dashboard').classList.add('hidden');
        document.getElementById('auth-section').classList.remove('hidden');
      });
  }

  function logout() {
    token = '';
    sessionStorage.removeItem('vv_admin_token');
    stopAutoRefresh();
    document.getElementById('dashboard').classList.add('hidden');
    document.getElementById('auth-section').classList.remove('hidden');
  }

  function applyStatus(data) {
    const d = data.data || {};
    document.getElementById('cnt-total').textContent  = (d.total  !== undefined) ? d.total  : '—';
    document.getElementById('cnt-green').textContent  = (d.green  !== undefined) ? d.green  : '—';
    document.getElementById('cnt-red').textContent    = (d.red    !== undefined) ? d.red    : '—';
    document.getElementById('cnt-yellow').textContent = (d.yellow !== undefined) ? d.yellow : '—';
    document.getElementById('cnt-live').textContent   = d.greenLiveCount || '—';
    document.getElementById('updated-at').textContent = d.updatedAt
      ? 'Последнее обновление: ' + d.updatedAt
      : 'Данных нет';
    document.getElementById('last-refresh').textContent = 'Обновлено: ' + new Date().toLocaleTimeString('ru-RU');

    // Scraper status list
    const list = document.getElementById('scraper-status-list');
    list.innerHTML = '';
    const scrapers = data.scrapers || {};
    for (const [name, s] of Object.entries(scrapers)) {
      const isRunning = s.running;
      const exitIcon = s.exit_code === 0 ? '✅' : (s.exit_code === null ? '—' : '❌');
      const badge = isRunning
        ? '<span class="badge badge-on running">⚙️ РАБОТАЕТ</span>'
        : '<span class="badge badge-off">' + exitIcon + ' Ожидание</span>';
      const stopBtn = isRunning
        ? '<button class="btn btn-red" style="font-size:11px;padding:2px 8px" onclick="killScraper(\'' + name + '\')">⛔ Стоп</button>'
        : '';
      const lastRun = s.last_run ? 'Запуск: ' + s.last_run : 'Не запускался';
      list.innerHTML += '<div class="flex items-center gap-3 p-2 rounded-lg" style="background:rgba(15,23,42,.5)">'
        + '<div class="w-16" style="font-size:11px;font-weight:700;color:#cbd5e1">' + name.toUpperCase() + '</div>'
        + badge
        + '<div class="flex-1" style="font-size:11px;color:#64748b">' + lastRun + '</div>'
        + stopBtn
        + '</div>';
    }
    // Update button states
    for (const [name, s] of Object.entries(scrapers)) {
      const btn = document.getElementById('btn-' + name);
      if (btn) btn.disabled = s.running;
    }
  }

  function runScraper(name) {
    const btn = document.getElementById('btn-' + name);
    if (btn) btn.disabled = true;
    fetch('/admin/run/' + name, { method: 'POST', headers: { 'X-Admin-Token': token } })
      .then(r => r.json())
      .then(data => {
        log('[ADMIN] ' + JSON.stringify(data));
        setTimeout(refreshStatus, 1000);
      })
      .catch(e => { log('[ADMIN] Error: ' + e); if (btn) btn.disabled = false; });
  }

  function killScraper(name) {
    // Sends a DELETE to kill (we don't have a kill endpoint, just warn)
    alert('Функция остановки: дождитесь завершения или перезапустите сервер. Скрапер "' + name + '" завершится сам после текущей итерации.');
  }

  function refreshStatus() {
    fetch('/admin/status', { headers: { 'X-Admin-Token': token } })
      .then(r => r.json())
      .then(data => applyStatus(data))
      .catch(() => {});
  }

  function loadLogs() {
    fetch('/admin/logs?n=100', { headers: { 'X-Admin-Token': token } })
      .then(r => r.json())
      .then(data => {
        const logEl = document.getElementById('log');
        logEl.textContent = data.lines.join('\n') || '(Логов пока нет)';
        logEl.scrollTop = logEl.scrollHeight;
      })
      .catch(() => {});
  }

  function clearLog() {
    document.getElementById('log').textContent = '(очищено)';
  }

  function log(line) {
    const logEl = document.getElementById('log');
    if (logEl.textContent === 'Нажмите «Обновить» чтобы загрузить логи...' || logEl.textContent === '(очищено)') {
      logEl.textContent = '';
    }
    logEl.textContent += line + '\n';
    logEl.scrollTop = logEl.scrollHeight;
  }

  function startAutoRefresh() {
    stopAutoRefresh();
    autoRefreshInterval = setInterval(() => {
      refreshStatus();
    }, 5000); // refresh status every 5s
  }

  function stopAutoRefresh() {
    if (autoRefreshInterval) { clearInterval(autoRefreshInterval); autoRefreshInterval = null; }
  }
</script>
</body>
</html>"""


# Path to the admin HTML file (next to this script)
ADMIN_HTML_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "admin.html")


@app.get("/admin")
def admin_panel_page():
    """Serve the admin panel. Accessible from any URL (AWS/localhost)."""
    if os.path.exists(ADMIN_HTML_PATH):
        return FileResponse(ADMIN_HTML_PATH, media_type="text/html; charset=utf-8")
    # Fallback: inline minimal page
    return HTMLResponse("<h2>admin.html not found</h2>", status_code=500)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
