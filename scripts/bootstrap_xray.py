#!/usr/bin/env python3
"""One-shot CLI to install xray-core and optionally smoke-test the pool.

Usage::

    python scripts/bootstrap_xray.py                  # install pinned version
    python scripts/bootstrap_xray.py --force          # reinstall even if present
    python scripts/bootstrap_xray.py --version 1.8.24 # install a specific version
    python scripts/bootstrap_xray.py --smoke-test     # also prove RU egress

Exit code 0 on success, non-zero on failure (useful in systemd preStart units
and in CI bootstrap jobs).
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from vless import installer  # noqa: E402
from vless.config_gen import build_xray_config  # noqa: E402
from vless.xray import XrayProcess, XrayStartupError  # noqa: E402


def _run_version_check(binary: Path) -> str:
    """Return ``xray -version`` stdout or a short error message."""
    try:
        proc = subprocess.run(  # noqa: S603 — fully-controlled args
            [str(binary), "-version"],
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"<failed to run xray -version: {exc}>"
    if proc.returncode != 0:
        return f"<xray -version exited {proc.returncode}: {proc.stderr.strip()}>"
    return proc.stdout.strip() or proc.stderr.strip()


def _smoke_test(binary: Path, *, smoke_dir: Path) -> tuple[bool, str]:
    """Fetch → parse → geo-filter → build config → start xray → verify egress.

    Returns ``(ok, message)``. ``smoke_dir`` holds the generated config and
    the xray log so the caller can inspect them after the run.
    """
    from vless import sources  # local import to keep module import cheap

    smoke_dir.mkdir(parents=True, exist_ok=True)

    text = sources.fetch_igareck_list()
    nodes, errors = sources.parse_vless_list(text)
    ru_nodes, _rejected = sources.filter_ru_nodes(nodes)
    if len(ru_nodes) < 1:
        return False, f"no RU nodes found (parsed={len(nodes)} errors={len(errors)})"

    # Keep the pool small to shorten startup: xray validates every outbound.
    pool = ru_nodes[:5]
    config = build_xray_config(pool)
    config_path = smoke_dir / "smoke.json"
    config_path.write_text(json.dumps(config, indent=2, ensure_ascii=False), encoding="utf-8")

    log_path = smoke_dir / "xray.log"
    process = XrayProcess(
        binary=binary,
        config_path=config_path,
        log_path=log_path,
    )
    try:
        process.start()
    except XrayStartupError as exc:
        return False, f"xray startup failed: {exc} (log: {log_path})"

    try:
        ok, detail = process.verify_egress(expected_country="RU", timeout=20.0)
    finally:
        process.stop()

    if ok:
        return True, f"egress OK — detected country={detail} via {len(pool)} nodes"
    return False, f"egress failed — detected={detail} (log: {log_path})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Install and verify xray-core")
    parser.add_argument(
        "--version",
        default=installer.XRAY_VERSION,
        help=f"xray version to install (default: {installer.XRAY_VERSION})",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="reinstall even if the binary is already present",
    )
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="after install, start xray with a live RU pool and verify egress",
    )
    args = parser.parse_args(argv)

    slug = installer.detect_platform()
    print(f"[bootstrap] platform={slug}, target version={args.version}")

    try:
        binary = installer.install(args.version, force=args.force)
    except installer.InstallError as exc:
        print(f"[bootstrap] install failed: {exc}", file=sys.stderr)
        return 1

    print(f"[bootstrap] installed at {binary}")
    print(f"[bootstrap] {_run_version_check(binary)}")

    if args.smoke_test:
        smoke_dir = installer.BIN_ROOT / "configs"
        ok, detail = _smoke_test(binary, smoke_dir=smoke_dir)
        status = "PASS" if ok else "FAIL"
        print(f"[bootstrap] smoke-test {status}: {detail}")
        return 0 if ok else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
