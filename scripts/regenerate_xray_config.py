"""One-off: rewrite xray active.json with current pool + manual seeds.

Run on EC2 after a code change to vless/config_gen.py or
vless/manual_seeds.py to push the new config without waiting for the
next pool refresh cycle. After running, restart saleapp-xray so it
loads the new config:

    sudo python3 scripts/regenerate_xray_config.py
    sudo systemctl restart saleapp-xray
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from vless import pool_state
from vless.config_gen import build_xray_config
from vless.parser import VlessNode

XRAY_CONFIG_PATH = _REPO_ROOT / "bin" / "xray" / "configs" / "active.json"
POOL_PATH = _REPO_ROOT / "data" / "vless_pool.json"


def _entry_to_node(entry: dict) -> VlessNode:
    """Reconstruct a VlessNode from its on-disk pool entry shape."""
    return VlessNode(
        uuid=entry.get("uuid", ""),
        host=entry.get("host", ""),
        port=int(entry.get("port", 443)),
        name=entry.get("name", ""),
        reality_pbk=entry.get("reality_pbk", ""),
        reality_sni=entry.get("reality_sni", ""),
        reality_sid=entry.get("reality_sid", ""),
        reality_spx=entry.get("reality_spx", ""),
        reality_fp=entry.get("reality_fp", "chrome"),
        flow=entry.get("flow", ""),
        transport=entry.get("transport", "tcp"),
        encryption=entry.get("encryption", "none"),
        header_type=entry.get("header_type", "none"),
        security=entry.get("security", "reality"),
        tls_sni=entry.get("tls_sni", ""),
        tls_allow_insecure=bool(entry.get("tls_allow_insecure", False)),
        extra=entry.get("extra") or {},
    )


def main() -> None:
    pool = pool_state.load(POOL_PATH)
    nodes_raw = pool.get("nodes", []) if isinstance(pool, dict) else []
    nodes = [_entry_to_node(e) for e in nodes_raw if e.get("host")]
    print(f"Reconstructed {len(nodes)} VLESS nodes from {POOL_PATH}")

    cfg = build_xray_config(nodes)
    outs = cfg["outbounds"]
    manual = sum(1 for o in outs if o["tag"].startswith("manual-"))
    dynamic = sum(1 for o in outs if o["tag"].startswith("node-"))
    print(f"Generated config: {dynamic} dynamic + {manual} manual + {len(outs) - dynamic - manual} system outbounds")
    print(f"Selector tags: {cfg['routing']['balancers'][0]['selector']}")

    XRAY_CONFIG_PATH.write_text(
        json.dumps(cfg, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"Wrote {XRAY_CONFIG_PATH}")
    print("Now run: sudo systemctl restart saleapp-xray")


if __name__ == "__main__":
    main()
