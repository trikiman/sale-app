"""Unit tests for scrape_merge.py NEW-product detection (v1.27).

The merge step writes per-product `isNew` based on whether the id was
present in the immediately-prior run's snapshot at
``data/previous_run_ids.json``. After writing proposals.json the merge
also persists the current run's ids as the next run's baseline.
"""
from __future__ import annotations

import json
import os
import sys
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


def _run_merge(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> dict:
    """Invoke scrape_merge.merge_products with DATA_DIR redirected to a tmp dir."""
    import importlib

    # Reload to bind to fresh DATA_DIR — the module reads it at import time.
    if "scrape_merge" in sys.modules:
        del sys.modules["scrape_merge"]
    import scrape_merge as sm  # noqa: E402

    monkeypatch.setattr(sm, "DATA_DIR", str(data_dir), raising=True)
    # The merge also writes to miniapp/public/data.json — point that at a
    # throwaway dir to avoid touching the real frontend.
    monkeypatch.setattr(sm, "BASE_DIR", str(data_dir.parent), raising=True)
    sm.merge_products()
    return _read_proposals(data_dir)


def test_first_run_marks_nothing_new(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """No previous_run_ids.json exists → all isNew flags must be False."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "miniapp" / "public").mkdir(parents=True)
    _seed_color_files(data_dir, {
        "green": [{"id": "1", "name": "A", "type": "green"}],
        "red": [{"id": "2", "name": "B", "type": "red"}],
        "yellow": [],
    })
    out = _run_merge(monkeypatch, data_dir)
    new_count = sum(1 for p in out["products"] if p.get("isNew"))
    assert new_count == 0, "first run should not mark anything as new"
    # Snapshot must be persisted for the next run.
    snap = json.loads((data_dir / "previous_run_ids.json").read_text(encoding="utf-8"))
    assert set(snap["ids"]) == {"1", "2"}


def test_second_run_flags_only_new_ids(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """ids present in run-1 stay isNew=False on run-2; new ids flip to True."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "miniapp" / "public").mkdir(parents=True)
    # Seed an existing baseline as if run-1 already happened.
    (data_dir / "previous_run_ids.json").write_text(
        json.dumps({"ids": ["1", "2", "3"], "count": 3}),
        encoding="utf-8",
    )
    _seed_color_files(data_dir, {
        "green": [
            {"id": "1", "name": "A", "type": "green"},   # was in baseline
            {"id": "4", "name": "D", "type": "green"},   # NEW
        ],
        "red": [
            {"id": "2", "name": "B", "type": "red"},     # was in baseline
            {"id": "5", "name": "E", "type": "red"},     # NEW
        ],
        "yellow": [],
    })
    out = _run_merge(monkeypatch, data_dir)
    by_id = {p["id"]: p for p in out["products"]}
    assert by_id["1"]["isNew"] is False
    assert by_id["2"]["isNew"] is False
    assert by_id["4"]["isNew"] is True
    assert by_id["5"]["isNew"] is True
    # Baseline must be updated for the next run.
    snap = json.loads((data_dir / "previous_run_ids.json").read_text(encoding="utf-8"))
    assert set(snap["ids"]) == {"1", "2", "4", "5"}


def test_third_run_demotes_previously_new_ids(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Items marked isNew on run-2 must flip back to isNew=False on run-3."""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (tmp_path / "miniapp" / "public").mkdir(parents=True)
    # Baseline reflects what run-2 just produced — items 4 and 5 were "new" then.
    (data_dir / "previous_run_ids.json").write_text(
        json.dumps({"ids": ["1", "2", "4", "5"], "count": 4}),
        encoding="utf-8",
    )
    _seed_color_files(data_dir, {
        "green": [
            {"id": "1", "name": "A", "type": "green"},
            {"id": "4", "name": "D", "type": "green"},  # WAS new last run, NOT new now
        ],
        "red": [
            {"id": "5", "name": "E", "type": "red"},    # WAS new last run, NOT new now
            {"id": "6", "name": "F", "type": "red"},    # NEW THIS RUN
        ],
        "yellow": [],
    })
    out = _run_merge(monkeypatch, data_dir)
    by_id = {p["id"]: p for p in out["products"]}
    assert by_id["1"]["isNew"] is False
    assert by_id["4"]["isNew"] is False, "was new last run, must reset"
    assert by_id["5"]["isNew"] is False, "was new last run, must reset"
    assert by_id["6"]["isNew"] is True, "first appearance — must flag"


def test_corrupt_baseline_treated_as_first_run(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If previous_run_ids.json is unreadable, fall back to first-run behavior
    (no false-positive flood)."""
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
    new_count = sum(1 for p in out["products"] if p.get("isNew"))
    assert new_count == 0
