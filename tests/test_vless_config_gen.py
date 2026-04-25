"""Tests for :mod:`vless.config_gen` — xray-core config generation."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from vless.config_gen import (
    XRAY_LISTEN_HOST,
    XRAY_LISTEN_PORT,
    build_xray_config,
)
from vless.parser import VlessNode, parse_vless_list

_FIXTURE = Path(__file__).parent / "fixtures" / "vless_sample.txt"


def _sample_nodes(n: int = 3) -> list[VlessNode]:
    nodes, _errors = parse_vless_list(_FIXTURE.read_text(encoding="utf-8"))
    return nodes[:n]


def test_single_socks_inbound_on_default_host_port():
    config = build_xray_config(_sample_nodes(1))
    inbounds = config["inbounds"]
    assert len(inbounds) == 1
    assert inbounds[0]["protocol"] == "socks"
    assert inbounds[0]["listen"] == XRAY_LISTEN_HOST
    assert inbounds[0]["port"] == XRAY_LISTEN_PORT
    assert inbounds[0]["settings"]["auth"] == "noauth"
    assert inbounds[0]["settings"]["udp"] is True


def test_outbound_shape_matches_nodes():
    nodes = _sample_nodes(2)
    config = build_xray_config(nodes)
    # Two VLESS outbounds + direct + block fallbacks.
    assert len(config["outbounds"]) == len(nodes) + 2

    for idx, node in enumerate(nodes):
        outbound = config["outbounds"][idx]
        assert outbound["tag"] == f"node-{idx}"
        assert outbound["protocol"] == "vless"
        vnext = outbound["settings"]["vnext"][0]
        assert vnext["address"] == node.host
        assert vnext["port"] == node.port
        assert vnext["users"][0]["id"] == node.uuid
        assert vnext["users"][0]["encryption"] == node.encryption
        if node.flow:
            assert vnext["users"][0]["flow"] == node.flow
        stream = outbound["streamSettings"]
        assert stream["security"] == "reality"
        assert stream["realitySettings"]["publicKey"] == node.reality_pbk
        assert stream["realitySettings"]["serverName"] == node.reality_sni


def test_balancer_references_every_node_tag():
    nodes = _sample_nodes(3)
    config = build_xray_config(nodes)
    balancers = config["routing"]["balancers"]
    assert len(balancers) == 1
    balancer = balancers[0]
    assert balancer["tag"] == "ru-balancer"
    assert balancer["strategy"] == {"type": "leastPing"}
    assert balancer["selector"] == [f"node-{i}" for i in range(len(nodes))]
    # One routing rule that sends all inbound traffic to the balancer.
    rules = config["routing"]["rules"]
    assert len(rules) == 1
    assert rules[0]["balancerTag"] == "ru-balancer"
    assert rules[0]["inboundTag"] == ["socks-in"]


def test_empty_node_list_raises():
    with pytest.raises(ValueError):
        build_xray_config([])


def test_config_is_json_serializable():
    config = build_xray_config(_sample_nodes(3))
    # json.dumps must succeed without a default= hook — the generator
    # promises JSON-safe types only.
    serialized = json.dumps(config)
    # And the round-trip must preserve the shape.
    reparsed = json.loads(serialized)
    assert reparsed["routing"]["balancers"][0]["selector"] == [
        "node-0",
        "node-1",
        "node-2",
    ]


def test_custom_listen_host_port_is_honored():
    config = build_xray_config(
        _sample_nodes(1), listen_host="0.0.0.0", listen_port=20808
    )
    assert config["inbounds"][0]["listen"] == "0.0.0.0"
    assert config["inbounds"][0]["port"] == 20808


def test_build_xray_config_has_policy_block():
    config = build_xray_config(_sample_nodes(1))
    assert "policy" in config
    level0 = config["policy"]["levels"]["0"]
    assert level0["connIdle"] == 30, "connIdle must be 30s, not xray default 300s"
    assert level0["handshake"] == 8, "handshake must be 8s to fit VLESS+Reality (3-5s observed)"
    assert level0["bufferSize"] == 4096
    assert level0["statsUserUplink"] is False
    assert level0["statsUserDownlink"] is False


def test_build_xray_config_has_observatory():
    config = build_xray_config(_sample_nodes(1))
    assert "observatory" in config
    obs = config["observatory"]
    assert obs["subjectSelector"] == ["node-"]
    assert obs["probeUrl"] == "https://www.google.com/generate_204"
    assert obs["probeInterval"] == "5m"


def test_build_xray_config_balancer_uses_least_ping():
    nodes = _sample_nodes(2)
    config = build_xray_config(nodes)
    balancer = config["routing"]["balancers"][0]
    assert balancer["strategy"] == {"type": "leastPing"}
    assert set(balancer["selector"]) == {"node-0", "node-1"}


def test_build_xray_config_is_json_serializable_with_new_sections():
    config = build_xray_config(_sample_nodes(1))
    serialized = json.dumps(config, indent=2)
    roundtripped = json.loads(serialized)
    assert roundtripped["policy"]["levels"]["0"]["connIdle"] == 30
    assert roundtripped["observatory"]["probeInterval"] == "5m"
    assert roundtripped["routing"]["balancers"][0]["strategy"] == {"type": "leastPing"}


def test_spider_x_only_included_when_present():
    nodes = _sample_nodes(3)
    config = build_xray_config(nodes)
    settings_by_tag = {
        ob["tag"]: ob["streamSettings"]["realitySettings"]
        for ob in config["outbounds"]
        if ob["protocol"] == "vless"
    }
    # node-0 has spx=/ in the fixture → spiderX should be present.
    assert settings_by_tag["node-0"].get("spiderX") == "/"
    # node-1 omits spx → spiderX should NOT be present.
    assert "spiderX" not in settings_by_tag["node-1"]
