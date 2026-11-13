"""Tests for :mod:`vless.asn_filter` — offline, no network access required.

The module's whole job is to drop candidates from measured-blocked ASNs
without ever emptying the pool when the geolocation lookup fails. These
tests pin exactly that behaviour.
"""
from __future__ import annotations

import json

import pytest

from vless import asn_filter
from vless.parser import VlessNode


def _node(host: str, port: int = 443) -> VlessNode:
    return VlessNode(
        uuid="11111111-2222-3333-4444-555555555555",
        host=host,
        port=port,
        name="test",
    )


@pytest.fixture(autouse=True)
def _isolated_cache(tmp_path, monkeypatch):
    """Point the disk cache at tmp_path so tests never touch .cache/."""
    cache_file = tmp_path / "asn_lookup.json"
    monkeypatch.setattr(asn_filter, "_cache_path", lambda: cache_file)
    yield cache_file


def _fake_lookup(mapping: dict[str, int]):
    """Build a stand-in for ``_lookup_uncached`` from {ip: asn}."""

    def _lookup(ips: list[str]) -> dict[str, dict]:
        import time

        out = {}
        for ip in ips:
            if ip in mapping:
                out[ip] = {
                    "asn": mapping[ip],
                    "asname": f"AS{mapping[ip]}",
                    "country": "RU",
                    "ts": time.time(),
                }
        return out

    return _lookup


def test_drops_blocked_asn(monkeypatch):
    nodes = [_node("93.77.177.164"), _node("85.193.91.193")]
    monkeypatch.setattr(
        asn_filter, "_lookup_uncached", _fake_lookup({"93.77.177.164": 200350, "85.193.91.193": 9123})
    )

    survivors = asn_filter.filter_blocked_asn(nodes)

    assert [n.host for n in survivors] == ["85.193.91.193"]
    assert nodes[0].extra["rejected_reason"] == "asn_blocked=AS200350"
    assert survivors[0].extra["asn"] == 9123


def test_fails_open_when_lookup_returns_nothing(monkeypatch):
    """A dead geolocation API must never empty the pool."""
    nodes = [_node("93.77.177.164"), _node("85.193.91.193")]
    monkeypatch.setattr(asn_filter, "_lookup_uncached", lambda ips: {})

    survivors = asn_filter.filter_blocked_asn(nodes)

    assert len(survivors) == 2
    assert all("rejected_reason" not in n.extra for n in nodes)


def test_hostnames_are_passed_through(monkeypatch):
    """We cannot resolve hostnames cheaply, so they must survive untouched."""
    nodes = [_node("node.example.com"), _node("85.193.91.193")]
    monkeypatch.setattr(asn_filter, "_lookup_uncached", _fake_lookup({"85.193.91.193": 9123}))

    survivors = asn_filter.filter_blocked_asn(nodes)

    assert [n.host for n in survivors] == ["node.example.com", "85.193.91.193"]


def test_unresolved_ip_is_allowed(monkeypatch):
    """An IP the API could not resolve is unknown, not blocked."""
    nodes = [_node("10.0.0.1")]
    monkeypatch.setattr(asn_filter, "_lookup_uncached", lambda ips: {})

    assert len(asn_filter.filter_blocked_asn(nodes)) == 1


def test_empty_input():
    assert asn_filter.filter_blocked_asn([]) == []


def test_cache_avoids_second_lookup(monkeypatch):
    calls: list[list[str]] = []

    def _counting(ips):
        calls.append(list(ips))
        return _fake_lookup({"85.193.91.193": 9123})(ips)

    monkeypatch.setattr(asn_filter, "_lookup_uncached", _counting)

    asn_filter.filter_blocked_asn([_node("85.193.91.193")])
    asn_filter.filter_blocked_asn([_node("85.193.91.193")])

    assert len(calls) == 1, "second call must be served from the disk cache"
    cached = json.loads(asn_filter._cache_path().read_text(encoding="utf-8"))
    assert cached["85.193.91.193"]["asn"] == 9123


def test_resolve_asns_skips_non_ipv4(monkeypatch):
    monkeypatch.setattr(
        asn_filter, "_lookup_uncached", _fake_lookup({"85.193.91.193": 9123})
    )
    resolved = asn_filter.resolve_asns({"85.193.91.193", "example.org"})
    assert set(resolved) == {"85.193.91.193"}


def test_preferred_asn_count_uses_cache(monkeypatch, _isolated_cache):
    monkeypatch.setattr(
        asn_filter, "_lookup_uncached",
        _fake_lookup({"85.193.91.193": 9123, "83.217.201.82": 200350}),
    )
    nodes = [_node("85.193.91.193"), _node("83.217.201.82")]
    asn_filter.resolve_asns({n.host for n in nodes})

    assert asn_filter.preferred_asn_count(nodes) == 1