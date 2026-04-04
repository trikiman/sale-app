"""
Stealth Chrome launcher for all scrapers.
Centralizes anti-detection flags and navigator.webdriver patching.

Used by: scrape_green.py, scrape_red.py, scrape_yellow.py

Chrome Launch Strategy:
  Chrome MUST be pre-launched from top-level PowerShell (run_app.bat → start_chrome.ps1)
  because Python's subprocess chain cannot launch Chrome on Windows.
  Scrapers only CONNECT via nodriver Browser.create(host, port).
"""
import asyncio
import os
import shutil
import socket
import sys
import tempfile


SCRAPER_CHROME_PORT = 19222


def find_chrome():
    """Find Chrome executable on Windows."""
    candidates = [
        r'C:\Program Files\Google\Chrome\Application\chrome.exe',
        r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
        os.path.expandvars(r'%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe'),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    found = shutil.which('chrome') or shutil.which('google-chrome')
    if found:
        return found
    raise FileNotFoundError("Chrome not found. Install Google Chrome.")


def find_free_port():
    """Find a free TCP port."""
    with socket.socket() as s:
        s.bind(('', 0))
        return s.getsockname()[1]


def is_chrome_cdp_ready(port):
    """Check if Chrome CDP is responding on the given port."""
    try:
        import urllib.request
        resp = urllib.request.urlopen(f'http://127.0.0.1:{port}/json/version', timeout=2)
        return resp.status == 200
    except Exception:
        return False


async def launch_stealth_browser(tag="SCRAPER", profile_dir=None, offscreen=False):
    """Connect to pre-launched Chrome via nodriver CDP.

    Chrome is pre-launched by start_chrome.ps1 (called from run_app.bat).
    This function only CONNECTS — it never launches Chrome.

    Returns:
        (browser, proc, profile_dir, is_temp_profile)
    """
    import nodriver as uc

    port = SCRAPER_CHROME_PORT
    is_temp = profile_dir is None
    if is_temp:
        profile_dir = tempfile.mkdtemp(prefix='uc_')

    # Wait for Chrome CDP to be ready (it should already be running)
    # On Linux (EC2), auto-launch Chrome if not running
    for attempt in range(10):
        if is_chrome_cdp_ready(port):
            if attempt == 0:
                print(f"  [{tag}] Chrome ready on port {port}")
            else:
                print(f"  [{tag}] Chrome ready on port {port} (waited {attempt}s)")
            break
        if attempt == 0:
            print(f"  [{tag}] Waiting for Chrome on port {port}...")
            # On Linux, auto-launch Chrome if not running
            if sys.platform != 'win32':
                import subprocess as _sp
                chrome_path = find_chrome()
                _chrome_profile = os.path.join(tempfile.gettempdir(), f'uc_scraper_{port}')
                os.makedirs(_chrome_profile, exist_ok=True)
                _sp.Popen([
                    chrome_path,
                    f'--remote-debugging-port={port}',
                    f'--user-data-dir={_chrome_profile}',
                    '--no-first-run', '--no-default-browser-check',
                    '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
                    '--disable-software-rasterizer',
                    '--headless=new',
                    '--disable-features=IsolateOrigins,site-per-process',
                    '--disable-blink-features=AutomationControlled',
                    '--window-size=1280,720',
                    'about:blank',
                ], stdout=_sp.DEVNULL, stderr=_sp.DEVNULL)
                print(f"  [{tag}] Auto-launched Chrome on Linux (port {port})")
        await asyncio.sleep(1)
    else:
        raise RuntimeError(
            f"Chrome not available on port {port}. "
            f"Make sure run_app.bat launched Chrome via start_chrome.ps1"
        )

    # Ensure the local CDP websocket never goes through a system/SOCKS proxy.
    no_proxy_hosts = ['127.0.0.1', 'localhost']
    for env_key in ('NO_PROXY', 'no_proxy'):
        current = os.environ.get(env_key, '')
        parts = [p.strip() for p in current.split(',') if p.strip()]
        for host in no_proxy_hosts:
            if host not in parts:
                parts.append(host)
        os.environ[env_key] = ','.join(parts)

    # Connect via nodriver
    browser = await uc.Browser.create(
        host='127.0.0.1',
        port=port,
    )
    print(f"  [{tag}] Chrome connected (port: {port})")

    # === Apply stealth patches via CDP ===
    try:
        tab = browser.main_tab
        if tab is None:
            tab = await browser.get('about:blank')

        await tab.send(uc.cdp.page.add_script_to_evaluate_on_new_document(
            source="""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                window.chrome = window.chrome || {};
                window.chrome.runtime = window.chrome.runtime || {};
                const originalQuery = window.navigator.permissions.query;
                window.navigator.permissions.query = (parameters) => (
                    parameters.name === 'notifications' ?
                        Promise.resolve({ state: Notification.permission }) :
                        originalQuery(parameters)
                );
            """
        ))
        print(f"  [{tag}] Stealth patches applied (navigator.webdriver, chrome.runtime)")
    except Exception as e:
        print(f"  [{tag}] Warning: stealth patches failed: {e}")

    # Dummy proc for compatibility with scrapers
    class _Proc:
        pid = 0
        def poll(self): return None
        def kill(self): pass

    return browser, _Proc(), profile_dir, is_temp


def cleanup_browser(browser, proc, profile_dir, is_temp, tag="SCRAPER"):
    """Close browser connection and clean up temp profile.
    Does NOT kill Chrome — it's shared and pre-launched.
    """
    if browser:
        try:
            browser.stop()
        except Exception:
            pass

    if is_temp and profile_dir and os.path.isdir(profile_dir):
        try:
            shutil.rmtree(profile_dir)
            print(f"successfully removed temp profile {profile_dir}")
        except Exception:
            pass


def restart_chrome_with_proxy(proxy: str | None = None, tag="PROXY"):
    """Kill existing scraper Chrome and relaunch with/without proxy.

    Args:
        proxy: SOCKS5 proxy string like "socks5://ip:port", or None for direct.
        tag: Log tag prefix.
    """
    import subprocess as sp

    port = SCRAPER_CHROME_PORT
    profile_dir = os.path.join(tempfile.gettempdir(), f"uc_scraper_{port}")

    # 1. Kill existing Chrome on our CDP port
    print(f"  [{tag}] Restarting Chrome {'with proxy ' + proxy if proxy else 'direct (no proxy)'}...")
    if sys.platform == 'win32':
        # Find and kill Chrome using our profile dir
        try:
            sp.run(
                ['taskkill', '/F', '/IM', 'chrome.exe'],
                capture_output=True, timeout=10
            )
        except Exception:
            pass
    else:
        try:
            sp.run(['pkill', '-f', f'remote-debugging-port={port}'],
                   capture_output=True, timeout=5)
        except Exception:
            pass

    # Wait for port to free up
    import time as _time
    for _ in range(5):
        if not is_chrome_cdp_ready(port):
            break
        _time.sleep(1)

    # 2. Set proxy env var for start_chrome.ps1
    env = os.environ.copy()
    if proxy:
        env['SCRAPER_PROXY'] = proxy
    elif 'SCRAPER_PROXY' in env:
        del env['SCRAPER_PROXY']

    # 3. Relaunch Chrome
    chrome_path = find_chrome()
    args = [
        chrome_path,
        f'--remote-debugging-port={port}',
        f'--user-data-dir={profile_dir}',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=IsolateOrigins,site-per-process,LocalNetworkAccessChecks',
        '--disable-blink-features=AutomationControlled',
        '--window-size=1280,720',
    ]
    if proxy:
        args.append(f'--proxy-server={proxy}')

    sp.Popen(args, stdout=sp.DEVNULL, stderr=sp.DEVNULL, env=env)

    # 4. Wait for CDP to be ready
    for i in range(15):
        if is_chrome_cdp_ready(port):
            print(f"  [{tag}] Chrome ready on port {port} (waited {i}s)")
            return True
        _time.sleep(1)

    print(f"  [{tag}] WARNING: Chrome may not have started on port {port}")
    return False
