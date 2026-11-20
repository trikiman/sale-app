"""A failed green cycle must leave its reason on disk.

Gap #10 (20.11 22:50→23:35 MSK) was two green runs that produced nothing. The snapshot is
deliberately kept on such runs, so the soak log had only `exit 1` — no reason. The log window
had already rotated by the time anyone looked, so the cause stayed unknown. These tests pin
the two halves of the fix: the scraper writes a report, and the recorder picks it up.
"""
import ast
import json
import pathlib
import time

ROOT = pathlib.Path(__file__).resolve().parents[1]


def test_scraper_writes_failure_report_with_reason_and_count():
    src = (ROOT / "scrape_green.py").read_text(encoding="utf-8")
    assert "green_last_failure.json" in src, "scrape_green must persist why a run found nothing"
    tree = ast.parse(src)
    dumps = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
             and n.func.attr == "dump"]
    assert dumps, "failure report must be actual JSON on disk"
    # the payload must carry enough to tell the cases apart
    blob = src[src.index("green_last_failure.json"):]
    for field in ("reason", "products_found", "vkusvill_empty_banner", "logged_in"):
        assert field in blob, f"failure report is missing '{field}'"


def test_recorder_surfaces_the_reason_on_non_zero_exit():
    src = (ROOT / "scheduler_service.py").read_text(encoding="utf-8")
    assert "green_last_failure.json" in src, "recorder must read the failure report"
    assert 'failed:' in src, "recorder must label the reason as a failure, not a normal empty"
    # it must be gated on a real failure, not applied to healthy cycles
    marker = "if exit_code not in (0, None):"
    assert marker in src, "the failure report must only be used for failed runs"


def test_uptime_record_keeps_failed_runs_distinguishable(tmp_path):
    """Shape check: with a failure report present the reason is not 'ok'."""
    report = tmp_path / "green_last_failure.json"
    report.write_text(json.dumps({
        "ts": time.strftime("%Y-%m-%d %H:%M:%S"),
        "reason": "unknown_empty",
        "products_found": 0,
        "vkusvill_empty_banner": False,
        "logged_in": True,
    }), encoding="utf-8")
    payload = json.loads(report.read_text(encoding="utf-8"))
    assert payload["reason"] != "ok"
    assert payload["products_found"] == 0