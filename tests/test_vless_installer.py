"""Unit tests for :mod:`vless.installer`.

All tests stage into a ``tmp_path`` root (never touching the real ``bin/``)
and use a file:// URL against a fabricated zip so we never hit GitHub.
"""
from __future__ import annotations

import hashlib
import platform
import stat
import zipfile
from pathlib import Path

import pytest

from vless import installer


def _build_fake_release_zip(dest: Path, *, exe_content: bytes = b"#!/bin/sh\nexit 0\n") -> str:
    """Create a minimal xray-shaped zip and return its SHA256 digest.

    The archive mimics the real release layout (xray + geoip.dat +
    geosite.dat) so the installer's extraction path is exercised end-to-end.
    """
    exe_name = "xray.exe" if platform.system().lower() == "windows" else "xray"
    with zipfile.ZipFile(dest, "w") as zf:
        zf.writestr(exe_name, exe_content)
        zf.writestr("geoip.dat", b"stub")
        zf.writestr("geosite.dat", b"stub")
        zf.writestr("README.md", b"stub release")
    return hashlib.sha256(dest.read_bytes()).hexdigest()


@pytest.fixture
def isolated_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect ``installer.BIN_ROOT`` into ``tmp_path/bin/xray`` for one test."""
    root = tmp_path / "bin" / "xray"
    monkeypatch.setattr(installer, "BIN_ROOT", root)
    return root


def test_detect_platform_returns_known_slug() -> None:
    slug = installer.detect_platform()
    assert slug in {"linux-64", "macos-64", "windows-64"}


def test_install_happy_path_extracts_and_sets_current(
    isolated_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    archive_path = tmp_path / "Xray-fake.zip"
    sha = _build_fake_release_zip(archive_path)
    slug = installer.detect_platform()
    sha_table = {slug: sha}

    installed = installer.install(
        version="test-1.0",
        root=isolated_root,
        sha256=sha_table,
        release_url=archive_path.resolve().as_uri(),
    )

    assert installed.exists()
    assert installed == installer.binary_path("test-1.0", root=isolated_root)
    assert (isolated_root / "current").exists(), "current/ pointer must be set"
    version_dir = isolated_root / "vtest-1.0"
    assert version_dir.exists(), "version directory must be created"
    assert (version_dir / "geoip.dat").exists()
    assert (version_dir / "geosite.dat").exists()

    if platform.system().lower() != "windows":
        mode = installed.stat().st_mode
        assert mode & stat.S_IXUSR, "xray binary must be executable after install"


def test_install_is_idempotent_when_already_present(
    isolated_root: Path, tmp_path: Path
) -> None:
    archive = tmp_path / "Xray-fake.zip"
    sha = _build_fake_release_zip(archive)
    slug = installer.detect_platform()
    sha_table = {slug: sha}

    installer.install(
        version="idem-1",
        root=isolated_root,
        sha256=sha_table,
        release_url=archive.resolve().as_uri(),
    )

    # Second call must short-circuit without a fresh download: point the URL
    # at /dev/null — install must NOT try to fetch it.
    installer.install(
        version="idem-1",
        root=isolated_root,
        sha256=sha_table,
        release_url="file:///nonexistent-path-that-would-fail.zip",
    )
    assert installer.is_installed("idem-1", root=isolated_root)


def test_install_force_reinstalls_even_if_present(
    isolated_root: Path, tmp_path: Path
) -> None:
    archive = tmp_path / "Xray-fake.zip"
    sha = _build_fake_release_zip(archive)
    slug = installer.detect_platform()
    sha_table = {slug: sha}

    installer.install(
        version="force-1",
        root=isolated_root,
        sha256=sha_table,
        release_url=archive.resolve().as_uri(),
    )

    # With force=True + a new release with a fresh SHA, installer should
    # re-extract. Build a second archive with different content (and sha).
    archive2 = tmp_path / "Xray-fake-2.zip"
    sha2 = _build_fake_release_zip(archive2, exe_content=b"#!/bin/sh\nexit 1\n")
    sha_table2 = {slug: sha2}
    installer.install(
        version="force-1",
        root=isolated_root,
        force=True,
        sha256=sha_table2,
        release_url=archive2.resolve().as_uri(),
    )
    assert installer.is_installed("force-1", root=isolated_root)


def test_install_rejects_checksum_mismatch(
    isolated_root: Path, tmp_path: Path
) -> None:
    archive = tmp_path / "Xray-fake.zip"
    _build_fake_release_zip(archive)
    slug = installer.detect_platform()
    wrong_table = {slug: "0" * 64}

    with pytest.raises(installer.InstallError) as excinfo:
        installer.install(
            version="bad-sha",
            root=isolated_root,
            sha256=wrong_table,
            release_url=archive.resolve().as_uri(),
        )
    assert "checksum mismatch" in str(excinfo.value)
    # Partial install must not have created the version dir.
    assert not (isolated_root / "vbad-sha").exists()


def test_install_rejects_bad_archive(
    isolated_root: Path, tmp_path: Path
) -> None:
    archive = tmp_path / "not-a-zip.zip"
    archive.write_bytes(b"definitely not a zipfile")
    sha = hashlib.sha256(archive.read_bytes()).hexdigest()
    slug = installer.detect_platform()

    with pytest.raises(installer.InstallError) as excinfo:
        installer.install(
            version="bad-zip",
            root=isolated_root,
            sha256={slug: sha},
            release_url=archive.resolve().as_uri(),
        )
    assert "zip" in str(excinfo.value).lower()


def test_install_without_sha_for_platform_raises(
    isolated_root: Path, tmp_path: Path
) -> None:
    archive = tmp_path / "Xray-fake.zip"
    _build_fake_release_zip(archive)

    with pytest.raises(installer.InstallError) as excinfo:
        installer.install(
            version="no-sha",
            root=isolated_root,
            sha256={},  # empty — no entry for any platform
            release_url=archive.resolve().as_uri(),
        )
    assert "SHA256" in str(excinfo.value)


def test_binary_path_uses_os_specific_extension(isolated_root: Path) -> None:
    path = installer.binary_path("9.9.9", root=isolated_root)
    if platform.system().lower() == "windows":
        assert path.name == "xray.exe"
    else:
        assert path.name == "xray"
    assert path.parent.name == "v9.9.9"


def test_is_installed_false_when_binary_missing(isolated_root: Path) -> None:
    assert not installer.is_installed("missing-1", root=isolated_root)


def test_xray_sha256_table_covers_all_supported_platforms() -> None:
    # Keeps the pinned table honest. If an OS loses its entry, a later
    # install() on that OS would raise a less-helpful error.
    assert set(installer.XRAY_SHA256) == {"windows-64", "linux-64", "macos-64"}
    for slug, digest in installer.XRAY_SHA256.items():
        assert len(digest) == 64, f"{slug} has non-sha256 length"
        int(digest, 16)  # all hex digits


def test_sha256_table_is_lowercase_hex() -> None:
    for digest in installer.XRAY_SHA256.values():
        assert digest == digest.lower()
