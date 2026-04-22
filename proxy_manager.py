"""Compatibility shim: proxy_manager → vless.manager (VLESS+Reality migration).

v1.15 replaced the free SOCKS5 pool with a VLESS+Reality pool behind a local
xray-core SOCKS5 bridge. The old implementation lives under
``legacy/proxy-socks5/proxy_manager.py`` (preserved for one-operation rollback).

For the legacy behavior, see ``legacy/README.md`` and run:

    git revert <commit-of-this-shim>

Callers do not need any code changes — every public method of the old
``ProxyManager`` is preserved on ``VlessProxyManager`` via the 56-03 contract.
"""
from vless.manager import VlessProxyManager as ProxyManager

__all__ = ["ProxyManager"]
