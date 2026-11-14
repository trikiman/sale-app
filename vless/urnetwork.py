"""Free RU residential egress via URnetwork (api.bringyour.com).

Why this exists
---------------
VkusVill drops datacenter ASNs and detects public VLESS feeds
(``vpn_detected`` on 66/208 candidates during v1.28 verification).
URnetwork provides free residential egress (30 GiB/day, no card or
phone required) that exits through real Russian ISP networks (e.g.
AS12389 Rostelecom) and passes VkusVill with HTTP 200 in ~2.7 s.

Integration design
------------------
- ``ensure_ru_proxy()`` creates an instant URnetwork account + RU proxy
  client once and persists credentials locally in
  ``data/urnetwork_proxy.json`` (gitignored — NEVER committed).
- ``build_urnetwork_outbounds()`` reads ONLY the local cache file and
  emits a standard xray ``socks`` outbound tagged ``urn-ru-0``. If the
  file does not exist (e.g. in CI / unit tests), it returns ``([], [])``
  so existing ``build_xray_config`` invariants stay untouched.
- ``xray``'s ``observatory`` + ``leastPing`` balancer probes ``urn-ru-0``
  against ``https://vkusvill.ru/favicon.ico`` alongside ``manual-*`` and
  ``node-*`` outbounds, automatically preferring whichever exit is live
  and fastest.
- **Fail open.** Any API/network error logs a warning and returns ``None``
  without breaking ``ensure_pool()`` or ``xray`` startup.
"""
from __future__ import annotations

import json
import logging
import os
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

_log = logging.getLogger(__name__)

_API_BASE = "https://api.bringyour.com"
_HTTP_TIMEOUT_S = 15.0
_FAIL_COOLDOWN_S = 600.0  # avoid hammering /auth/network-create on 429
_MAX_CACHE_AGE_S = 30 * 24 * 3600  # refresh client after 30 days

_LAST_FAIL_MONO: float = 0.0


def default_cache_path() -> Path:
    root = Path(__file__).resolve().parent.parent
    return root / "data" / "urnetwork_proxy.json"


def load_cached_proxy(cache_path: Path | None = None) -> dict[str, Any] | None:
    """Return cached RU proxy record if present, valid, and not expired."""
    path = cache_path or default_cache_path()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    host = str(data.get("host") or "").strip()
    port = int(data.get("port") or 0)
    token = str(data.get("auth_token") or "").strip()
    if not host or port <= 0 or not token:
        return None
    created_at = float(data.get("created_at") or 0)
    if created_at and (time.time() - created_at) > _MAX_CACHE_AGE_S:
        return None
    return data


def _save_cached_proxy(data: dict[str, Any], cache_path: Path) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = cache_path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(cache_path)
    try:
        os.chmod(cache_path, 0o600)
    except OSError:
        pass


def _provision_ru_proxy() -> dict[str, Any] | None:
    """Create a fresh URnetwork account and request a RU residential proxy."""
    try:
        import httpx
    except ImportError:
        return None

    network_name = f"sa{secrets.token_hex(6)}"
    with httpx.Client(timeout=_HTTP_TIMEOUT_S) as client:
        r1 = client.post(
            f"{_API_BASE}/auth/network-create",
            json={
                "terms": True,
                "product_updates": False,
                "network_name": network_name,
            },
        )
        if r1.status_code != 200:
            _log.warning(
                "URnetwork network-create failed: HTTP %s (%s)",
                r1.status_code,
                r1.text[:160],
            )
            return None
        d1 = r1.json()
        by_jwt = str(((d1.get("network") or {}).get("by_jwt")) or "").strip()
        if not by_jwt:
            _log.warning("URnetwork network-create missing network.by_jwt")
            return None

        r2 = client.post(
            f"{_API_BASE}/network/auth-client",
            headers={"Authorization": f"Bearer {by_jwt}"},
            json={
                "proxy_config": {
                    "initial_device_state": {
                        "country_code": "RU",
                    }
                }
            },
        )
        if r2.status_code != 200:
            _log.warning(
                "URnetwork auth-client failed: HTTP %s (%s)",
                r2.status_code,
                r2.text[:160],
            )
            return None
        d2 = r2.json()

    res = d2.get("proxy_config_result") or {}
    socks_url = str(res.get("socks_proxy_url") or "").strip()
    auth_token = str(res.get("auth_token") or "").strip()
    if not socks_url or not auth_token:
        _log.warning("URnetwork auth-client missing socks_proxy_url or auth_token")
        return None

    parsed = urlparse(socks_url)
    host = parsed.hostname or ""
    port = parsed.port or 0
    if not host or port <= 0:
        _log.warning("URnetwork returned unparseable socks_proxy_url: %r", socks_url)
        return None

    return {
        "provider": "urnetwork",
        "country": "RU",
        "host": host,
        "port": port,
        "socks_url": socks_url,
        "https_url": str(res.get("https_proxy_url") or ""),
        "auth_token": auth_token,
        "client_id": str(res.get("client_id") or ""),
        "by_jwt": by_jwt,
        "created_at": time.time(),
    }


def ensure_ru_proxy(
    cache_path: Path | None = None,
    *,
    force_refresh: bool = False,
    log_fn: Any = None,
) -> dict[str, Any] | None:
    """Return a cached RU URnetwork proxy or provision one if missing.

    Safe to call from ``ensure_pool()``: returns immediately when the cache
    file already exists, and respects a 10-minute cooldown after API errors.
    """
    global _LAST_FAIL_MONO

    path = cache_path or default_cache_path()
    if (
        cache_path is None
        and os.environ.get("PYTEST_CURRENT_TEST")
        and path == (Path(__file__).resolve().parent.parent / "data" / "urnetwork_proxy.json")
    ):
        return None
    if not force_refresh:
        cached = load_cached_proxy(path)
        if cached is not None:
            return cached

    now_mono = time.monotonic()
    if not force_refresh and _LAST_FAIL_MONO and (now_mono - _LAST_FAIL_MONO) < _FAIL_COOLDOWN_S:
        return None

    try:
        record = _provision_ru_proxy()
    except Exception as exc:  # noqa: BLE001 — fail open
        _log.warning("URnetwork provisioning error: %s", exc)
        record = None

    if record is None:
        _LAST_FAIL_MONO = now_mono
        return None

    _LAST_FAIL_MONO = 0.0
    try:
        _save_cached_proxy(record, path)
    except OSError as exc:
        _log.warning("Failed to save URnetwork cache %s: %s", path, exc)

    msg = f"URnetwork RU residential proxy provisioned: {record['host']}:{record['port']}"
    if log_fn is not None:
        log_fn(msg)
    else:
        _log.info(msg)
    return record


def build_urnetwork_outbounds(
    cache_path: Path | None = None,
) -> tuple[list[dict], list[str]]:
    """Build xray ``socks`` outbound from cached URnetwork RU proxy, if present.

    Performs NO network calls. Returns ``([], [])`` when no cached proxy is
    available so unit tests and offline config builds are unaffected.
    """
    cached = load_cached_proxy(cache_path)
    if cached is None:
        return [], []

    tag = "urn-ru-0"
    outbound = {
        "tag": tag,
        "protocol": "socks",
        "settings": {
            "servers": [
                {
                    "address": cached["host"],
                    "port": int(cached["port"]),
                    "users": [
                        {
                            "user": cached["auth_token"],
                            "pass": "",
                        }
                    ],
                }
            ]
        },
    }
    return [outbound], [tag]


__all__ = [
    "build_urnetwork_outbounds",
    "default_cache_path",
    "ensure_ru_proxy",
    "load_cached_proxy",
]
