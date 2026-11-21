"""Health must distinguish standing egress debt from a new fault.

The VLESS pool has been empty since 18.11.2026 while all three scrapers keep collecting
(direct / URnetwork), so `/api/health/deep` has said `degraded` every single time. That is
how noise becomes habit: when gap #11 appeared, the daily report blamed egress and both probes
timed out — and the real cause was a JS deadline on a 100-card modal. The reasons are now split
so `acute` means "something that is NOT the known empty pool".
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = (ROOT / "backend/main.py").read_text(encoding="utf-8")


def test_chronic_prefixes_cover_the_empty_pool():
    m = re.search(r"_CHRONIC_REASON_PREFIXES[^=]*=\s*\(([^)]*)\)", SRC)
    assert m, "the chronic classifier must exist"
    assert "pool_below_min_healthy" in m.group(1)


def test_snapshot_splits_chronic_from_acute():
    for key in ('"chronic_reasons"', '"acute_reasons"', '"acute"', '"status_note"'):
        assert key in SRC, f"{key} missing from the health snapshot"


def test_status_keeps_the_documented_obs02_meaning():
    # existing monitors read `status`; the new fields must not repurpose it
    assert 'if n_failed == 0:\n        status = "healthy"' in SRC
    assert 'status = "degraded"' in SRC


def test_egress_debt_only_is_labelled():
    assert 'status_note = "egress_debt_only"' in SRC
    body = SRC.split('status_note = "egress_debt_only"')[0].rsplit("\n", 4)[-4:]
    joined = "\n".join(body)
    assert "chronic_reasons" in joined and "acute_reasons" in joined, (
        "the label may only apply when nothing acute is wrong"
    )


def test_pool_empty_alone_is_not_acute():
    """A pool-only reason list must produce acute == False."""
    reasons = ["pool_below_min_healthy:0_lt_5"]
    chronic_prefixes = ("pool_below_min_healthy",)
    chronic = [r for r in reasons if r.startswith(chronic_prefixes)]
    acute = [r for r in reasons if r not in chronic]
    assert acute == []


def test_a_dead_scraper_stays_acute():
    reasons = ["pool_below_min_healthy:0_lt_5", "stale_products_3600s"]
    chronic_prefixes = ("pool_below_min_healthy",)
    chronic = [r for r in reasons if r.startswith(chronic_prefixes)]
    acute = [r for r in reasons if r not in chronic]
    assert acute == ["stale_products_3600s"]