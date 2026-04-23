"""Tests for :mod:`vless.parser` — VLESS URL parsing."""
from __future__ import annotations

from pathlib import Path

import pytest

from vless.parser import (
    VlessNode,
    VlessParseError,
    parse_vless_list,
    parse_vless_url,
)

_FIXTURE = Path(__file__).parent / "fixtures" / "vless_sample.txt"


def test_parses_canonical_url_with_all_reality_params():
    url = (
        "vless://aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee@1.2.3.4:443"
        "?encryption=none&flow=xtls-rprx-vision&security=reality"
        "&sni=www.microsoft.com&fp=chrome&pbk=PUBKEY&sid=abcd&spx=%2F"
        "&type=tcp&headerType=none#%F0%9F%87%B7%F0%9F%87%BA%20Moscow"
    )
    node = parse_vless_url(url)

    assert isinstance(node, VlessNode)
    assert node.uuid == "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert node.host == "1.2.3.4"
    assert node.port == 443
    assert node.reality_pbk == "PUBKEY"
    assert node.reality_sni == "www.microsoft.com"
    assert node.reality_sid == "abcd"
    assert node.reality_spx == "/"
    assert node.reality_fp == "chrome"
    assert node.flow == "xtls-rprx-vision"
    assert node.transport == "tcp"
    assert node.encryption == "none"
    assert node.header_type == "none"
    assert "Moscow" in node.name
    assert node.extra == {}
    assert node.address == "1.2.3.4:443"


def test_missing_optional_params_default_correctly():
    url = (
        "vless://11111111-2222-3333-4444-555555555555@10.0.0.1:8443"
        "?security=reality&sni=example.com&pbk=PK1"
    )
    node = parse_vless_url(url)
    assert node.reality_sid == ""
    assert node.reality_spx == ""
    assert node.flow == ""
    assert node.reality_fp == "chrome"  # defaulted
    assert node.transport == "tcp"  # defaulted
    assert node.encryption == "none"  # defaulted


def test_url_encoded_fragment_is_decoded():
    url = (
        "vless://aaaaaaaa-0000-0000-0000-000000000000@1.2.3.4:443"
        "?security=reality&sni=s.example.com&pbk=P"
        "#%F0%9F%87%B7%F0%9F%87%BA%20RU%20Server"
    )
    node = parse_vless_url(url)
    # Fragment starts with a flag emoji pair; decoding must have occurred
    # (we compare against the decoded ASCII tail rather than the raw bytes).
    assert node.name.endswith("RU Server")
    assert "%20" not in node.name


def test_fragment_fallback_when_empty_uses_host_port():
    url = "vless://abcd-ef@1.2.3.4:443?security=reality&sni=x&pbk=P"
    node = parse_vless_url(url)
    assert node.name == "1.2.3.4:443"


def test_unknown_query_params_are_preserved_in_extra():
    url = (
        "vless://abcd-ef@1.2.3.4:443"
        "?security=reality&sni=s&pbk=P&customFlag=hello&anotherOne=value2"
    )
    node = parse_vless_url(url)
    assert node.extra == {"customFlag": "hello", "anotherOne": "value2"}


def test_rejects_non_vless_scheme():
    with pytest.raises(VlessParseError, match="scheme"):
        parse_vless_url("https://example.com/")


def test_rejects_missing_uuid():
    with pytest.raises(VlessParseError, match="uuid"):
        parse_vless_url("vless://@1.2.3.4:443?security=reality&pbk=P&sni=s")


def test_rejects_missing_host():
    with pytest.raises(VlessParseError):
        parse_vless_url("vless://uuid@:443?security=reality&pbk=P&sni=s")


def test_rejects_missing_port():
    with pytest.raises(VlessParseError, match="port"):
        parse_vless_url("vless://uuid@example.com?security=reality&pbk=P&sni=s")


def test_accepts_security_tls():
    """VLESS+TLS+xtls-rprx-vision nodes (igareck white-lists) must parse."""
    url = (
        "vless://75807638-6f19-07d0-ae08-38492ee85c88@178.72.181.28:52006"
        "?encryption=none&flow=xtls-rprx-vision&security=tls&fp=chrome"
        "&insecure=1&allowInsecure=1&type=tcp&headerType=none"
        "#%F0%9F%87%B7%F0%9F%87%BA%20Russia%20%5B%2ACIDR%5D"
    )
    node = parse_vless_url(url)
    assert node.security == "tls"
    assert node.flow == "xtls-rprx-vision"
    assert node.host == "178.72.181.28"
    assert node.port == 52006
    assert node.tls_allow_insecure is True
    # Reality-specific fields stay empty for TLS nodes.
    assert node.reality_pbk == ""
    assert node.reality_sni == ""
    assert "Russia" in node.name


def test_accepts_security_tls_with_sni():
    url = (
        "vless://uuid@5.178.87.140:52006?encryption=none&flow=xtls-rprx-vision"
        "&security=tls&sni=cluster-russia-1.firstvideocdn.ru&fp=chrome"
        "&insecure=0&type=tcp#RU"
    )
    node = parse_vless_url(url)
    assert node.security == "tls"
    assert node.tls_sni == "cluster-russia-1.firstvideocdn.ru"
    assert node.tls_allow_insecure is False


def test_rejects_unknown_security():
    with pytest.raises(VlessParseError, match="security"):
        parse_vless_url(
            "vless://uuid@1.2.3.4:443?security=weirdproto&pbk=P&sni=s"
        )


def test_rejects_missing_public_key_when_reality():
    with pytest.raises(VlessParseError, match="public key"):
        parse_vless_url("vless://uuid@1.2.3.4:443?security=reality&sni=s")


def test_tls_does_not_require_public_key():
    """TLS mode has no pbk — parser must not complain."""
    node = parse_vless_url(
        "vless://uuid@1.2.3.4:443?security=tls&type=tcp#RU"
    )
    assert node.security == "tls"


def test_parse_vless_list_skips_blanks_and_comments():
    text = "\n\n# top comment\n  # indented comment\n\n"
    nodes, errors = parse_vless_list(text)
    assert nodes == []
    assert errors == []


def test_parse_vless_list_tolerates_mixed_good_and_bad_lines():
    text = (
        "vless://a@1.2.3.4:443?security=reality&pbk=P1&sni=s#ok1\n"
        "not-a-url-at-all\n"
        "vless://b@5.6.7.8:443?security=reality&pbk=P2&sni=s#ok2\n"
        "vless://@9.9.9.9:443?security=reality&pbk=P3&sni=s\n"  # missing uuid
    )
    nodes, errors = parse_vless_list(text)
    assert len(nodes) == 2
    assert nodes[0].uuid == "a"
    assert nodes[1].uuid == "b"
    assert len(errors) == 2
    # Errors should carry the 1-indexed line number we saw in the source.
    reported_lines = sorted(err[0] for err in errors)
    assert reported_lines == [2, 4]


def test_parse_vless_list_handles_none_text():
    nodes, errors = parse_vless_list(None)  # type: ignore[arg-type]
    assert nodes == []
    assert errors == []


def test_fixture_parses_with_expected_counts():
    text = _FIXTURE.read_text(encoding="utf-8")
    nodes, errors = parse_vless_list(text)
    # The fixture contains 9 valid VLESS URLs and 2 malformed lines.
    assert len(nodes) == 9
    assert len(errors) == 2
    # The unknown_param=preserveme URL must round-trip into extra.
    preserved = [n for n in nodes if n.extra.get("unknown_param") == "preserveme"]
    assert len(preserved) == 1
