"""product_details fallback tests.

Updated Phase 74 (v1.23): replace the stale ``requests.get`` mock (left over
from pre-v1.15 when product_details used ``requests``; it's been ``httpx``
since Phase 56) with an ``httpx.AsyncClient`` stub matching the pattern in
``backend/test_product_details_latency.py``.

Scope: endpoint returns the fallback payload when the bridge is unreachable,
and a repeat call within backoff does not re-issue the fetch.
"""
from __future__ import annotations

import json
import os
import sys
from typing import Any

import httpx
import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import backend.main as main
from backend import detail_events, detail_service


client = TestClient(main.app)


class _FakeResponse:
    def __init__(self, *, status_code: int, text: str) -> None:
        self.status_code = status_code
        self.text = text
        self.content = text.encode("utf-8")

        class _Elapsed:
            def total_seconds(self) -> float:
                return 0.05

        self.elapsed = _Elapsed()


class _AlwaysTimeoutClient:
    """httpx.AsyncClient stub that raises ConnectTimeout on every .get()."""

    calls = {"count": 0}

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    async def __aenter__(self) -> "_AlwaysTimeoutClient":
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get(self, url: str, headers: dict | None = None) -> _FakeResponse:
        _AlwaysTimeoutClient.calls["count"] += 1
        raise httpx.ConnectTimeout("timeout")


def _stub_record(monkeypatch: pytest.MonkeyPatch, *, pid: str, weight: str, image: str) -> None:
    monkeypatch.setattr(
        main,
        "_load_product_record",
        lambda p: {
            "id": pid,
            "url": "https://vkusvill.ru/goods/test-42.html",
            "weight": weight,
            "image": image,
        },
    )


def test_product_details_returns_fallback_payload_on_upstream_timeout(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    _stub_record(monkeypatch, pid="42", weight="500 г", image="https://img.example/test.webp")
    monkeypatch.setattr(detail_service, "read_cache", lambda pid: None)
    monkeypatch.setattr(detail_events, "LEDGER_PATH", str(tmp_path / "detail_events.jsonl"))
    monkeypatch.setattr(httpx, "AsyncClient", _AlwaysTimeoutClient)
    _AlwaysTimeoutClient.calls = {"count": 0}

    response = client.get("/api/product/42/details")

    assert response.status_code == 200
    body = response.json()
    assert body["id"] == "42"
    assert body["weight"] == "500 г"
    # Fallback preserves the existing catalog image when upstream is down
    assert body["images"] == ["https://img.example/test.webp"]
    assert body["source_unavailable"] is True
    # 3 retries per v1.23 PERF-10 retry budget
    assert _AlwaysTimeoutClient.calls["count"] == 3


def test_product_details_cache_hit_skips_fetch(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    """Second call after cache write must not re-fetch."""
    _stub_record(monkeypatch, pid="42", weight="", image="")
    monkeypatch.setattr(detail_events, "LEDGER_PATH", str(tmp_path / "detail_events.jsonl"))

    call_count = {"n": 0}

    def _read_cache_flaky(pid: str) -> dict | None:
        # First call returns None (cache miss), second returns a cached dict
        call_count["n"] += 1
        if call_count["n"] == 1:
            return None
        return {"id": pid, "cached": True}

    monkeypatch.setattr(detail_service, "read_cache", _read_cache_flaky)
    monkeypatch.setattr(httpx, "AsyncClient", _AlwaysTimeoutClient)
    _AlwaysTimeoutClient.calls = {"count": 0}

    first = client.get("/api/product/42/details")
    second = client.get("/api/product/42/details")

    assert first.status_code == 200
    assert second.status_code == 200
    # First call fetched (3 retries all timed out), second hit cache (0 fetches)
    assert _AlwaysTimeoutClient.calls["count"] == 3
    assert second.json() == {"id": "42", "cached": True}
