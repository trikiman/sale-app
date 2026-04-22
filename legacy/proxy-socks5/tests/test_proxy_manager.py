import concurrent.futures
import socket
import threading

import proxy_manager


class _FakeFuture:
    def __init__(self, result_value):
        self._result_value = result_value
        self.cancel_called = False

    def result(self):
        return self._result_value

    def cancel(self):
        self.cancel_called = True
        return True


class _FakeExecutor:
    def __init__(self, future_by_proxy):
        self._future_by_proxy = future_by_proxy
        self.shutdown_args = None

    def submit(self, fn, proxy_addr):
        return self._future_by_proxy[proxy_addr]

    def shutdown(self, wait, cancel_futures):
        self.shutdown_args = (wait, cancel_futures)


def _patch_refresh(monkeypatch, pm, executor, as_completed_impl):
    monkeypatch.setattr(
        concurrent.futures,
        "ThreadPoolExecutor",
        lambda max_workers: executor,
    )
    monkeypatch.setattr(concurrent.futures, "as_completed", as_completed_impl)
    monkeypatch.setattr(pm, "_save_cache", lambda: None)
    monkeypatch.setattr(pm, "_track_event", lambda *args, **kwargs: None)


def test_refresh_proxy_list_cancels_pending_and_never_waits_on_workers(monkeypatch):
    """Regression: shutdown(wait=True) deadlocked the scheduler for 33h when
    SOCKS5 probe threads got stuck in kernel-level recv(). Shutdown must NOT
    wait for running workers."""
    first = _FakeFuture(("1.1.1.1:1080", 0.1))
    second = _FakeFuture(None)
    executor = _FakeExecutor({
        "1.1.1.1:1080": first,
        "2.2.2.2:1080": second,
    })

    monkeypatch.setattr(proxy_manager, "MAX_CACHED", 1)

    def _as_completed(futures, timeout=None):
        # Verify that the refresh path passes an outer timeout so the main
        # thread can never block forever if every future stalls.
        assert timeout is not None, "refresh_proxy_list must pass an outer timeout"
        return iter([first])

    pm = proxy_manager.ProxyManager(log_func=lambda message: None)
    pm._cache = {"updated_at": None, "proxies": []}
    monkeypatch.setattr(pm, "_fetch_proxy_list", lambda: ["1.1.1.1:1080", "2.2.2.2:1080"])
    _patch_refresh(monkeypatch, pm, executor, _as_completed)

    found = pm.refresh_proxy_list()

    assert found == 1
    assert second.cancel_called is True
    # Critical: wait=False. Waiting would deadlock if a worker is stuck in
    # recv() — that is exactly how the scheduler hung in production.
    assert executor.shutdown_args == (False, True)
    assert len(pm._cache["proxies"]) == 1
    assert pm._cache["proxies"][0]["addr"] == "1.1.1.1:1080"
    assert pm._cache["proxies"][0]["speed"] == 0.1


def test_refresh_proxy_list_handles_outer_timeout(monkeypatch):
    """If every probe stalls, as_completed raises TimeoutError. The refresh
    must swallow it, still call shutdown(wait=False, ...), and return a
    (possibly empty) result instead of propagating the error upward."""
    stuck = _FakeFuture(None)
    executor = _FakeExecutor({"3.3.3.3:1080": stuck})

    def _as_completed(futures, timeout=None):
        raise concurrent.futures.TimeoutError()

    pm = proxy_manager.ProxyManager(log_func=lambda message: None)
    pm._cache = {"updated_at": None, "proxies": []}
    monkeypatch.setattr(pm, "_fetch_proxy_list", lambda: ["3.3.3.3:1080"])
    _patch_refresh(monkeypatch, pm, executor, _as_completed)

    found = pm.refresh_proxy_list()

    assert found == 0
    assert stuck.cancel_called is True
    assert executor.shutdown_args == (False, True)


def test_test_proxy_skips_httpx_when_socks5_preflight_fails(monkeypatch):
    """_test_proxy must NOT call the expensive httpx probe when the raw-socket
    SOCKS5 greeting already proved the proxy is dead. This is what keeps
    refresh_proxy_list fast and stall-free."""
    pm = proxy_manager.ProxyManager(log_func=lambda message: None)
    monkeypatch.setattr(proxy_manager.ProxyManager, "_socks5_preflight", staticmethod(lambda addr, **_: False))
    monkeypatch.setattr(pm, "_track_event", lambda *args, **kwargs: None)
    probe_calls = []

    def _probe(*args, **kwargs):
        probe_calls.append((args, kwargs))
        return True

    monkeypatch.setattr(pm, "_probe_vkusvill", _probe)

    assert pm._test_proxy("9.9.9.9:1080") is None
    assert probe_calls == []


def test_test_proxy_runs_httpx_when_preflight_succeeds(monkeypatch):
    pm = proxy_manager.ProxyManager(log_func=lambda message: None)
    monkeypatch.setattr(proxy_manager.ProxyManager, "_socks5_preflight", staticmethod(lambda addr, **_: True))
    monkeypatch.setattr(pm, "_track_event", lambda *args, **kwargs: None)
    monkeypatch.setattr(pm, "_probe_vkusvill", lambda *a, **kw: True)

    result = pm._test_proxy("9.9.9.9:1080")

    assert result is not None
    addr, speed = result
    assert addr == "9.9.9.9:1080"
    assert speed >= 0


def test_socks5_preflight_returns_false_on_connect_timeout():
    """192.0.2.0/24 is TEST-NET-1 — packets are dropped by routers everywhere,
    so connect() always times out. The preflight must return False within the
    configured connect_timeout and never raise."""
    ok = proxy_manager.ProxyManager._socks5_preflight(
        "192.0.2.1:1080", connect_timeout=0.5, handshake_timeout=0.5
    )
    assert ok is False


def test_socks5_preflight_handles_plain_tcp_listener():
    """A listener that accepts TCP but never answers the SOCKS5 greeting must
    be rejected by the preflight within handshake_timeout — this is the exact
    failure mode that hung the production scheduler."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]
    stop = threading.Event()

    def _accept_and_idle():
        conn = None
        try:
            server.settimeout(1.5)
            conn, _ = server.accept()
            # Hold the connection open without ever writing a SOCKS5 reply.
            while not stop.is_set():
                try:
                    conn.settimeout(0.1)
                    conn.recv(1)
                except (socket.timeout, OSError):
                    pass
        except (socket.timeout, OSError):
            pass
        finally:
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass

    t = threading.Thread(target=_accept_and_idle, daemon=True)
    t.start()
    try:
        ok = proxy_manager.ProxyManager._socks5_preflight(
            f"127.0.0.1:{port}", connect_timeout=1.0, handshake_timeout=0.5
        )
        assert ok is False
    finally:
        stop.set()
        try:
            server.close()
        except Exception:
            pass


def test_socks5_preflight_rejects_malformed_address():
    assert proxy_manager.ProxyManager._socks5_preflight("not-an-address") is False
    assert proxy_manager.ProxyManager._socks5_preflight(":1080") is False
    assert proxy_manager.ProxyManager._socks5_preflight("1.2.3.4:notaport") is False

