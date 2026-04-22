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

import importlib.util
import sys
from pathlib import Path

_LEGACY_DIR = Path(__file__).resolve().parent.parent
_ARCHIVED_MODULE = _LEGACY_DIR / "proxy_manager.py"

# Always bind ``proxy_manager`` to the archived file before these tests run,
# even if a sibling suite already imported the production shim in the same
# pytest session (e.g. ``pytest tests/ legacy/``). Rebinding via
# ``importlib`` wins over any sys.path ordering the outer suite may have
# established, so the archived tests' ``import proxy_manager`` reliably
# hits the SOCKS5 implementation.
_spec = importlib.util.spec_from_file_location("proxy_manager", _ARCHIVED_MODULE)
_archived = importlib.util.module_from_spec(_spec)
sys.modules["proxy_manager"] = _archived
_spec.loader.exec_module(_archived)
