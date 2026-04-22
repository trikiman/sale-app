"""Persistence for the VLESS node pool (``data/vless_pool.json``).

Keeps the on-disk pool file small and atomic — we rewrite the whole file on
every refresh rather than appending, so recovery after a crash is just
"load the last good file". Separate module from the manager so tests can
mock or replay pool state without spinning up xray.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Iterable

from vless.parser import VlessNode

POOL_PATH_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "vless_pool.json"

# Fields on PoolEntry that mirror VlessNode; kept explicit so pool entries
# serialise cleanly even if VlessNode gains new internal-only fields.
_NODE_FIELDS = (
    "uuid",
    "host",
    "port",
    "name",
    "reality_pbk",
    "reality_sni",
    "reality_sid",
    "reality_spx",
    "reality_fp",
    "flow",
    "transport",
    "encryption",
    "header_type",
)


def _entry_from_node(node: VlessNode, *, verified_country: str = "RU") -> dict:
    """Convert a :class:`VlessNode` into the on-disk pool entry shape."""
    data = {field: getattr(node, field) for field in _NODE_FIELDS}
    data["verified_country"] = verified_country
    data["verified_at"] = datetime.now().isoformat(timespec="seconds")
    data["last_success_at"] = None
    data["success_count"] = 0
    data["failure_count"] = 0
    data["extra"] = dict(node.extra) if node.extra else {}
    return data


def _node_from_entry(entry: dict) -> VlessNode:
    """Reconstruct a :class:`VlessNode` from a pool entry dict.

    Tolerates missing optional fields so upgrading the schema later (or
    loading a hand-edited pool file) does not crash the manager.
    """
    extra = entry.get("extra") or {}
    kwargs = {field: entry.get(field, "") for field in _NODE_FIELDS}
    port = kwargs.get("port") or 0
    try:
        kwargs["port"] = int(port)
    except (TypeError, ValueError):
        kwargs["port"] = 0
    kwargs.setdefault("transport", "tcp")
    kwargs.setdefault("encryption", "none")
    kwargs.setdefault("header_type", "none")
    kwargs.setdefault("reality_fp", "chrome")
    return VlessNode(extra=extra, **kwargs)


def load(path: Path | None = None) -> dict:
    """Load a pool file, returning an empty shape if none exists yet."""
    real_path = path or POOL_PATH_DEFAULT
    try:
        with real_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return {"updated_at": None, "nodes": []}
    except (OSError, json.JSONDecodeError):
        # Corrupt file on disk — treat as empty pool. We deliberately do NOT
        # raise: refresh will rebuild it from upstream, and the alternative
        # is a crash loop on startup if someone hand-edits the file.
        return {"updated_at": None, "nodes": []}
    if "nodes" not in data:
        data["nodes"] = []
    return data


def save(data: dict, path: Path | None = None) -> None:
    """Atomically write ``data`` to the pool file."""
    real_path = path or POOL_PATH_DEFAULT
    real_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=real_path.name + ".",
        suffix=".tmp",
        dir=str(real_path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
        os.replace(tmp_name, real_path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def replace_nodes(
    data: dict,
    nodes: Iterable[VlessNode],
    *,
    verified_country: str = "RU",
) -> dict:
    """Return a new pool dict with ``nodes`` as the admitted set.

    Preserves ``success_count`` / ``failure_count`` / ``last_success_at`` for
    nodes that reappear (matched by ``host:port``); initialises them for new
    admissions. ``updated_at`` is stamped with the current ISO timestamp.
    """
    previous = {(entry.get("host"), int(entry.get("port", 0))): entry for entry in data.get("nodes", [])}
    fresh_entries: list[dict] = []
    for node in nodes:
        key = (node.host, int(node.port))
        entry = _entry_from_node(node, verified_country=verified_country)
        prior = previous.get(key)
        if prior:
            entry["success_count"] = int(prior.get("success_count", 0) or 0)
            entry["failure_count"] = int(prior.get("failure_count", 0) or 0)
            entry["last_success_at"] = prior.get("last_success_at")
            # Keep the earliest verified_at — we only need a single witness.
            if prior.get("verified_at"):
                entry["verified_at"] = prior["verified_at"]
        fresh_entries.append(entry)
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "nodes": fresh_entries,
    }


def nodes_from(data: dict) -> list[VlessNode]:
    """Return the stored pool entries as :class:`VlessNode` instances."""
    return [_node_from_entry(entry) for entry in data.get("nodes", [])]


def remove_host(data: dict, host: str) -> tuple[dict, int]:
    """Return (new_pool_dict, removed_count) after dropping every entry with ``host``."""
    before = data.get("nodes", [])
    after = [entry for entry in before if entry.get("host") != host]
    new_data = {
        "updated_at": data.get("updated_at"),
        "nodes": after,
    }
    return new_data, len(before) - len(after)


def note_success(data: dict, host: str, port: int | None = None) -> dict:
    """Bump ``success_count`` / ``last_success_at`` for the matching node."""
    for entry in data.get("nodes", []):
        if entry.get("host") != host:
            continue
        if port is not None and int(entry.get("port", 0) or 0) != int(port):
            continue
        entry["success_count"] = int(entry.get("success_count", 0) or 0) + 1
        entry["last_success_at"] = datetime.now().isoformat(timespec="seconds")
    return data


def note_failure(data: dict, host: str, port: int | None = None) -> dict:
    """Bump ``failure_count`` for the matching node."""
    for entry in data.get("nodes", []):
        if entry.get("host") != host:
            continue
        if port is not None and int(entry.get("port", 0) or 0) != int(port):
            continue
        entry["failure_count"] = int(entry.get("failure_count", 0) or 0) + 1
    return data


__all__ = [
    "POOL_PATH_DEFAULT",
    "load",
    "save",
    "replace_nodes",
    "nodes_from",
    "remove_host",
    "note_success",
    "note_failure",
]


# Silence "asdict imported but unused" — it's kept as a deliberate hook for
# callers that want to persist ad-hoc VlessNode instances without round
# tripping through this module.
_ = asdict
