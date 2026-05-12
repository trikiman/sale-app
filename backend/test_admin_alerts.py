"""Phase 80 (v1.25 OBS-08/09/10) — admin alert module tests.

Verifies:
- No-op when TELEGRAM_TOKEN missing
- No-op when ADMIN_TELEGRAM_CHAT_IDS missing/empty
- Happy-path: POST to Telegram API, ledger entry written
- Cooldown: same kind within window is skipped
- force=True bypasses cooldown
- Multi-chat fanout with partial failure
- Ledger I/O failures never raise
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def tmp_ledger(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Per-test tmp ledger path."""
    path = tmp_path / "admin_alerts.jsonl"
    monkeypatch.setenv("SALEAPP_ADMIN_ALERTS_PATH", str(path))
    # Re-import to pick up env var
    from backend import admin_alerts
    monkeypatch.setattr(admin_alerts, "LEDGER_PATH", str(path))
    return path


@pytest.fixture
def fake_httpx(monkeypatch: pytest.MonkeyPatch):
    """Replace admin_alerts.httpx.post with a controllable fake."""
    from backend import admin_alerts

    calls: list[dict] = []

    class _FakeResp:
        def __init__(self, status_code: int = 200, text: str = "ok"):
            self.status_code = status_code
            self.text = text

    def _fake_post(url, data=None, timeout=None, **kwargs):
        calls.append({"url": url, "data": dict(data or {})})
        # Default: 200 OK
        return _FakeResp(status_code=200, text="ok")

    class _FakeHttpx:
        post = staticmethod(_fake_post)

    monkeypatch.setattr(admin_alerts, "httpx", _FakeHttpx)
    return calls


def test_no_token_is_noop(tmp_ledger, monkeypatch, fake_httpx):
    from backend import admin_alerts
    monkeypatch.delenv("TELEGRAM_TOKEN", raising=False)
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_IDS", "111")

    result = admin_alerts.send_admin_alert("pool_dead", "test")
    assert result["sent"] is False
    assert result["reason"] == "no_token"
    assert len(fake_httpx) == 0
    assert not tmp_ledger.exists()


def test_no_chat_ids_is_noop(tmp_ledger, monkeypatch, fake_httpx):
    from backend import admin_alerts
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_IDS", "")

    result = admin_alerts.send_admin_alert("pool_dead", "test")
    assert result["sent"] is False
    assert result["reason"] == "no_admin_chat_ids"
    assert len(fake_httpx) == 0


def test_happy_path_sends_and_records(tmp_ledger, monkeypatch, fake_httpx):
    from backend import admin_alerts
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_IDS", "111,222")

    result = admin_alerts.send_admin_alert("pool_dead", "pool is dead")

    assert result["sent"] is True
    assert result["reason"] == "ok"
    assert set(result["sent_to"]) == {111, 222}
    assert len(fake_httpx) == 2
    # Check URL format
    assert "api.telegram.org/botfake-token/sendMessage" in fake_httpx[0]["url"]
    # Check ledger entry
    entries = [json.loads(line) for line in tmp_ledger.read_text().splitlines() if line.strip()]
    assert len(entries) == 1
    assert entries[0]["kind"] == "pool_dead"
    assert set(entries[0]["sent_to"]) == {111, 222}


def test_cooldown_skips_duplicate_kind(tmp_ledger, monkeypatch, fake_httpx):
    from backend import admin_alerts
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_IDS", "111")

    # First send
    r1 = admin_alerts.send_admin_alert("pool_dead", "first")
    assert r1["sent"] is True

    # Second send within 30-min cooldown
    r2 = admin_alerts.send_admin_alert("pool_dead", "second")
    assert r2["sent"] is False
    assert r2["reason"] == "cooldown_active"
    assert r2["cooldown_remaining_s"] > 0
    # httpx called only once
    assert len(fake_httpx) == 1


def test_force_bypasses_cooldown(tmp_ledger, monkeypatch, fake_httpx):
    from backend import admin_alerts
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_IDS", "111")

    admin_alerts.send_admin_alert("pool_dead", "first")
    r = admin_alerts.send_admin_alert("pool_dead", "second", force=True)

    assert r["sent"] is True
    assert len(fake_httpx) == 2


def test_different_kinds_dont_share_cooldown(tmp_ledger, monkeypatch, fake_httpx):
    from backend import admin_alerts
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_IDS", "111")

    r1 = admin_alerts.send_admin_alert("pool_dead", "first")
    r2 = admin_alerts.send_admin_alert("breaker_transition", "second")

    assert r1["sent"] is True
    assert r2["sent"] is True
    assert len(fake_httpx) == 2


def test_custom_cooldown_override(tmp_ledger, monkeypatch, fake_httpx):
    from backend import admin_alerts
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_IDS", "111")

    admin_alerts.send_admin_alert("pool_dead", "first", cooldown_s=0)
    # cooldown=0 → next call should send
    r2 = admin_alerts.send_admin_alert("pool_dead", "second", cooldown_s=0)

    assert r2["sent"] is True
    assert len(fake_httpx) == 2


def test_partial_failure_reports_errors(tmp_ledger, monkeypatch):
    """Two chats: one 403 (bot blocked), one 200. Result records both."""
    from backend import admin_alerts

    class _FakeResp:
        def __init__(self, sc, text="ok"):
            self.status_code = sc
            self.text = text

    call_count = {"n": 0}

    def _fake_post(url, data=None, timeout=None, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return _FakeResp(403, "Forbidden: bot was blocked by the user")
        return _FakeResp(200, "ok")

    class _FakeHttpx:
        post = staticmethod(_fake_post)

    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_IDS", "111,222")
    monkeypatch.setattr(admin_alerts, "httpx", _FakeHttpx)

    result = admin_alerts.send_admin_alert("pool_dead", "test")

    # One succeeded → sent=True
    assert result["sent"] is True
    assert result["sent_to"] == [222]

    # Ledger records errors for the failed chat
    entries = [json.loads(line) for line in tmp_ledger.read_text().splitlines() if line.strip()]
    assert len(entries) == 1
    assert "errors" in entries[0]
    assert entries[0]["errors"][0]["chat_id"] == 111
    assert entries[0]["errors"][0]["status"] == 403


def test_ledger_io_failure_does_not_raise(tmp_path, monkeypatch, fake_httpx):
    """If the ledger file can't be written, send must still report success
    (or cooldown status) without raising."""
    from backend import admin_alerts

    bad_path = str(tmp_path / "nonexistent" / "sub" / "alerts.jsonl")
    # This path has a non-creatable parent due to a file in the way
    (tmp_path / "nonexistent").write_text("blocking file")
    monkeypatch.setattr(admin_alerts, "LEDGER_PATH", bad_path)
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_IDS", "111")

    # Must not raise
    result = admin_alerts.send_admin_alert("pool_dead", "test")
    assert result["sent"] is True  # httpx call succeeded
    # Ledger write silently failed


def test_invalid_chat_id_in_env_is_ignored(tmp_ledger, monkeypatch, fake_httpx):
    """Malformed ADMIN_TELEGRAM_CHAT_IDS entries are dropped, not crashing."""
    from backend import admin_alerts
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_IDS", "111,not_an_int,222, ,333")

    result = admin_alerts.send_admin_alert("pool_dead", "test")
    assert result["sent"] is True
    assert set(result["sent_to"]) == {111, 222, 333}


def test_read_recent_returns_entries(tmp_ledger, monkeypatch, fake_httpx):
    from backend import admin_alerts
    monkeypatch.setenv("TELEGRAM_TOKEN", "fake-token")
    monkeypatch.setenv("ADMIN_TELEGRAM_CHAT_IDS", "111")

    admin_alerts.send_admin_alert("pool_dead", "first", force=True)
    admin_alerts.send_admin_alert("pool_dead", "second", force=True)
    admin_alerts.send_admin_alert("pool_dead", "third", force=True)

    recent = admin_alerts.read_recent(limit=2)
    assert len(recent) == 2
    assert recent[0]["message"] == "second"
    assert recent[1]["message"] == "third"
