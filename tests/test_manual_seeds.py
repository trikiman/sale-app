"""Unit tests for vless.manual_seeds and its integration with build_xray_config.

Operator added 6 known-working RU trojan endpoints as a fallback floor
on 2026-05-23. They must:
  1. Be present in every xray config regardless of dynamic pool state.
  2. Be picked up by both observatory probes and the leastPing balancer.
  3. Survive when build_xray_config is called with nodes=[] (previously
     raised ValueError; now manual seeds keep it valid).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from vless.config_gen import build_xray_config  # noqa: E402
from vless.manual_seeds import (  # noqa: E402
    MANUAL_TROJAN_SEEDS,
    build_manual_outbounds,
)


def test_manual_seeds_constant_has_at_least_six_entries() -> None:
    """Operator-supplied 6 endpoints — guard against accidental list-edit slip."""
    assert len(MANUAL_TROJAN_SEEDS) == 6
    for host, port, ws_path in MANUAL_TROJAN_SEEDS:
        assert isinstance(host, str) and host
        assert isinstance(port, int) and 1 <= port <= 65535
        assert ws_path.startswith("/")


def test_build_manual_outbounds_produces_valid_xray_shape() -> None:
    """Each outbound must conform to xray-core's trojan outbound spec."""
    outbounds, tags = build_manual_outbounds()
    assert len(outbounds) == 6
    assert tags == [f"manual-{i}" for i in range(6)]
    for ob in outbounds:
        assert ob["protocol"] == "trojan"
        assert ob["tag"].startswith("manual-")
        servers = ob["settings"]["servers"]
        assert len(servers) == 1
        assert "address" in servers[0] and "port" in servers[0] and "password" in servers[0]
        ss = ob["streamSettings"]
        assert ss["network"] == "ws"
        assert ss["security"] == "tls"
        assert ss["tlsSettings"]["serverName"]
        assert ss["wsSettings"]["path"].startswith("/")


def test_build_manual_outbounds_respects_start_idx() -> None:
    """``start_idx`` controls tag numbering for appending after dynamic nodes."""
    outbounds, tags = build_manual_outbounds(start_idx=10)
    assert tags == [f"manual-{i}" for i in range(10, 16)]
    assert all(o["tag"] == t for o, t in zip(outbounds, tags))


def test_xray_config_with_empty_nodes_succeeds_with_manual_seeds() -> None:
    """Pre-v1.27: empty nodes raised ValueError. Now manual seeds keep
    the config valid as a safety floor."""
    cfg = build_xray_config(nodes=[])
    outbounds = cfg["outbounds"]
    # 6 manual + direct + block
    assert len(outbounds) == 8
    manual_count = sum(1 for o in outbounds if o["tag"].startswith("manual-"))
    assert manual_count == 6
    # Balancer must route through manual seeds when they're the only options.
    selector = cfg["routing"]["balancers"][0]["selector"]
    assert selector == [f"manual-{i}" for i in range(6)]
    # Observatory must probe manual seeds.
    assert "manual-" in cfg["observatory"]["subjectSelector"]


def test_xray_config_appends_manual_seeds_after_dynamic_nodes() -> None:
    """Dynamic VLESS nodes use ``node-N``; manual seeds use ``manual-N``;
    selector lists both in that order."""
    from vless.parser import VlessNode

    fake_node = VlessNode(
        uuid="00000000-0000-0000-0000-000000000000",
        host="1.2.3.4",
        port=443,
        name="fake",
        reality_pbk="x",
        reality_sni="example.com",
    )
    cfg = build_xray_config(nodes=[fake_node, fake_node])
    selector = cfg["routing"]["balancers"][0]["selector"]
    assert selector[:2] == ["node-0", "node-1"]
    assert selector[2:] == [f"manual-{i}" for i in range(6)]
