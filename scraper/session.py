"""
VkusVill Session Manager
Handles authenticated requests with cookies
"""
import json
import os
import time
import requests
from typing import Optional, Dict, Any

import config


class VkusVillSession:
    """Manages authenticated session for VkusVill scraping"""
    
    def __init__(self):
        self.session = requests.Session()
        self._setup_headers()
        self._load_cookies()
    
    def _setup_headers(self):
        """Set up browser-like headers to avoid detection"""
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0"
        })
    
    def _load_cookies(self):
        """Load cookies from file if available"""
        if os.path.exists(config.COOKIES_FILE):
            try:
                with open(config.COOKIES_FILE, 'r', encoding='utf-8') as f:
                    cookies = json.load(f)
                    for cookie in cookies:
                        # Handle both simple and complex cookie formats
                        if isinstance(cookie, dict):
                            name = cookie.get('name')
                            value = cookie.get('value')
                            if name and value:
                                self.session.cookies.set(
                                    name, 
                                    value,
                                    domain=cookie.get('domain', '.vkusvill.ru'),
                                    path=cookie.get('path', '/')
                                )
                        elif isinstance(cookie, str):
                            # Simple name=value format
                            if '=' in cookie:
                                name, value = cookie.split('=', 1)
                                self.session.cookies.set(name.strip(), value.strip())
                print(f"Loaded {len(self.session.cookies)} cookies from {config.COOKIES_FILE}")
            except Exception as e:
                print(f"Error loading cookies: {e}")
        else:
            print(f"Warning: Cookies file not found at {config.COOKIES_FILE}")
            print("You need to export cookies from your logged-in browser session.")
    
    def save_cookies(self):
        """Save current session cookies to file"""
        cookies = []
        for cookie in self.session.cookies:
            cookies.append({
                'name': cookie.name,
                'value': cookie.value,
                'domain': cookie.domain,
                'path': cookie.path
            })
        
        os.makedirs(os.path.dirname(config.COOKIES_FILE), exist_ok=True)
        with open(config.COOKIES_FILE, 'w', encoding='utf-8') as f:
            json.dump(cookies, f, indent=2, ensure_ascii=False)
        print(f"Saved {len(cookies)} cookies to {config.COOKIES_FILE}")
    
    def get(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Make GET request with retry logic"""
        max_retries = 3
        retry_delay = config.REQUEST_DELAY
        
        for attempt in range(max_retries):
            try:
                response = self.session.get(
                    url, 
                    timeout=config.REQUEST_TIMEOUT,
                    **kwargs
                )
                response.raise_for_status()
                
                # Add delay between requests to avoid rate limiting
                time.sleep(config.REQUEST_DELAY)
                
                return response
                
            except requests.exceptions.RequestException as e:
                print(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    print(f"All retries exhausted for URL: {url}")
                    return None
        
        return None
    
    def is_logged_in(self) -> bool:
        """Check if the current session is authenticated"""
        # Try to access a page that requires login
        response = self.get(config.VKUSVILL_BASE_URL + "/cart/")
        if response:
            # Check if redirected to login or if cart content is visible
            return "Зелёные ценники" in response.text or "Мой заказ" in response.text
        return False


# Global session instance
_session_instance: Optional[VkusVillSession] = None


def get_session() -> VkusVillSession:
    """Get or create the global session instance"""
    global _session_instance
    if _session_instance is None:
        _session_instance = VkusVillSession()
    return _session_instance
