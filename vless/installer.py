"""Install a pinned xray-core release under ``bin/xray/``.

The installer is intentionally stdlib-only (``urllib.request``, ``zipfile``,
``hashlib``) so it can run on a freshly-provisioned machine *before* any
Python wheels are compiled. It downloads the official release archive for the
current OS, verifies its SHA256 against a vetted table, extracts to a
per-version directory, and updates the ``bin/xray/current`` pointer.

No xray process is started here; :mod:`vless.xray` owns lifecycle.
"""
from __future__ import annotations

import hashlib
import os
import platform
import shutil
import stat
import sys
import tempfile
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Literal

# Pin to a specific xray-core release. Do NOT auto-latest — a version bump is
# a deliberate code change that must be paired with a fresh SHA256 table.
XRAY_VERSION = "24.11.30"

# SHA256 of the released .zip archives, generated from the official GitHub
# release assets for v24.11.30. Verified 2026-04-22.
XRAY_SHA256: dict[str, str] = {
    "windows-64": "576e46a4d17ea08ef7c3120ec747581709412083cc0e69d2c3ead72ee001897f",
    "linux-64": "679d6ec1c2ecabd84ad1e2deab6e52789c52f0a387902cc72e135a3bb3949554",
    "macos-64": "bb9d1f1563a173a86aac6136db53261ecd3ee2a0a357968273edbd69d976d938",
}

_RELEASE_BASE = "https://github.com/XTLS/Xray-core/releases/download"

BIN_ROOT = Path(__file__).resolve().parent.parent / "bin" / "xray"

PlatformSlug = Literal["windows-64", "linux-64", "macos-64"]


class InstallError(RuntimeError):
    """Raised when xray installation fails.

    The original cause (network error, checksum mismatch, zipfile error, ...)
    is chained via ``__cause__`` so operators see the full traceback.
    """


def detect_platform() -> PlatformSlug:
    """Return the xray release slug for the current OS.

    We only support the 3 x86_64 variants xray ships. ARM / 32-bit Linux are
    explicitly rejected so bootstrap fails loudly instead of silently
    downloading an incompatible binary.
    """
    system = platform.system().lower()
    machine = platform.machine().lower()
    arch_ok = machine in {"x86_64", "amd64"}
    if not arch_ok:
        raise InstallError(
            f"unsupported architecture {machine!r}; xray bootstrap supports x86_64 only"
        )
    if system == "linux":
        return "linux-64"
    if system == "darwin":
        return "macos-64"
    if system == "windows":
        return "windows-64"
    raise InstallError(f"unsupported OS {system!r}; expected linux/darwin/windows")


def binary_path(version: str = XRAY_VERSION, *, root: Path | None = None) -> Path:
    """Return the expected path of the xray binary for ``version``.

    Does not check whether the binary exists. The ``root`` parameter is a
    hook for tests to redirect installs into a tempdir without touching the
    real ``bin/`` tree.
    """
    bin_root = root if root is not None else BIN_ROOT
    exe = "xray.exe" if platform.system().lower() == "windows" else "xray"
    return bin_root / f"v{version}" / exe


def _current_link(root: Path) -> Path:
    return root / "current"


def is_installed(version: str = XRAY_VERSION, *, root: Path | None = None) -> bool:
    """True if the pinned xray binary is already on disk and executable."""
    path = binary_path(version, root=root)
    if not path.exists():
        return False
    if platform.system().lower() == "windows":
        return path.is_file()
    mode = path.stat().st_mode
    return bool(mode & stat.S_IXUSR)


def _download_with_progress(url: str, dest: Path, *, progress_stream=sys.stderr) -> None:
    """Stream ``url`` into ``dest`` and print rough progress to stderr."""
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "sale-app/xray-installer"},
    )
    try:
        with urllib.request.urlopen(req) as resp, dest.open("wb") as out:
            total = resp.headers.get("Content-Length")
            total_bytes = int(total) if total and total.isdigit() else 0
            downloaded = 0
            next_progress = 1 << 20  # first tick at 1 MiB
            while True:
                chunk = resp.read(1 << 15)
                if not chunk:
                    break
                out.write(chunk)
                downloaded += len(chunk)
                if downloaded >= next_progress:
                    if total_bytes:
                        pct = downloaded * 100 // total_bytes
                        print(
                            f"[xray-install] {downloaded // (1 << 20)} MiB"
                            f" / {total_bytes // (1 << 20)} MiB ({pct}%)",
                            file=progress_stream,
                        )
                    else:
                        print(
                            f"[xray-install] {downloaded // (1 << 20)} MiB",
                            file=progress_stream,
                        )
                    next_progress += 1 << 20
    except urllib.error.URLError as exc:
        raise InstallError(f"download failed: {url!r}") from exc


def _sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _release_url(version: str, slug: PlatformSlug) -> str:
    return f"{_RELEASE_BASE}/v{version}/Xray-{slug}.zip"


def _update_current_symlink(root: Path, version: str) -> None:
    """Point ``bin/xray/current`` at ``v<version>/``.

    Uses a symlink on Unix. On Windows, falls back to a recursive directory
    copy if we cannot create a directory junction — this keeps bootstrap
    working without admin privileges.
    """
    link = _current_link(root)
    target = root / f"v{version}"
    if link.exists() or link.is_symlink():
        if link.is_symlink() or link.is_file():
            link.unlink()
        else:
            shutil.rmtree(link)
    if platform.system().lower() == "windows":
        try:
            os.symlink(target, link, target_is_directory=True)
        except OSError:
            # Admin-free fallback for dev machines with no symlink privilege.
            shutil.copytree(target, link)
    else:
        os.symlink(target.name, link)  # relative symlink keeps trees movable


def install(
    version: str = XRAY_VERSION,
    *,
    force: bool = False,
    root: Path | None = None,
    sha256: dict[str, str] | None = None,
    release_url: str | None = None,
) -> Path:
    """Download, verify, and extract the pinned xray release.

    Returns the absolute path to the installed xray executable. When the
    expected binary already exists and ``force`` is False, this call is a
    fast no-op. Tests pass ``root`` / ``sha256`` / ``release_url`` to stage
    installs in a tempdir without hitting GitHub.
    """
    bin_root = root if root is not None else BIN_ROOT
    sha_table = sha256 if sha256 is not None else XRAY_SHA256

    if not force and is_installed(version, root=bin_root):
        return binary_path(version, root=bin_root)

    slug = detect_platform()
    expected_sha = sha_table.get(slug)
    if not expected_sha:
        raise InstallError(f"no SHA256 pinned for platform {slug!r}")

    url = release_url if release_url is not None else _release_url(version, slug)
    bin_root.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="xray-install-") as staging:
        staging_path = Path(staging)
        archive = staging_path / f"Xray-{slug}.zip"

        _download_with_progress(url, archive)

        actual_sha = _sha256_of(archive)
        if actual_sha.lower() != expected_sha.lower():
            raise InstallError(
                f"checksum mismatch for {slug} v{version}: "
                f"expected {expected_sha}, got {actual_sha}"
            )

        # Extract into a fresh per-version directory so a failure midway
        # leaves the previous install untouched.
        version_dir = bin_root / f"v{version}"
        extract_dir = staging_path / "extract"
        extract_dir.mkdir()
        try:
            with zipfile.ZipFile(archive) as zf:
                zf.extractall(extract_dir)
        except zipfile.BadZipFile as exc:
            raise InstallError("downloaded archive is not a valid zip") from exc

        # Wipe any previous copy of this version so extraction is atomic
        # from the caller's perspective.
        if version_dir.exists():
            shutil.rmtree(version_dir)
        shutil.move(str(extract_dir), str(version_dir))

        if platform.system().lower() != "windows":
            bin_file = version_dir / "xray"
            if bin_file.exists():
                bin_file.chmod(bin_file.stat().st_mode | 0o755)

    _update_current_symlink(bin_root, version)

    return binary_path(version, root=bin_root)


__all__ = [
    "XRAY_VERSION",
    "XRAY_SHA256",
    "BIN_ROOT",
    "InstallError",
    "detect_platform",
    "is_installed",
    "install",
    "binary_path",
]
