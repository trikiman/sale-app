"""Tests for :mod:`vless.urnetwork` — free RU residential egress."""
from __future__ import annotations

import json
import time

import pytest

from vless import config_gen, urnetwork


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    cache_file = tmp_path / "urnetwork_proxy.json"
    monkeypatch.setattr(urnetwork, "default_cache_path", lambda: cache_file)
    monkeypatch.setattr(urnetwork, "_LAST_FAIL_MONO", 0.0)
    yield cache_file


def test_build_outbounds_empty_when_no_cache():
    outbounds, tags = urnetwork.build_urnetwork_outbounds()
    assert outbounds == []
    assert tags == []


def test_build_outbounds_shape_from_cache(_isolated_cache):
    _isolated_cache.write_text(
        json.dumps(
            {
                "host": "crisp.bringyour.com",
                "port": 7117,
                "auth_token": "TEST_TOKEN_123",
                "created_at": time.time(),
            }
        ),
        encoding="utf-8",
    )

    outbounds, tags = urnetwork.build_urnetwork_outbounds()

    assert tags == ["urn-ru-0"]
    assert len(outbounds) == 1
    ob = outbounds[0]
    assert ob["tag"] == "urn-ru-0"
    assert ob["protocol"] == "socks"
    srv = ob["settings"]["servers"][0]
    assert srv["address"] == "crisp.bringyour.com"
    assert srv["port"] == 7117
    assert srv["users"] == [{"user": "TEST_TOKEN_123", "pass": ""}]


def test_ensure_ru_proxy_provisions_and_caches(monkeypatch, _isolated_cache):
    calls = []

    def fake_provision():
        calls.append(1)
        return {
            "provider": "urnetwork",
            "country": "RU",
            "host": "crisp.bringyour.com",
            "port": 7117,
            "auth_token": "TOK_ABC",
            "created_at": time.time(),
        }

    monkeypatch.setattr(urnetwork, "_provision_ru_proxy", fake_provision)

    first = urnetwork.ensure_ru_proxy()
    second = urnetwork.ensure_ru_proxy()

    assert first is not None and first["auth_token"] == "TOK_ABC"
    assert second is not None and second["auth_token"] == "TOK_ABC"
    assert len(calls) == 1, "second call must hit disk cache"
    assert _isolated_cache.exists()


def test_ensure_ru_proxy_fails_open_with_cooldown(monkeypatch):
    calls = []

    def boom():
        calls.append(1)
        raise RuntimeError("network down")

    monkeypatch.setattr(urnetwork, "_provision_ru_proxy", boom)

    assert urnetwork.ensure_ru_proxy() is None
    assert urnetwork.ensure_ru_proxy() is None
    assert len(calls) == 1, "cooldown should suppress immediate retry"


def test_config_gen_includes_urnetwork_when_cached(_isolated_cache):
    _isolated_cache.write_text(
        json.dumps(
            {
                "host": "crisp.bringyour.com",
                "port": 7117,
                "auth_token": "TOK_CFG",
                "created_at": time.time(),
            }
        ),
        encoding="utf-8",
    )

    cfg = config_gen.build_xray_config([])
    tags = [o["tag"] for o in cfg["outbounds"]]
    assert "urn-ru-0" in tags
    assert "urn-ru-0" in cfg["routing"]["balancers"][0]["selector"]
    assert "urn-" in cfg["observatory"]["subjectSelector"]

    # Probe configs must exclude urnetwork so candidates are tested on their own
    probe_cfg = config_gen.build_xray_config([], include_urnetwork=False)
    assert "urn-ru-0" not in [o["tag"] for o in probe_cfg["outbounds"]]
    assert "urn-" not in probe_cfg["observatory"]["subjectSelector"]
