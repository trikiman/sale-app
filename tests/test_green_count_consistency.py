"""The green counter must not contradict the green cards.

Observed live 2026-11-18 04:55 MSK: `/api/products` reported `greenLiveCount: 4`
while the payload carried exactly **one** green card. `greenLiveCount` is read from
proposals.json (stamped at merge time); the cards come from that same payload, so a
green scrape landing between merge and request lets the counter drift ahead of the
list. The UI then advertises "4 зелёных" over a single card — exactly the kind of
discrepancy the operator catches in a screenshot.

The endpoint now exposes `greenListedCount` (cards actually present) and
`greenCountMismatch` (counter minus cards) so the drift is visible in the contract.
"""
from __future__ import annotations


def _src() -> str:
    return open("backend/main.py", encoding="utf-8").read()


def test_response_model_exposes_both_counts() -> None:
    src = _src()
    model = src.split("class ProductsResponse(BaseModel):")[1].split("class ")[0]
    assert "greenListedCount" in model
    assert "greenCountMismatch" in model


def test_endpoint_sets_listed_count_from_the_actual_payload() -> None:
    src = _src()
    assert 'data["greenListedCount"] = _green_in_payload' in src
    # _green_in_payload must be counted over the payload, not inferred elsewhere.
    block = src.split("_green_in_payload = sum(")[1][:200]
    assert 'p.get("type") == "green"' in block
    assert 'data.get("products")' in block


def test_mismatch_is_none_when_counts_agree_or_list_is_empty() -> None:
    src = _src()
    block = src.split('data["greenListedCount"] = _green_in_payload')[1].split("return data")[0]
    assert "if _live_green and _green_in_payload" in block, (
        "a zero/absent counter or an empty list must not raise a mismatch"
    )
    assert 'data["greenCountMismatch"] = None' in block
