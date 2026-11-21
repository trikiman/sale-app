"""A failed green run must always leave a reason — including failures before classification.

21.11.2026, 06:18: a cycle failed, `live_count` correctly came back null (the freshness fix
working), and there was no reason anywhere: `green_last_failure.json` is written only on the
"empty section, no banner" path, and the log window had rotated. This adds a fallback written
from `__main__`, where the process knows it gave up, and refuses to overwrite a detailed
report from the same run.
"""
import ast
import json
import os
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "scrape_green.py").read_text(encoding="utf-8")


def _load_fallback(tmp_path):
    tree = ast.parse(SRC)
    fn = next(n for n in tree.body
              if isinstance(n, ast.FunctionDef) and n.name == "_write_generic_failure")
    code = compile(ast.Module(body=[fn], type_ignores=[]), "<fallback>", "exec")
    namespace = {"os": os, "time": time, "json": json, "DATA_DIR": str(tmp_path), "print": print}
    exec(code, namespace)  # noqa: S102 — isolated helper under test
    return namespace["_write_generic_failure"], pathlib.Path(tmp_path)


def test_main_calls_the_fallback_on_failure():
    tree = ast.parse(SRC)
    main_if = next(n for n in tree.body
                   if isinstance(n, ast.If)
                   and isinstance(n.test, ast.Compare)
                   and isinstance(n.test.left, ast.Name)
                   and n.test.left.id == "__name__")
    body_src = ast.get_source_segment(SRC, main_if) or ""
    assert "_write_generic_failure()" in body_src, "failure must leave a reason on disk"
    assert "SystemExit(0 if _ok else 1)" in body_src, "exit code contract must stay"


def test_fallback_writes_unclassified_reason(tmp_path):
    write, root = _load_fallback(tmp_path)
    write()
    payload = json.loads((root / "green_last_failure.json").read_text(encoding="utf-8"))
    assert payload["reason"] == "unclassified_failure"
    assert payload["ts"]


def test_fallback_keeps_a_fresh_detailed_report(tmp_path):
    write, root = _load_fallback(tmp_path)
    detailed = root / "green_last_failure.json"
    detailed.write_text(json.dumps({"ts": "x", "reason": "unknown_empty",
                                    "products_found": 0}), encoding="utf-8")
    write()
    payload = json.loads(detailed.read_text(encoding="utf-8"))
    assert payload["reason"] == "unknown_empty", (
        "a detailed report from this same run must win over the generic one"
    )


def test_fallback_overwrites_a_stale_report(tmp_path):
    write, root = _load_fallback(tmp_path)
    stale = root / "green_last_failure.json"
    stale.write_text(json.dumps({"ts": "old", "reason": "unknown_empty"}), encoding="utf-8")
    old = time.time() - 3600
    os.utime(stale, (old, old))
    write()
    payload = json.loads(stale.read_text(encoding="utf-8"))
    assert payload["reason"] == "unclassified_failure"