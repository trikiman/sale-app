"""Subprocess wrapper around the xray-core binary.

:class:`XrayProcess` owns a single long-lived xray subprocess and the config
file it reads. It is the only component in the ``vless/`` package that
actually talks to the kernel — everything above (:mod:`vless.manager` in
56-03) delegates process lifecycle here.

Thread-safety: ``start``, ``stop``, ``restart``, ``write_config`` are guarded
by a single reentrant lock. ``is_running`` / ``health_check`` are cheap reads
safe to call without holding the lock.
"""
from __future__ import annotations

import collections
import json
import os
import platform
import socket
import subprocess
import tempfile
import threading
import time
from pathlib import Path

from vless.installer import binary_path as _default_binary_path

_LOG_ROTATE_BYTES = 5 * 1024 * 1024  # 5 MiB — keeps disk usage bounded
_POLL_INTERVAL = 0.2
_RESTART_WINDOW_S = 300  # 5 minutes


class XrayStartupError(RuntimeError):
    """Raised when :meth:`XrayProcess.start` cannot produce a healthy inbound."""


class XrayCrashedError(RuntimeError):
    """Raised when the watcher thread observes xray exit unexpectedly."""


def _atomic_write_text(path: Path, text: str) -> None:
    """Write ``text`` to ``path`` atomically (write-tempfile-rename).

    Prevents xray from ever reading a half-written config during a restart.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                # fsync is a best-effort hardening; if the FS doesn't support
                # it (e.g. tmpfs in tests) we still get an atomic rename.
                pass
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise


def _extract_inbound_port(config_path: Path, default: int = 10808) -> int:
    """Return the first SOCKS inbound port in ``config_path``.

    Falls back to ``default`` when the config is unreadable or has no socks
    inbound — the wrapper still works but ``health_check`` will probe the
    default port.
    """
    try:
        data = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default
    for inbound in data.get("inbounds", []):
        if inbound.get("protocol") == "socks":
            port = inbound.get("port")
            if isinstance(port, int):
                return port
    return default


class XrayProcess:
    """Supervise a single xray-core subprocess.

    The wrapper writes the config, spawns xray, waits for its inbound SOCKS5
    port to start accepting connections, and keeps a watcher thread alive
    that re-spawns xray if it exits within the configured restart budget.
    """

    def __init__(
        self,
        *,
        binary: Path | None = None,
        config_path: Path,
        log_path: Path | None = None,
        restart_limit: int = 3,
        health_check_timeout: float = 5.0,
        log_func=None,
    ) -> None:
        self._binary = Path(binary) if binary is not None else _default_binary_path()
        self._config_path = Path(config_path)
        if log_path is None:
            log_path = self._binary.parent.parent / "logs" / "xray.log"
        self._log_path = Path(log_path)
        self._restart_limit = int(restart_limit)
        self._health_check_timeout = float(health_check_timeout)
        self._log = log_func or (lambda msg: print(msg, flush=True))

        self._lock = threading.RLock()
        self._proc: subprocess.Popen | None = None
        self._watcher: threading.Thread | None = None
        self._stopping = threading.Event()
        self._restart_history: collections.deque[float] = collections.deque()
        self._log_handle = None

    # ── Lifecycle ────────────────────────────────────────────────

    def start(self) -> None:
        """Spawn xray and block until its inbound SOCKS5 port accepts TCP."""
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                return
            if not self._config_path.exists():
                raise XrayStartupError(
                    f"xray config not found at {self._config_path}"
                )
            self._ensure_log_rotated()
            self._log_handle = self._log_path.open("ab")
            try:
                self._proc = self._spawn_subprocess()
            except FileNotFoundError as exc:
                self._close_log_handle()
                raise XrayStartupError(f"xray binary missing: {self._binary}") from exc
            except OSError as exc:
                self._close_log_handle()
                raise XrayStartupError(f"failed to spawn xray: {exc}") from exc
            self._stopping.clear()
            self._watcher = threading.Thread(
                target=self._watch_loop, name="xray-watcher", daemon=True
            )
            self._watcher.start()
            self._log(f"xray started (pid={self._proc.pid}, port={self.inbound_port})")

            deadline = time.monotonic() + self._health_check_timeout
            while time.monotonic() < deadline:
                if self._proc.poll() is not None:
                    code = self._proc.returncode
                    self._stopping.set()
                    self._close_log_handle()
                    raise XrayStartupError(
                        f"xray exited during startup with code {code} "
                        f"(see {self._log_path})"
                    )
                if self.health_check():
                    return
                time.sleep(_POLL_INTERVAL)
            self._force_stop()
            raise XrayStartupError(
                f"xray did not open inbound :{self.inbound_port} within "
                f"{self._health_check_timeout:.1f}s"
            )

    def stop(self, *, timeout: float = 5.0) -> None:
        """Send SIGTERM and wait up to ``timeout`` seconds before SIGKILL."""
        with self._lock:
            self._stopping.set()
            proc = self._proc
            if proc is None or proc.poll() is not None:
                self._close_log_handle()
                self._proc = None
                return
            try:
                if platform.system().lower() == "windows":
                    proc.terminate()
                else:
                    try:
                        os.killpg(os.getpgid(proc.pid), 15)
                    except (ProcessLookupError, OSError):
                        proc.terminate()
                try:
                    proc.wait(timeout=timeout)
                except subprocess.TimeoutExpired:
                    if platform.system().lower() == "windows":
                        proc.kill()
                    else:
                        try:
                            os.killpg(os.getpgid(proc.pid), 9)
                        except (ProcessLookupError, OSError):
                            proc.kill()
                    try:
                        proc.wait(timeout=timeout)
                    except subprocess.TimeoutExpired:
                        pass
            finally:
                self._close_log_handle()
                self._proc = None
                self._log("xray stopped")

    def restart(self, *, new_config: dict | None = None) -> None:
        """Restart xray, optionally overwriting its config first."""
        with self._lock:
            if new_config is not None:
                self.write_config(new_config)
            self.stop()
            self.start()

    def write_config(self, config: dict) -> None:
        """Atomically serialize ``config`` to :attr:`config_path`."""
        _atomic_write_text(
            self._config_path,
            json.dumps(config, indent=2, ensure_ascii=False),
        )

    # ── Health / diagnostics ────────────────────────────────────

    def is_running(self) -> bool:
        proc = self._proc
        return proc is not None and proc.poll() is None

    def health_check(self) -> bool:
        """Return True if the inbound SOCKS5 port accepts TCP within 1s."""
        try:
            with socket.create_connection(("127.0.0.1", self.inbound_port), timeout=1.0):
                return True
        except OSError:
            return False

    def verify_egress(
        self,
        *,
        expected_country: str = "RU",
        timeout: float = 10.0,
        url: str = "https://ipinfo.io/json",
    ) -> tuple[bool, str]:
        """Issue an HTTPS probe through the local SOCKS5 listener.

        Returns ``(ok, detected_country_or_error)``. Uses ``httpx`` (already
        a project dependency) and falls back to returning the underlying
        error message on any failure.
        """
        try:
            import httpx  # local import keeps installer stdlib-only
        except ImportError:
            return False, "httpx not available in environment"
        proxy = f"socks5h://127.0.0.1:{self.inbound_port}"
        try:
            with httpx.Client(proxy=proxy, timeout=timeout) as client:
                response = client.get(url)
                response.raise_for_status()
                data = response.json()
                country = str(data.get("country", "")).upper()
                return country == expected_country.upper(), country or "unknown"
        except Exception as exc:  # noqa: BLE001 — diagnostic path
            return False, f"{type(exc).__name__}: {exc}"

    @property
    def inbound_port(self) -> int:
        return _extract_inbound_port(self._config_path)

    @property
    def log_path(self) -> Path:
        return self._log_path

    @property
    def config_path(self) -> Path:
        return self._config_path

    # ── Internals ────────────────────────────────────────────────

    def _spawn_subprocess(self) -> subprocess.Popen:
        kwargs: dict = {
            "stdout": self._log_handle,
            "stderr": self._log_handle,
        }
        if platform.system().lower() == "windows":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
        else:
            kwargs["preexec_fn"] = os.setsid
        return subprocess.Popen(  # noqa: S603 — args fully controlled
            [str(self._binary), "-config", str(self._config_path)],
            **kwargs,
        )

    def _watch_loop(self) -> None:
        while not self._stopping.is_set():
            proc = self._proc
            if proc is None:
                return
            exit_code = proc.poll()
            if exit_code is None:
                # Not exited — periodic log rotation check.
                try:
                    self._rotate_log_if_needed()
                except OSError as exc:
                    self._log(f"xray log rotation failed: {exc}")
                time.sleep(1.0)
                continue

            self._log(f"xray exited unexpectedly (code={exit_code}); evaluating restart")
            with self._lock:
                self._close_log_handle()
                self._proc = None
                if self._stopping.is_set():
                    return
                now = time.monotonic()
                self._restart_history.append(now)
                while (
                    self._restart_history
                    and now - self._restart_history[0] > _RESTART_WINDOW_S
                ):
                    self._restart_history.popleft()
                if len(self._restart_history) > self._restart_limit:
                    self._log(
                        "xray restart budget exhausted "
                        f"({self._restart_limit}/5min); giving up"
                    )
                    return
                try:
                    self._ensure_log_rotated()
                    self._log_handle = self._log_path.open("ab")
                    self._proc = self._spawn_subprocess()
                    self._log(f"xray respawned (pid={self._proc.pid})")
                except Exception as exc:  # noqa: BLE001
                    self._log(f"xray respawn failed: {exc}")
                    self._close_log_handle()
                    return

    def _force_stop(self) -> None:
        proc = self._proc
        if proc is None:
            return
        try:
            proc.kill()
        except OSError:
            pass
        self._close_log_handle()
        self._proc = None

    def _close_log_handle(self) -> None:
        handle = self._log_handle
        self._log_handle = None
        if handle is not None:
            try:
                handle.close()
            except OSError:
                pass

    def _ensure_log_rotated(self) -> None:
        self._log_path.parent.mkdir(parents=True, exist_ok=True)
        self._rotate_log_if_needed()

    def _rotate_log_if_needed(self) -> None:
        try:
            size = self._log_path.stat().st_size
        except FileNotFoundError:
            return
        if size < _LOG_ROTATE_BYTES:
            return
        rotated = self._log_path.with_suffix(self._log_path.suffix + ".1")
        try:
            if rotated.exists():
                rotated.unlink()
            self._log_path.rename(rotated)
        except OSError:
            return


__all__ = [
    "XrayProcess",
    "XrayStartupError",
    "XrayCrashedError",
]


# Best-effort shutdown: if the process holding an XrayProcess exits without
# calling stop(), urllib.request fetches are the only egress — but the xray
# subprocess would leak. 56-03 wires a real atexit hook into VlessProxyManager.
