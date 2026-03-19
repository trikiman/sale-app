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
    for attempt in range(10):
        if is_chrome_cdp_ready(port):
            if attempt == 0:
                print(f"  [{tag}] Chrome ready on port {port}")
            else:
                print(f"  [{tag}] Chrome ready on port {port} (waited {attempt}s)")
            break
        if attempt == 0:
            print(f"  [{tag}] Waiting for Chrome on port {port}...")
        await asyncio.sleep(1)
    else:
        raise RuntimeError(
            f"Chrome not available on port {port}. "
            f"Make sure run_app.bat launched Chrome via start_chrome.ps1"
        )

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
