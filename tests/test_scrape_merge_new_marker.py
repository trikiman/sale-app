"""Unit tests for scrape_merge.py NEW-product detection (v1.27.1).

Sliding-window NEW marker: items get isNew=True for 30 min after their
first appearance, then graduate to isNew=False. Snapshot tracks
``first_seen`` per id so the window survives multiple merge cycles.
Legacy ``{"ids": [...]}`` snapshots are loaded as ancient (won't trip
the window) so a deploy doesn't flip every existing product to NEW.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _seed_color_files(data_dir: Path, by_color: dict[str, list[dict]]) -> None:
    for color, items in by_color.items():
        path = data_dir / f"{color}_products.json"
        path.write_text(
            json.dumps({"products": items, "live_count": len(items)}, ensure_ascii=False),
            encoding="utf-8",
        )


def _read_proposals(data_dir: Path) -> dict:
    return json.loads((data_dir / "proposals.json").read_text(encoding="utf-8"))


def _read_snapshot(data_dir: Path) -> dict:
    return json.loads((data_dir / "previous_run_ids.json").read_text(encoding="utf-8"))


def _run_merge(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> dict:
    """Invoke scrape_merge.merge_products with DATA_DIR redirected."""
    if "scrape_merge" in sys.modules:
        del sys.modules["scrape_merge"]
    import scrape_merge as sm  # noqa: E402

    monkeypatch.setattr(sm, "DATA_DIR", str(data_dir), raising=True)
    monkeypatch.setattr(sm, "BASE_DIR", str(data_dir.parent), raising=True)
    sm.merge_products()
    return _read_proposals(data_dir)


def test_first_run_marks_nothing_new(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No snapshot exists → all isNew flags must be False (cold-start guard).
    Snapshot is created for next run."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "miniapp" / "public").mkdir(parents=True)
    _seed_color_files(data_dir, {
        "green": [{"id": "1", "name": "A", "type": "green"}],
        "red": [{"id": "2", "name": "B", "type": "red"}],
        "yellow": [],
    })
    out = _run_merge(monkeypatch, data_dir)
    assert all(p["isNew"] is False for p in out["products"])
    snap = _read_snapshot(data_dir)
    assert set(snap["first_seen"].keys()) == {"1", "2"}


def test_new_id_gets_isNew_within_window(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ids present in baseline carry first_seen forward; brand-new ids get
    first_seen=now and are isNew=True (within 30-min window)."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "miniapp" / "public").mkdir(parents=True)
    # Existing baseline with first_seen 5 min ago for ids 1,2,3 (still in window).
    five_min_ago = (datetime.now() - timedelta(minutes=5)).isoformat(timespec="seconds")
    (data_dir / "previous_run_ids.json").write_text(json.dumps({
        "first_seen": {"1": five_min_ago, "2": five_min_ago, "3": five_min_ago},
        "count": 3,
    }), encoding="utf-8")
    _seed_color_files(data_dir, {
        "green": [
            {"id": "1", "name": "A", "type": "green"},
            {"id": "4", "name": "D", "type": "green"},  # brand new
        ],
        "red": [{"id": "5", "name": "E", "type": "red"}],  # brand new
        "yellow": [],
    })
    out = _run_merge(monkeypatch, data_dir)
    by_id = {p["id"]: p for p in out["products"]}
    # All 3 (1, 4, 5) should be NEW: 1 because first_seen 5 min ago is < 30 min,
    # 4 and 5 because their first_seen is right now.
    assert by_id["1"]["isNew"] is True
    assert by_id["4"]["isNew"] is True
    assert by_id["5"]["isNew"] is True


def test_isNew_persists_across_multiple_cycles_within_window(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Item that first appeared 10 min ago must still show isNew=True
    even though several merge cycles ran in between (regression guard
    against the v1.27 'one-cycle' bug)."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "miniapp" / "public").mkdir(parents=True)
    ten_min_ago = (datetime.now() - timedelta(minutes=10)).isoformat(timespec="seconds")
    (data_dir / "previous_run_ids.json").write_text(json.dumps({
        "first_seen": {"42": ten_min_ago},
        "count": 1,
    }), encoding="utf-8")
    _seed_color_files(data_dir, {
        "green": [{"id": "42", "name": "Stable", "type": "green"}],
        "red": [],
        "yellow": [],
    })
    out = _run_merge(monkeypatch, data_dir)
    by_id = {p["id"]: p for p in out["products"]}
    assert by_id["42"]["isNew"] is True, "10 min < 30 min window — must still be NEW"
    # Snapshot must preserve the original first_seen, not bump to now.
    snap = _read_snapshot(data_dir)
    assert snap["first_seen"]["42"] == ten_min_ago


def test_isNew_graduates_after_window_expires(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Item whose first_seen is older than 30 min must graduate to
    isNew=False — that's how items eventually stop being NEW."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "miniapp" / "public").mkdir(parents=True)
    forty_min_ago = (datetime.now() - timedelta(minutes=40)).isoformat(timespec="seconds")
    (data_dir / "previous_run_ids.json").write_text(json.dumps({
        "first_seen": {"7": forty_min_ago},
        "count": 1,
    }), encoding="utf-8")
    _seed_color_files(data_dir, {
        "green": [{"id": "7", "name": "Older", "type": "green"}],
        "red": [],
        "yellow": [],
    })
    out = _run_merge(monkeypatch, data_dir)
    by_id = {p["id"]: p for p in out["products"]}
    assert by_id["7"]["isNew"] is False, "40 min > 30 min window — must be normal"


def test_legacy_snapshot_format_loaded_as_ancient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An old-format snapshot (``{"ids": [...]}``) must NOT cause every
    listed item to flip to isNew=True after upgrade — they get loaded
    with first_seen far in the past so they immediately graduate.
    This prevents a flood of false positives on the deploy day."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "miniapp" / "public").mkdir(parents=True)
    (data_dir / "previous_run_ids.json").write_text(json.dumps({
        "ids": ["1", "2", "3"],
        "count": 3,
    }), encoding="utf-8")
    _seed_color_files(data_dir, {
        "green": [
            {"id": "1", "name": "A", "type": "green"},
            {"id": "2", "name": "B", "type": "green"},
            {"id": "3", "name": "C", "type": "green"},
        ],
        "red": [],
        "yellow": [],
    })
    out = _run_merge(monkeypatch, data_dir)
    assert all(p["isNew"] is False for p in out["products"])


def test_corrupt_snapshot_treated_as_first_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "miniapp" / "public").mkdir(parents=True)
    (data_dir / "previous_run_ids.json").write_text("not-json", encoding="utf-8")
    _seed_color_files(data_dir, {
        "green": [{"id": "9", "name": "Z", "type": "green"}],
        "red": [],
        "yellow": [],
    })
    out = _run_merge(monkeypatch, data_dir)
    assert all(p["isNew"] is False for p in out["products"])


def test_dropped_id_removed_from_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An id present in baseline but absent in current run must be
    dropped from snapshot — otherwise stale ids accumulate forever."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "miniapp" / "public").mkdir(parents=True)
    five_min_ago = (datetime.now() - timedelta(minutes=5)).isoformat(timespec="seconds")
    (data_dir / "previous_run_ids.json").write_text(json.dumps({
        "first_seen": {"a": five_min_ago, "b": five_min_ago, "c": five_min_ago},
        "count": 3,
    }), encoding="utf-8")
    _seed_color_files(data_dir, {
        "green": [{"id": "a", "name": "A", "type": "green"}],  # 'b' and 'c' dropped
        "red": [],
        "yellow": [],
    })
    _run_merge(monkeypatch, data_dir)
    snap = _read_snapshot(data_dir)
    assert set(snap["first_seen"].keys()) == {"a"}
