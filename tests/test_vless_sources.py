"""Unit tests for ``vless.sources._fetch_one`` base64 auto-decode.

Regression test for v1.27 — operator added a v2nodes.com paid
subscription to ``EXTRA_VLESS_SOURCES``. v2nodes returns base64-encoded
bodies. The plain-text fetcher used to silently let those bodies through
unchanged, which made ``parse_vless_list`` see no nodes from that
source. _fetch_one now auto-decodes base64 when the raw body has no
``vless://`` literal but the decoded text does.
"""
from __future__ import annotations

import base64
import io
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from vless import sources  # noqa: E402


class _FakeResponse:
    """Minimal urllib response stub for ``_fetch_one``."""

    def __init__(self, body: bytes, charset: str = "utf-8") -> None:
        self._body = body
        self._charset = charset

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    @property
    def headers(self):  # noqa: D401
        return _FakeHeaders(self._charset)


class _FakeHeaders:
    def __init__(self, charset: str) -> None:
        self._charset = charset

    def get_content_charset(self) -> str:
        return self._charset


def _patch_urlopen(body: bytes):
    return patch.object(
        sources.urllib.request,
        "urlopen",
        lambda req, timeout=None: _FakeResponse(body),
    )


def test_fetch_one_passes_plain_text_unchanged() -> None:
    """Plain ``vless://`` bodies must not be base64-decoded — they would
    fail because random text rarely round-trips through base64 cleanly."""
    plain = "vless://uuid@host:443?security=reality\nvless://other@h2:443\n"
    with _patch_urlopen(plain.encode("utf-8")):
        result = sources._fetch_one("https://example/plain.txt", timeout=5)
    assert result == plain


def test_fetch_one_decodes_base64_subscription() -> None:
    """v2nodes-style base64 body must be decoded to plain ``vless://``."""
    inner = "vless://uuid@host:443?security=reality&type=tcp\n"
    encoded = base64.b64encode(inner.encode("utf-8")).decode("ascii")
    with _patch_urlopen(encoded.encode("ascii")):
        result = sources._fetch_one("https://v2nodes/sub", timeout=5)
    assert "vless://" in result
    assert result.strip() == inner.strip()


def test_fetch_one_handles_missing_base64_padding() -> None:
    """Subscription endpoints sometimes omit ``=`` padding."""
    inner = "vless://uuid@h:443?security=reality\n"
    encoded = base64.b64encode(inner.encode("utf-8")).decode("ascii").rstrip("=")
    with _patch_urlopen(encoded.encode("ascii")):
        result = sources._fetch_one("https://v2nodes/sub", timeout=5)
    assert "vless://" in result


def test_fetch_one_falls_back_to_raw_when_b64_decode_yields_garbage() -> None:
    """If the body isn't base64 AND has no ``vless://``, return raw text
    unchanged so callers see the original error rather than corrupted
    binary output."""
    junk = "<html><body>404 not found</body></html>"
    with _patch_urlopen(junk.encode("utf-8")):
        result = sources._fetch_one("https://broken/source", timeout=5)
    assert result == junk
