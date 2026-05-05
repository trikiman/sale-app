"""Phase 60 REL-06: regression guard for xray observatory probeURL.

The reverted PR #25 / v1.18 postmortem identified that xray was ranking
outbounds by ping time to ``google.com/generate_204`` while real traffic
went to VkusVill. A node blocked by VkusVill's WAF but otherwise fast still
won the ``leastPing`` race, so the balancer silently preferred degraded
nodes. Phase 60 fixed this by changing the probe URL to a VkusVill
endpoint. These tests ensure the fix cannot regress without visible test
failure.
"""
from __future__ import annotations

import pytest

from vless.config_gen import build_xray_config
from vless.parser import VlessNode


def _fake_node() -> VlessNode:
    """Minimal but valid VlessNode for config_gen to build a config from."""
    return VlessNode(
        uuid="00000000-0000-0000-0000-000000000000",
        host="127.0.0.1",
        port=443,
        name="test-node",
        reality_pbk="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
        reality_sni="example.com",
        reality_sid="00",
        reality_fp="chrome",
        security="reality",
    )


def test_probe_url_targets_vkusvill_not_google():
    cfg = build_xray_config([_fake_node()])
    probe = cfg["observatory"]["probeURL"]
    assert "vkusvill.ru" in probe, (
        f"probeURL regressed to '{probe}'. Must target vkusvill.ru per "
        "REL-06. Re-read .planning/phases/60-observatory-probe-and-circuit-"
        "breaker/README.md before changing."
    )
    assert "google.com" not in probe, (
        f"probeURL regressed to Google: '{probe}'. This was the silent-"
        "killer root cause in v1.18: leastPing ranked by Google ping "
        "instead of VkusVill reachability. Do not re-introduce."
    )


def test_probe_interval_is_at_most_sixty_seconds():
    cfg = build_xray_config([_fake_node()])
    interval = cfg["observatory"]["probeInterval"]
    # Accept 60s / 30s / 15s / 10s; reject "5m" or anything minute-granularity.
    assert interval.endswith("s"), (
        f"probeInterval '{interval}' must be in seconds. 'm' granularity "
        "means degraded nodes stay ranked high for up to 5 minutes."
    )
    value = int(interval.rstrip("s"))
    assert value <= 60, (
        f"probeInterval {interval} is > 60s. REL-06 requires <= 60s so the "
        "balancer notices a degraded node within one minute."
    )


def test_balancer_uses_leastping_strategy():
    cfg = build_xray_config([_fake_node()])
    balancers = cfg["routing"]["balancers"]
    assert balancers, "at least one balancer must exist in the routing config"
    assert balancers[0]["strategy"]["type"] == "leastPing", (
        "probeURL fix is only meaningful when leastPing is the strategy. "
        "Do not regress to random or roundRobin without revisiting REL-06."
    )


def test_multiple_nodes_share_single_observatory_probeURL():
    """Observatory is a single shared block, not per-outbound."""
    nodes = [_fake_node(), _fake_node()]
    cfg = build_xray_config(nodes)
    # The observatory dict has exactly one probeURL; ranking applies to
    # all ``node-N`` subjects uniformly.
    assert isinstance(cfg["observatory"]["probeURL"], str)
    assert cfg["observatory"]["subjectSelector"] == ["node-"]
