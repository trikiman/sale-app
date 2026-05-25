"""Hand-curated trojan outbound seeds — always present in xray config.

v1.27 hotfix 2026-05-23: operator supplied 6 known-working RU trojan
endpoints to use as a fallback floor for cycle continuity. They are
appended to every xray config alongside the dynamically-discovered
VLESS pool, so even a fully-empty dynamic pool still has working
outbounds. xray's ``observatory`` + ``leastPing`` balancer treats them
identically to dynamic VLESS nodes — fastest live outbound wins per
connection.

These bypass the normal probe + admit + quarantine pipeline. They
don't count toward ``pool_size`` and don't get persisted in
``vless_pool.json``. They are pure, build-time-baked-in safety net.

If any of these stop working, the balancer rotates to the others or to
dynamic VLESS pool members. To remove a stale seed, delete it from
``MANUAL_TROJAN_SEEDS`` below and redeploy.

All 6 share password / SNI / transport / WS host. Only host/port/path
differ. Source: operator-supplied 2026-05-23 09:39 MSK.
"""
from __future__ import annotations


_SHARED_PASSWORD = "8r<[9'l6hAO#8ZQi"
_SHARED_SNI = "Koma-YT.PAGeS.Dev"

# (host, port, ws_path)
MANUAL_TROJAN_SEEDS: tuple[tuple[str, int, str], ...] = (
    ("93.77.177.164",   443,  "/trTelegram\U0001F1E8\U0001F1F3+@WangCai2"),
    ("150.241.74.98",   8443, "/trTelegram\U0001F1E8\U0001F1F3 @WangCai2"),
    ("212.113.112.236", 8443, "/trTelegram\U0001F1E8\U0001F1F3+@WangCai2"),
    ("85.193.90.131",   2053, "/trTelegram\U0001F1E8\U0001F1F3+@WangCai2"),
    ("85.193.91.193",   8443, "/trTelegram\U0001F1E8\U0001F1F3+@WangCai2"),
    ("91.196.32.171",   8443, "/trTelegram\U0001F1E8\U0001F1F3+@WangCai2"),
)


def build_manual_outbounds(start_idx: int = 0) -> tuple[list[dict], list[str]]:
    """Build xray outbound dicts + their tags for the manual seeds.

    Returns ``(outbounds, tags)``. Tags are ``manual-{idx}`` starting at
    ``start_idx`` so callers can append after dynamic ``node-N`` outbounds.

    The shape mirrors xray-core's trojan outbound spec — see
    https://xtls.github.io/config/outbounds/trojan.html. WebSocket transport
    uses the same SNI as the WS Host header (the operator's deployment
    expects them identical).
    """
    outbounds: list[dict] = []
    tags: list[str] = []
    for offset, (host, port, ws_path) in enumerate(MANUAL_TROJAN_SEEDS):
        tag = f"manual-{start_idx + offset}"
        tags.append(tag)
        outbounds.append({
            "tag": tag,
            "protocol": "trojan",
            "settings": {
                "servers": [{
                    "address": host,
                    "port": port,
                    "password": _SHARED_PASSWORD,
                }],
            },
            "streamSettings": {
                "network": "ws",
                "security": "tls",
                "tlsSettings": {
                    "serverName": _SHARED_SNI,
                    "allowInsecure": False,
                    "fingerprint": "chrome",
                },
                "wsSettings": {
                    "path": ws_path,
                    "headers": {"Host": _SHARED_SNI},
                },
            },
        })
    return outbounds, tags
