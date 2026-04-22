"""VLESS+Reality proxy pool support for the VkusVill scraper.

This package replaces the free-SOCKS5 proxy pool with a VLESS+Reality pool
tunneled through a local ``xray-core`` SOCKS5 bridge. The 56-01 layer exposes
only the pure-Python pieces (URL parsing, xray config generation, source
fetching + geo filtering). Higher-level pieces (the subprocess bridge and the
``ProxyManager``-compatible manager) land in subsequent plans.
"""
from vless.config_gen import (
    XRAY_LISTEN_HOST,
    XRAY_LISTEN_PORT,
    build_xray_config,
)
from vless.parser import (
    VlessNode,
    VlessParseError,
    parse_vless_list,
    parse_vless_url,
)

# ``vless.sources`` is deliberately NOT imported eagerly: importing it from a
# package __init__ and then running ``python -m vless.sources`` races with
# runpy and emits a spurious RuntimeWarning. Callers that need the source
# fetcher should ``from vless import sources`` (or import its symbols
# explicitly).

__all__ = [
    "VlessNode",
    "VlessParseError",
    "parse_vless_url",
    "parse_vless_list",
    "build_xray_config",
    "XRAY_LISTEN_HOST",
    "XRAY_LISTEN_PORT",
]
