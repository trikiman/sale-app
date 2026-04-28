"""Tests for v1.16 Bug Reports endpoint (BUG-05..BUG-09)."""
import io
import json
import os
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
from fastapi.testclient import TestClient
from PIL import Image

import backend.main as main


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Override BUG_REPORTS_DIR to a tmp dir per-test, plus a known admin token."""
    bug_dir = tmp_path / "bug_reports"
    monkeypatch.setattr(main, "BUG_REPORTS_DIR", str(bug_dir))
    monkeypatch.setattr(
        main,
        "BUG_REPORTS_LAST_READ_PATH",
        str(tmp_path / "bug_reports_last_read.json"),
    )
    monkeypatch.setattr(main, "ADMIN_TOKEN", "test-admin-token")
    return TestClient(main.app)


def _valid_png_bytes(size=(10, 10), color=(255, 0, 0)) -> bytes:
    img = Image.new("RGB", size, color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _post_report(client, text="A real bug report description", category="ui",
                 telegram_id="1234567", photo_bytes=None, photo_mime="image/png",
                 photo_name="bug.png", **extra):
    """Helper to POST a bug report with the right multipart shape."""
    data = {
        "text": text,
        "category": category,
        "telegram_id": telegram_id,
    }
    data.update(extra)
    files = {}
    if photo_bytes is not None:
        files["photo"] = (photo_name, photo_bytes, photo_mime)
    headers = {"X-Telegram-User-Id": str(telegram_id)}
    return client.post("/api/bug-reports", data=data, files=files or None, headers=headers)


# ─── BUG-05: Storage ───────────────────────────────────────────────────────────

def test_submit_report_writes_json_file(client):
    resp = _post_report(client, text="Корзина не открывается, кнопка зависает", category="cart")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["success"] is True
    assert body["report_id"]
    # Verify file exists
    saved_files = [f for f in os.listdir(main.BUG_REPORTS_DIR) if f.endswith(".json")]
    assert len(saved_files) == 1
    # Verify contents
    with open(os.path.join(main.BUG_REPORTS_DIR, saved_files[0]), encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["text"] == "Корзина не открывается, кнопка зависает"
    assert payload["category"] == "cart"
    assert payload["telegram_id"] == "1234567"
    assert payload["report_id"] == body["report_id"]
    assert payload["has_photo"] is False
    assert "timestamp" in payload


def test_submit_report_with_photo_writes_jpg_alongside(client):
    photo = _valid_png_bytes()
    resp = _post_report(client, photo_bytes=photo, photo_mime="image/png")
    assert resp.status_code == 200, resp.text
    report_id = resp.json()["report_id"]
    json_path = os.path.join(main.BUG_REPORTS_DIR, f"{report_id}.json")
    jpg_path = os.path.join(main.BUG_REPORTS_DIR, f"{report_id}.jpg")
    assert os.path.exists(json_path)
    assert os.path.exists(jpg_path)
    # Photo bytes preserved
    assert open(jpg_path, "rb").read() == photo


def test_submit_report_attaches_console_logs(client):
    logs = [
        {"level": "error", "msg": "Failed fetch", "ts": 1700000000000},
        {"level": "warn", "msg": "Slow render", "ts": 1700000001000},
    ]
    resp = _post_report(
        client,
        text="UI broke after my last add to cart click",
        console_logs=json.dumps(logs),
    )
    assert resp.status_code == 200
    saved = [f for f in os.listdir(main.BUG_REPORTS_DIR) if f.endswith(".json")][0]
    with open(os.path.join(main.BUG_REPORTS_DIR, saved), encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["console_logs"] == logs


def test_submit_report_attaches_runtime_meta(client):
    resp = _post_report(
        client,
        text="Catalogue page is empty after refresh today",
        category="ui",
        route="/catalog",
        viewport="1920x1080",
        user_agent="Mozilla/5.0 (Windows; chrome)",
        app_version="abc1234",
    )
    assert resp.status_code == 200
    saved = [f for f in os.listdir(main.BUG_REPORTS_DIR) if f.endswith(".json")][0]
    with open(os.path.join(main.BUG_REPORTS_DIR, saved), encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["route"] == "/catalog"
    assert payload["viewport"] == "1920x1080"
    assert payload["user_agent"] == "Mozilla/5.0 (Windows; chrome)"
    assert payload["app_version"] == "abc1234"


# ─── BUG-06: Auth ──────────────────────────────────────────────────────────────

def test_submit_report_rejects_missing_auth_header(client):
    # No X-Telegram-User-Id header
    resp = client.post(
        "/api/bug-reports",
        data={
            "text": "An issue I want to report properly",
            "category": "ui",
            "telegram_id": "1234567",
        },
    )
    assert resp.status_code == 403
    # No file should have been written
    if os.path.isdir(main.BUG_REPORTS_DIR):
        assert not [f for f in os.listdir(main.BUG_REPORTS_DIR) if f.endswith(".json")]


def test_submit_report_rejects_mismatched_auth_header(client):
    # Header user does NOT match the body telegram_id
    resp = client.post(
        "/api/bug-reports",
        data={
            "text": "An issue I want to report properly",
            "category": "ui",
            "telegram_id": "1234567",
        },
        headers={"X-Telegram-User-Id": "9999999"},
    )
    assert resp.status_code == 403


# ─── BUG-07: Validation ───────────────────────────────────────────────────────

def test_submit_report_rejects_oversized_photo(client):
    big_photo = b"\x00" * (main.BUG_REPORT_MAX_PHOTO_BYTES + 1)
    resp = _post_report(client, photo_bytes=big_photo, photo_mime="image/png")
    assert resp.status_code == 400
    assert "exceeds" in resp.json()["detail"].lower()
    # No state written
    assert not [f for f in os.listdir(main.BUG_REPORTS_DIR) if f.endswith(".json")] if os.path.isdir(main.BUG_REPORTS_DIR) else True


def test_submit_report_rejects_corrupt_image_bytes(client):
    bad_bytes = b"this is not a real image"
    resp = _post_report(client, photo_bytes=bad_bytes, photo_mime="image/png")
    assert resp.status_code == 400
    assert "decoded" in resp.json()["detail"].lower() or "decode" in resp.json()["detail"].lower()


def test_submit_report_rejects_non_image_mime(client):
    resp = _post_report(
        client, photo_bytes=b"not really an image", photo_mime="text/plain", photo_name="bad.txt"
    )
    assert resp.status_code == 400


def test_submit_report_rejects_too_short_text(client):
    resp = _post_report(client, text="hi")  # below MIN
    assert resp.status_code == 400


def test_submit_report_rejects_too_long_text(client):
    resp = _post_report(client, text="a" * (main.BUG_REPORT_TEXT_MAX + 1))
    assert resp.status_code == 400


def test_submit_report_rejects_unknown_category(client):
    resp = _post_report(client, category="invalid_category_name")
    assert resp.status_code == 400


# ─── BUG-08: Admin list ───────────────────────────────────────────────────────

def test_admin_list_requires_token(client):
    resp = client.get("/api/admin/bug-reports")
    assert resp.status_code == 403


def test_admin_list_returns_empty_when_no_reports(client):
    resp = client.get(
        "/api/admin/bug-reports",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"total": 0, "reports": []}


def test_admin_list_returns_recent_reports_with_preview(client):
    # Submit two reports
    _post_report(client, text="Cart bug — first report happens here clearly", category="cart")
    _post_report(client, text="UI glitch on the second report shown", category="ui")
    resp = client.get(
        "/api/admin/bug-reports",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total"] == 2
    reports = body["reports"]
    assert len(reports) == 2
    # Each entry has the expected shape
    for r in reports:
        assert {"filename", "timestamp", "telegram_id", "category", "text_preview", "has_photo"} <= set(r.keys())


def test_admin_get_one_report_returns_full_payload(client):
    resp = _post_report(client, text="Specific bug detail to verify retrieval works")
    rid = resp.json()["report_id"]
    full = client.get(
        f"/api/admin/bug-reports/{rid}",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert full.status_code == 200
    body = full.json()
    assert body["report_id"] == rid
    assert body["text"] == "Specific bug detail to verify retrieval works"


def test_admin_get_nonexistent_report_returns_404(client):
    full = client.get(
        "/api/admin/bug-reports/nonexistent_xyz",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert full.status_code == 404


def test_admin_get_report_rejects_path_traversal(client):
    full = client.get(
        "/api/admin/bug-reports/..%2Fcookies",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    # Path traversal blocked at sanitize layer (400) or routing layer (404)
    assert full.status_code in (400, 404)


def test_admin_get_photo_returns_404_when_no_photo(client):
    resp = _post_report(client, text="A bug without an attached photo here")
    rid = resp.json()["report_id"]
    photo_resp = client.get(
        f"/api/admin/bug-reports/{rid}/photo",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert photo_resp.status_code == 404


def test_admin_get_photo_returns_jpg(client):
    photo_bytes = _valid_png_bytes()
    resp = _post_report(client, photo_bytes=photo_bytes)
    rid = resp.json()["report_id"]
    photo_resp = client.get(
        f"/api/admin/bug-reports/{rid}/photo",
        headers={"X-Admin-Token": "test-admin-token"},
    )
    assert photo_resp.status_code == 200
    assert photo_resp.headers["content-type"] == "image/jpeg"


# ─── BUG-09: admin/status counts ──────────────────────────────────────────────


def test_admin_status_exposes_bug_reports_counts(client, monkeypatch):
    # Fresh state: no reports
    resp = client.get("/admin/status", headers={"X-Admin-Token": "test-admin-token"})
    assert resp.status_code == 200
    body = resp.json()
    assert "bugReports" in body
    assert body["bugReports"]["count"] == 0
    assert body["bugReports"]["unread"] == 0

    # Submit one report
    _post_report(client, text="A new report submitted right here right now")
    resp = client.get("/admin/status", headers={"X-Admin-Token": "test-admin-token"})
    body = resp.json()
    assert body["bugReports"]["count"] == 1
    assert body["bugReports"]["unread"] == 1

    # After admin lists reports → unread should drop to 0
    client.get("/api/admin/bug-reports", headers={"X-Admin-Token": "test-admin-token"})
    resp = client.get("/admin/status", headers={"X-Admin-Token": "test-admin-token"})
    body = resp.json()
    assert body["bugReports"]["count"] == 1
    assert body["bugReports"]["unread"] == 0
