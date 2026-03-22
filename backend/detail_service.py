"""
Product detail fetcher — persistent Chrome singleton.

On Windows + uvicorn, the event loop is SelectorEventLoop which cannot
spawn subprocesses (needed by nodriver). Solution: run Chrome operations
in a dedicated background thread with its own ProactorEventLoop.

Architecture:
  - Background "chrome-worker" thread with ProactorEventLoop
  - Main uvicorn thread sends URLs via thread-safe queue  
  - Worker processes tasks and returns HTML via per-task result queues

Usage from main.py:
    from backend import detail_service
"""

import asyncio
import concurrent.futures
import json
import os
import logging
import queue
import shutil
import sys
import tempfile
import threading
import time
import traceback

logger = logging.getLogger("detail_service")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")
CACHE_PATH = os.path.join(DATA_DIR, "detail_cache.json")
COOKIES_PATH = os.path.join(DATA_DIR, "cookies.json")


# ── Chrome worker thread ───────────────────────────────────
_work_queue = queue.Queue()
_worker_thread = None
_worker_started = threading.Event()


class _ChromeTask:
    """A unit of work for the Chrome worker thread."""
    __slots__ = ('url', 'result_queue', 'html', 'error')

    def __init__(self, url: str):
        self.url = url
        self.result_queue = queue.Queue()
        self.html = None
        self.error = None


def _chrome_worker():
    """Background thread: ProactorEventLoop for Chrome."""
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    logger.info(f"[Worker] Event loop: {type(loop).__name__}")

    try:
        loop.run_until_complete(_worker_main(loop))
    except Exception as e:
        logger.error(f"[Worker] Fatal error: {e}\n{traceback.format_exc()}")
    finally:
        loop.close()


async def _worker_main(loop):
    """Main coroutine on the worker's ProactorEventLoop."""
    import nodriver as uc

    browser = None
    tmp_dir = None
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)

    async def ensure_browser():
        nonlocal browser, tmp_dir

        if browser is not None:
            try:
                if browser.targets:
                    return browser
            except Exception:
                logger.warning("[Worker] Chrome died, relaunching...")
                # Kill the old Chrome process before nulling reference
                try:
                    browser.stop()
                except Exception:
                    pass
                # Also kill OS process if we can find the PID
                try:
                    pid = getattr(browser, '_process_pid', None)
                    if pid:
                        import signal
                        os.kill(pid, signal.SIGTERM)
                except Exception:
                    pass
                browser = None

        if tmp_dir:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        tmp_dir = tempfile.mkdtemp(prefix='uc_detail_')
        logger.info(f"[Worker] Launching Chrome, tmp={tmp_dir}")

        _browser_args = [
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-features=LocalNetworkAccessChecks',
        ]
        if sys.platform == 'win32':
            _browser_args += ['--window-size=1,1', '--window-position=-9999,-9999']
        else:
            _browser_args += [
                '--headless=new', '--no-sandbox', '--disable-gpu',
                '--disable-dev-shm-usage', '--disable-software-rasterizer',
            ]
        browser = await uc.start(
            user_data_dir=tmp_dir,
            browser_args=_browser_args,
        )
        logger.info("[Worker] Chrome launched")

        # Load cookies
        if os.path.exists(COOKIES_PATH):
            try:
                with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                logger.info(f"[Worker] Loading {len(cookies)} cookies...")
                page = await browser.get('https://vkusvill.ru')
                await asyncio.sleep(2)
                loaded = 0
                for c in cookies:
                    try:
                        await page.send(uc.cdp.network.set_cookie(
                            name=c['name'], value=c['value'],
                            domain=c.get('domain', '.vkusvill.ru'),
                            path=c.get('path', '/'),
                            secure=c.get('secure', False),
                            http_only=c.get('httpOnly', False),
                        ))
                        loaded += 1
                    except Exception:
                        pass
                logger.info(f"[Worker] Cookies: {loaded}/{len(cookies)}")
                # NOTE: Don't close the page — browser.get() needs at least
                # one page target to navigate. Closing the only tab causes
                # StopIteration in nodriver's get() method.
            except Exception as e:
                logger.warning(f"[Worker] Cookie loading failed: {e}")

        return browser

    _worker_started.set()
    logger.info("[Worker] Ready, waiting for tasks")

    while True:
        # Non-blocking queue read via executor (keeps event loop alive
        # so nodriver's websocket & Chrome management can run)
        try:
            task = await loop.run_in_executor(executor, _work_queue.get, True, 60)
        except queue.Empty:
            continue

        if task is None:
            break  # Shutdown

        try:
            b = await ensure_browser()
            logger.info(f"[Worker] GET {task.url}")
            page = await b.get(task.url)
            await asyncio.sleep(2)
            task.html = await page.evaluate("document.documentElement.outerHTML")
            logger.info(f"[Worker] OK {len(task.html)} chars")
            try:
                await page.close()
            except Exception:
                pass
        except Exception as e:
            logger.error(f"[Worker] FAIL {task.url}: {e}\n{traceback.format_exc()}")
            task.error = str(e)

        task.result_queue.put(task)

    # Cleanup
    executor.shutdown(wait=False)
    if browser:
        try:
            browser.stop()
        except Exception:
            pass
    if tmp_dir:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    logger.info("[Worker] Stopped")


def _ensure_worker():
    """Start Chrome worker thread if not running."""
    global _worker_thread
    if _worker_thread is None or not _worker_thread.is_alive():
        _worker_started.clear()
        _worker_thread = threading.Thread(
            target=_chrome_worker, daemon=True, name="chrome-worker"
        )
        _worker_thread.start()
        if not _worker_started.wait(timeout=30):
            raise RuntimeError("Chrome worker failed to start")


# ── Cache ───────────────────────────────────────────────────
def _load_cache() -> dict:
    try:
        with open(CACHE_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save_cache(cache: dict):
    tmp = CACHE_PATH + ".tmp"
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    os.replace(tmp, CACHE_PATH)


def read_cache(product_id: str) -> dict | None:
    cache = _load_cache()
    entry = cache.get(str(product_id))
    if not entry:
        return None
    if entry.get("source_unavailable"):
        return None
    cached_at = entry.get("_cached_at", "")
    if cached_at:
        try:
            ts = time.mktime(time.strptime(cached_at, "%Y-%m-%d %H:%M:%S"))
            if time.time() - ts > 86400:
                return None
        except ValueError:
            pass
    return entry


def write_cache(product_id: str, data: dict):
    cache = _load_cache()
    data["_cached_at"] = time.strftime("%Y-%m-%d %H:%M:%S")
    cache[str(product_id)] = data
    _save_cache(cache)


# ── Public API ─────────────────────────────────────────────
async def fetch_product_html(url: str) -> str:
    """
    Fetch product page HTML using Chrome worker thread.
    First call: ~8-10s (launch + cookies). Subsequent: ~3s.
    Timeout: 15s — returns fallback if VkusVill unreachable.
    """
    _ensure_worker()

    task = _ChromeTask(url)
    _work_queue.put(task)

    # Wait for result without blocking uvicorn's event loop
    # Timeout after 15s to avoid infinite spinner
    import time as _time
    deadline = _time.monotonic() + 15
    while True:
        try:
            result = task.result_queue.get_nowait()
            break
        except queue.Empty:
            if _time.monotonic() > deadline:
                raise RuntimeError("Chrome fetch timed out (15s)")
            await asyncio.sleep(0.2)

    if result.error:
        raise RuntimeError(result.error)
    if not result.html:
        raise RuntimeError("Empty HTML")

    return result.html


def invalidate_cookies():
    """Force browser restart on next request."""
    _work_queue.put(None)


async def shutdown():
    """Cleanup on app shutdown."""
    _work_queue.put(None)
    if _worker_thread:
        _worker_thread.join(timeout=10)
