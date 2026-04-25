"""Build an xray-core configuration dict from a list of :class:`VlessNode`.

The generator is pure-Python and produces a JSON-serializable ``dict`` that
xray can consume via ``xray -config <path>``. No filesystem writes happen here
— persisting the config is the caller's responsibility.

The shape follows xray-core v24.x:

* One SOCKS5 inbound on ``127.0.0.1:10808`` (loopback, no auth, UDP enabled)
* One VLESS+Reality outbound per node, tagged ``node-<idx>``
* A ``balancer`` named ``ru-balancer`` referencing every node tag with
  strategy ``leastPing``, fed by an ``observatory`` block that probes every
  outbound matching ``node-*`` against ``generate_204`` every 5 minutes
* An explicit ``policy.levels["0"]`` block (handshake=8, connIdle=30) so a
  stalled VLESS upstream surfaces as a fast failure rather than xray's
  default 300s connection-idle hang
* A single routing rule that directs all traffic to the balancer
* ``log.loglevel = "warning"`` — the production default

We also include a ``"freedom"`` fallback outbound tagged ``direct`` so xray has
a legal place to drop unmatched traffic (none should exist, but xray refuses
to route to an undefined tag).
"""
from __future__ import annotations

from vless.parser import VlessNode

XRAY_LISTEN_HOST = "127.0.0.1"
XRAY_LISTEN_PORT = 10808
_BALANCER_TAG = "ru-balancer"


def _build_outbound(node: VlessNode, tag: str) -> dict:
    """Translate a :class:`VlessNode` into an xray VLESS outbound dict.

    Two security modes are supported:

    * ``security == "reality"`` — the igareck "black" / Reality-masked lists.
      Produces a ``realitySettings`` block with pbk/sni/sid/spx.
    * ``security == "tls"`` — plain VLESS+TLS+xtls-rprx-vision (the "white
      list" CIDR/SNI entries that actually egress on RU residential ranges).
      Produces a ``tlsSettings`` block with serverName + allowInsecure.
    """
    user: dict[str, object] = {"id": node.uuid, "encryption": node.encryption}
    if node.flow:
        user["flow"] = node.flow

    stream_settings: dict[str, object] = {
        "network": node.transport or "tcp",
    }
    if node.header_type and node.header_type != "none" and (node.transport or "tcp") == "tcp":
        stream_settings["tcpSettings"] = {
            "header": {"type": node.header_type},
        }

    if node.security == "tls":
        stream_settings["security"] = "tls"
        tls_settings: dict[str, object] = {
            "allowInsecure": bool(node.tls_allow_insecure),
            "fingerprint": node.reality_fp or "chrome",
        }
        # serverName defaults to the node host when no SNI was provided —
        # this matches what xray infers automatically but being explicit
        # keeps the generated config self-documenting.
        tls_settings["serverName"] = node.tls_sni or node.host
        stream_settings["tlsSettings"] = tls_settings
    else:
        stream_settings["security"] = "reality"
        reality_settings: dict[str, object] = {
            "show": False,
            "fingerprint": node.reality_fp or "chrome",
            "serverName": node.reality_sni,
            "publicKey": node.reality_pbk,
            "shortId": node.reality_sid,
        }
        if node.reality_spx:
            reality_settings["spiderX"] = node.reality_spx
        stream_settings["realitySettings"] = reality_settings

    return {
        "tag": tag,
        "protocol": "vless",
        "settings": {
            "vnext": [
                {
                    "address": node.host,
                    "port": node.port,
                    "users": [user],
                }
            ]
        },
        "streamSettings": stream_settings,
    }


def build_xray_config(
    nodes: list[VlessNode],
    *,
    listen_host: str = XRAY_LISTEN_HOST,
    listen_port: int = XRAY_LISTEN_PORT,
    log_level: str = "warning",
) -> dict:
    """Build a full xray-core config dict from a list of VLESS nodes.

    Raises ``ValueError`` if ``nodes`` is empty — xray cannot start without at
    least one outbound, so callers must surface pool exhaustion loudly rather
    than producing an unusable config.
    """
    if not nodes:
        raise ValueError("build_xray_config requires at least one VlessNode")

    outbounds: list[dict] = []
    node_tags: list[str] = []
    for idx, node in enumerate(nodes):
        tag = f"node-{idx}"
        node_tags.append(tag)
        outbounds.append(_build_outbound(node, tag))

    outbounds.append({"tag": "direct", "protocol": "freedom"})
    outbounds.append({"tag": "block", "protocol": "blackhole"})

    return {
        "log": {"loglevel": log_level},
        "inbounds": [
            {
                "tag": "socks-in",
                "listen": listen_host,
                "port": int(listen_port),
                "protocol": "socks",
                "settings": {"auth": "noauth", "udp": True},
                "sniffing": {"enabled": True, "destOverride": ["http", "tls"]},
            }
        ],
        "policy": {
            "levels": {
                "0": {
                    "handshake": 8,
                    "connIdle": 30,
                    "uplinkOnly": 5,
                    "downlinkOnly": 10,
                    "bufferSize": 4096,
                    "statsUserUplink": False,
                    "statsUserDownlink": False,
                },
            },
            "system": {
                "statsInboundUplink": False,
                "statsInboundDownlink": False,
            },
        },
        "outbounds": outbounds,
        "observatory": {
            "subjectSelector": ["node-"],
            "probeURL": "https://www.google.com/generate_204",
            "probeInterval": "5m",
        },
        "routing": {
            "domainStrategy": "AsIs",
            "balancers": [
                {
                    "tag": _BALANCER_TAG,
                    "selector": list(node_tags),
                    "strategy": {"type": "leastPing"},
                }
            ],
            "rules": [
                {
                    "type": "field",
                    "inboundTag": ["socks-in"],
                    "balancerTag": _BALANCER_TAG,
                }
            ],
        },
    }
