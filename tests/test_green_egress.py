"""v1.30 Phase 97 (GREEN-EGRESS-01) — URnetwork must be the working channel.

Measured 2026-11-16 on the Oracle box: the VLESS pool decayed to one node and
the scheduler logged

    VkusVill: BLOCKED (direct connection failed)
    Pool low (2/5) — refreshing...
    Removed VLESS node 37.235.247.81 (cooldown:reprobe_fail); pool 2 → 1

so full cycles and green cycles stalled and `green_products.json` stopped
advancing. URnetwork was already working for `basket_recalc`, but `urn-ru-0` was
only a *member of the leastPing balancer* — membership is not priority, and Xray
kept choosing dead VLESS nodes.

Three changes are pinned here:
1. a dedicated inbound (10809) with a pinned route to the UR outbound;
2. preflight probes that inbound first and reports which route answered;
3. `proxy_candidates()` puts URnetwork before the env/VLESS fallback.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


# ── 1. config_gen: pinned inbound + pinned route ────────────────────────


def _config_with_urn(monkeypatch):
    from vless import config_gen

    monkeypatch.setattr(
        "vless.urnetwork.build_urnetwork_outbounds",
        lambda: ([{"tag": "urn-ru-0", "protocol": "socks",
                   "settings": {"servers": [{"address": "127.0.0.1", "port": 7117}]}}], ["urn-ru-0"]),
    )
    return config_gen.build_xray_config([], include_urnetwork=True)


def _config_without_urn(monkeypatch):
    from vless import config_gen

    monkeypatch.setattr(
        "vless.urnetwork.build_urnetwork_outbounds", lambda: ([], []),
    )
    return config_gen.build_xray_config([], include_urnetwork=True)


def test_pinned_inbound_exists_only_with_a_urn_outbound(monkeypatch) -> None:
    with_urn = _config_with_urn(monkeypatch)
    tags = [i["tag"] for i in with_urn["inbounds"]]
    assert "urn-socks-in" in tags, "no dedicated URnetwork inbound"
    urn_in = next(i for i in with_urn["inbounds"] if i["tag"] == "urn-socks-in")
    assert urn_in["port"] == 10809
    assert urn_in["protocol"] == "socks"

    without = _config_without_urn(monkeypatch)
    assert "urn-socks-in" not in [i["tag"] for i in without["inbounds"]], (
        "inbound must not exist without a UR cache — it would route into nothing"
    )


def test_urn_traffic_is_pinned_not_balanced(monkeypatch) -> None:
    cfg = _config_with_urn(monkeypatch)
    rules = cfg["routing"]["rules"]
    assert rules[0]["inboundTag"] == ["urn-socks-in"], "pinned rule must come first"
    assert rules[0]["outboundTag"] == "urn-ru-0", (
        "UR inbound must be pinned to the UR outbound; routing by balancerTag "
        "lets leastPing pick a dead VLESS node — the original bug"
    )
    # the general path still uses the balancer
    assert any(r.get("balancerTag") for r in rules[1:]), "balancer rule disappeared"


def test_general_inbound_still_uses_the_balancer(monkeypatch) -> None:
    cfg = _config_with_urn(monkeypatch)
    general = [r for r in cfg["routing"]["rules"] if r["inboundTag"] == ["socks-in"]]
    assert general and "balancerTag" in general[0]


# ── 2. preflight: UR first, per-route cache, route reported ─────────────


def test_probe_order_is_urnetwork_then_vless() -> None:
    from vless import preflight

    routes = [r for r, _ in preflight._BRIDGE_PROXIES]
    assert routes == ["urnetwork", "vless"], routes
    ports = [p.rsplit(":", 1)[1] for _, p in preflight._BRIDGE_PROXIES]
    assert ports == ["10809", "10808"], ports


def _stub_client(status=None, raise_exc=None, seen=None, marker=None):
    class _Resp:
        def __init__(self, code):
            self.status_code = code

    class _Client:
        def __init__(self, proxy=None, **kwargs):
            if seen is not None:
                seen.append(proxy)

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def get(self, url):
            if raise_exc is not None:
                raise raise_exc
            return _Resp(status)

    return _Client


def test_probe_falls_back_when_urnetwork_is_dead(monkeypatch) -> None:
    from vless import preflight

    preflight.reset_probe_cache()
    calls = []

    original = preflight._probe_once

    def fake_once(proxy, timeout, route):
        calls.append(route)
        if route == "urnetwork":
            return preflight.ProbeResult(False, None, "connect_error", 0.1, route=route)
        return preflight.ProbeResult(True, 200, "ok", 0.1, route=route)

    monkeypatch.setattr(preflight, "_probe_once", fake_once)
    try:
        result = preflight.probe_bridge_alive()
        assert calls == ["urnetwork", "vless"], calls
        assert result.ok and result.route == "vless"
    finally:
        monkeypatch.setattr(preflight, "_probe_once", original)
        preflight.reset_probe_cache()


def test_probe_cache_is_per_route(monkeypatch) -> None:
    """A healthy URnetwork must not vouch for a dead balancer."""
    from vless import preflight

    preflight.reset_probe_cache()
    original = preflight._probe_once

    def fake_once(proxy, timeout, route):
        if route == "urnetwork":
            return preflight.ProbeResult(True, 200, "ok", 0.1, route=route)
        return preflight.ProbeResult(False, None, "timeout", 0.1, route=route)

    monkeypatch.setattr(preflight, "_probe_once", fake_once)
    try:
        first = preflight.probe_bridge_alive()
        assert first.route == "urnetwork"
        assert set(preflight._LAST_SUCCESS_AT) == {"urnetwork"}
        # cached hit still names its route
        second = preflight.probe_bridge_alive()
        assert second.cached and second.route == "urnetwork"
    finally:
        monkeypatch.setattr(preflight, "_probe_once", original)
        preflight.reset_probe_cache()


# ── 3. proxy_candidates order ───────────────────────────────────────────


def test_proxy_candidates_prefers_urnetwork(monkeypatch) -> None:
    from vless import urnetwork

    monkeypatch.setattr(urnetwork, "socks_proxy_url", lambda: "socks5h://urn:7117")
    monkeypatch.setenv("SOCKS_PROXY", "socks5h://127.0.0.1:10808")
    cands = urnetwork.proxy_candidates()
    assert cands[0] == "socks5h://urn:7117", (
        "env/VLESS must be the fallback, not the first attempt — otherwise every "
        "scrape burns its timeout on a dead node while a working exit waits"
    )
    assert cands[1] == "socks5h://127.0.0.1:10808"


def test_proxy_candidates_still_works_without_urn(monkeypatch) -> None:
    from vless import urnetwork

    monkeypatch.setattr(urnetwork, "socks_proxy_url", lambda: None)
    monkeypatch.setenv("SOCKS_PROXY", "socks5h://127.0.0.1:10808")
    assert urnetwork.proxy_candidates() == ["socks5h://127.0.0.1:10808"]