"""The deep-health freshness ages must fit one real cycle, not an imagined one.

OBS-02 assumed a cycle finishes within 15 minutes. Measured on 21.11.2026: GREEN alone takes
570-800 s on a 100-card markdown day, then RED, then YELLOW — 18-20 minutes end to end on
1 vCPU. With a 15-minute limit the endpoint reported `stale_cycle` and `stale_products` during
perfectly healthy cycles, and that constant noise is what let gap #11 be blamed on egress.

30 min (cycle) and 45 min (products, matching the tier staleness thresholds) still catch a
scheduler that genuinely stopped: three missed cycles.
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "backend/main.py").read_text(encoding="utf-8")


def _value(name: str) -> int:
    m = re.search(rf"{name} = (\d+) \* 60", SRC)
    assert m, f"{name} not found"
    return int(m.group(1))


def test_cycle_threshold_fits_one_full_cycle():
    assert _value("_DEEP_MAX_CYCLE_AGE_S") >= 30, (
        "one cycle is 18-20 min on a markdown day; 15 min fires during healthy runs"
    )


def test_products_threshold_matches_tier_staleness():
    assert _value("_DEEP_MAX_PRODUCTS_AGE_S") == 45


def test_thresholds_are_not_unbounded():
    assert _value("_DEEP_MAX_CYCLE_AGE_S") <= 60
    assert _value("_DEEP_MAX_PRODUCTS_AGE_S") <= 60


def test_thresholds_are_still_used():
    assert "_DEEP_MAX_CYCLE_AGE_S" in SRC.split("_DEEP_MAX_CYCLE_AGE_S = ")[1]
    assert "stale_cycle_" in SRC and "stale_products_" in SRC