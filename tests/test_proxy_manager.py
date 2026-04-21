import concurrent.futures

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


def test_refresh_proxy_list_cancels_pending_futures_on_early_exit(monkeypatch):
    first = _FakeFuture(("1.1.1.1:1080", 0.1))
    second = _FakeFuture(None)
    executor = _FakeExecutor({
        "1.1.1.1:1080": first,
        "2.2.2.2:1080": second,
    })

    monkeypatch.setattr(proxy_manager, "MAX_CACHED", 1)
    monkeypatch.setattr(
        concurrent.futures,
        "ThreadPoolExecutor",
        lambda max_workers: executor,
    )
    monkeypatch.setattr(
        concurrent.futures,
        "as_completed",
        lambda futures: iter([first]),
    )

    pm = proxy_manager.ProxyManager(log_func=lambda message: None)
    pm._cache = {"updated_at": None, "proxies": []}
    monkeypatch.setattr(pm, "_fetch_proxy_list", lambda: ["1.1.1.1:1080", "2.2.2.2:1080"])
    monkeypatch.setattr(pm, "_save_cache", lambda: None)
    monkeypatch.setattr(pm, "_track_event", lambda *args, **kwargs: None)

    found = pm.refresh_proxy_list()

    assert found == 1
    assert second.cancel_called is True
    assert executor.shutdown_args == (True, True)
    assert len(pm._cache["proxies"]) == 1
    assert pm._cache["proxies"][0]["addr"] == "1.1.1.1:1080"
    assert pm._cache["proxies"][0]["speed"] == 0.1
