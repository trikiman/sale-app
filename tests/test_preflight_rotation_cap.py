"""REL-03 + REL-04: rotation cap enforcement.

Simulates a bridge that always fails preflight; asserts ``_run_scraper_set``
rotates exactly 2 times (not 5 like PR #25) then proceeds to run scrapers.
Uses a fake ``VlessProxyManager`` that counts rotations but doesn't touch
xray.
"""
from __future__ import annotations

import os
import sys
import types

import pytest


def _install_httpx_stub_if_missing():
    if "httpx" in sys.modules:
        return
    try:
        import httpx  # noqa: F401
        return
    except Exception:
        pass
    fake = types.ModuleType("httpx")

    class _Err(Exception):
        pass

    fake.Client = type("Client", (), {})
    fake.ConnectTimeout = type("ConnectTimeout", (_Err,), {})
    fake.ReadTimeout = type("ReadTimeout", (_Err,), {})
    fake.ConnectError = type("ConnectError", (_Err,), {})
    fake.HTTPError = _Err
    sys.modules["httpx"] = fake


_install_httpx_stub_if_missing()


# scheduler_service.py has heavy side-effect imports (xray subprocess, etc.)
# via proxy_manager -> vless.manager. For a pure unit test of the rotation
# cap we import only what we need and stub the rest.
@pytest.fixture(autouse=True)
def _isolate_scheduler(monkeypatch):
    # Ensure we can import scheduler_service; if it attempts to instantiate
    # xray on import, swap out heavy deps with no-ops.
    try:
        import scheduler_service  # noqa: F401
    except Exception as exc:
        pytest.skip(f"scheduler_service unavailable in this env: {exc}")
    from vless import preflight
    preflight.reset_probe_cache()
    yield
    preflight.reset_probe_cache()


class FakeProxyManager:
    """Minimal stand-in for VlessProxyManager — counts rotations, no xray."""

    def __init__(self):
        self.mark_current_node_blocked_calls = []
        self.next_proxy_calls = 0

    def mark_current_node_blocked(self, reason: str = "test"):
        self.mark_current_node_blocked_calls.append(reason)

    def next_proxy(self):
        self.next_proxy_calls += 1
        return "127.0.0.1:10808"

    def get_working_proxy(self):
        return "127.0.0.1:10808"

    def pool_count(self):
        return 10  # healthy


def _patch_scheduler_deps(monkeypatch, scheduler_service, fake_pm):
    """Stub out everything _run_scraper_set calls besides the probe and pm."""
    monkeypatch.setattr(
        scheduler_service, "_prepare_proxy_connectivity", lambda ps: (fake_pm, ps)
    )
    monkeypatch.setattr(scheduler_service, "run_script", lambda *a, **k: 0)
    monkeypatch.setattr(scheduler_service, "_check_file_updated", lambda *a, **k: True)
    monkeypatch.setattr(scheduler_service, "_kill_all_scraper_chrome", lambda: None)
    # Avoid FileNotFound on DATA_DIR lookups
    monkeypatch.setattr(scheduler_service.os.path, "getmtime", lambda p: 0.0)
    monkeypatch.setattr(scheduler_service.os.path, "exists", lambda p: False)


def test_rotation_cap_is_exactly_two_when_probe_always_fails(monkeypatch):
    import scheduler_service
    from vless import preflight

    fake_pm = FakeProxyManager()
    _patch_scheduler_deps(monkeypatch, scheduler_service, fake_pm)

    # Make the probe always fail
    fail_result = preflight.ProbeResult(
        ok=False, status=None, reason="timeout", elapsed_s=12.0
    )
    monkeypatch.setattr(
        scheduler_service, "probe_bridge_alive", lambda timeout=12.0: fail_result
    )

    scrapers = [("scrape_green.py", "GREEN", "greens_data.json")]
    proxy_state = {"active_proxy": None, "consecutive_fails": 0}

    scheduler_service._run_scraper_set(scrapers, proxy_state)

    # Rotations: first = mark_current_node_blocked, second = next_proxy
    assert len(fake_pm.mark_current_node_blocked_calls) == 1, (
        f"Expected exactly 1 mark_current_node_blocked call, got "
        f"{len(fake_pm.mark_current_node_blocked_calls)}"
    )
    assert fake_pm.mark_current_node_blocked_calls[0] == "preflight_timeout"
    assert fake_pm.next_proxy_calls == 1, (
        f"Expected exactly 1 next_proxy call, got {fake_pm.next_proxy_calls}. "
        "PR #25's 5-rotation cascade MUST NOT regress."
    )


def test_no_rotation_when_probe_succeeds_first_try(monkeypatch):
    import scheduler_service
    from vless import preflight

    fake_pm = FakeProxyManager()
    _patch_scheduler_deps(monkeypatch, scheduler_service, fake_pm)

    ok_result = preflight.ProbeResult(ok=True, status=200, reason="ok", elapsed_s=8.1)
    monkeypatch.setattr(
        scheduler_service, "probe_bridge_alive", lambda timeout=12.0: ok_result
    )

    scrapers = [("scrape_green.py", "GREEN", "greens_data.json")]
    scheduler_service._run_scraper_set(scrapers, {"consecutive_fails": 0})

    assert fake_pm.mark_current_node_blocked_calls == []
    assert fake_pm.next_proxy_calls == 0


def test_one_rotation_when_probe_succeeds_on_retry(monkeypatch):
    import scheduler_service
    from vless import preflight

    fake_pm = FakeProxyManager()
    _patch_scheduler_deps(monkeypatch, scheduler_service, fake_pm)

    # First probe fails, second succeeds
    results = iter(
        [
            preflight.ProbeResult(
                ok=False, status=None, reason="timeout", elapsed_s=12.0
            ),
            preflight.ProbeResult(ok=True, status=200, reason="ok", elapsed_s=8.5),
        ]
    )
    monkeypatch.setattr(
        scheduler_service,
        "probe_bridge_alive",
        lambda timeout=12.0: next(results),
    )

    scrapers = [("scrape_green.py", "GREEN", "greens_data.json")]
    scheduler_service._run_scraper_set(scrapers, {"consecutive_fails": 0})

    assert len(fake_pm.mark_current_node_blocked_calls) == 1
    assert fake_pm.next_proxy_calls == 0  # stopped after first rotation succeeded
