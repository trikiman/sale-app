"""Make the archived ``proxy_manager`` importable for the legacy test suite.

The production ``proxy_manager.py`` at the repo root is a shim that
re-exports :class:`vless.manager.VlessProxyManager`; the archived SOCKS5
implementation lives at ``legacy/proxy-socks5/proxy_manager.py`` (this file's
parent directory). Inserting that directory at the head of ``sys.path`` lets
the archived tests say ``import proxy_manager`` and get the historical
module, not the shim, so their SOCKS5 internals (``_socks5_preflight``,
``_test_proxy``) are reachable.

This only affects runs under ``legacy/proxy-socks5/tests``; the normal
``pytest`` invocation (with ``testpaths = backend`` plus explicit
``tests/`` arg) never loads this conftest.
"""
from __future__ import annotations

import sys
from pathlib import Path

_LEGACY_DIR = Path(__file__).resolve().parent.parent
if str(_LEGACY_DIR) not in sys.path:
    sys.path.insert(0, str(_LEGACY_DIR))
