#!/usr/bin/env python3
"""
v1.20 Phase 64 — Ablation harness for basket_add.php 16-field payload.

Operator-run. For each of the 16 fields in cart.vkusvill_api's basket_add
payload, issues N cart-adds with that one field removed and measures:
  - success_rate  (fraction of calls returning success=Y)
  - p50_ms, p95_ms (request latency)

A field is classified as:
  - "droppable"  if success_rate >= 0.95 with it removed (server accepted)
  - "required"   otherwise

Baseline: all 16 fields present. Shipped JSON output feeds research doc
Section E (.planning/research/v1.20-API-SPIKE.md).

Usage (LIVE — will actually add/remove products from the given user's
VkusVill cart, so run against a throwaway test account):

  python scripts/ablate_basket_add_payload.py \\
    --user-id 12345 \\
    --product-id 731 \\
    --n-per-field 20 \\
    --output .planning/research/ablation-731.json

Usage (DRY-RUN — no network, validates payload shape + CLI wiring only,
safe for CI):

  python scripts/ablate_basket_add_payload.py \\
    --user-id 12345 \\
    --product-id 731 \\
    --n-per-field 2 \\
    --dry-run

The dry-run prints a synthetic results block to stdout (or --output) so
smoke check 64-C can assert "script runs end-to-end without network."

Safety: NOT called from any hot path. Not a pytest test. The live mode
touches VkusVill's production basket API — only run from an interactive
operator session.
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# The exact 16 fields from cart/vkusvill_api.py::VkusVillCart.add() —
# keep this in sync with the dict literal there. Ordering matches the
# source-code order so per-field reports are easier to cross-reference.
PAYLOAD_FIELDS: tuple[str, ...] = (
    "id",
    "xmlid",
    "max",
    "delivery_no_set",
    "koef",
    "step",
    "coupon",
    "isExperiment",
    "isOnlyOnline",
    "isGreen",
    "user_id",
    "skip_analogs",
    "is_app",
    "is_default_button",
    "cssInited",
    "price_type",
)

DROPPABLE_SUCCESS_THRESHOLD = 0.95


def _parse_args(argv):
    p = argparse.ArgumentParser(
        description="Ablation harness for VkusVill basket_add.php payload",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    p.add_argument("--user-id", required=True, help="VkusVill user_id to run ablation for")
    p.add_argument("--product-id", required=True, type=int, help="product_id to add/remove repeatedly")
    p.add_argument(
        "--n-per-field",
        type=int,
        default=20,
        help="Number of add+remove cycles per ablated field (and for baseline)",
    )
    p.add_argument(
        "--output",
        default="",
        help="Write JSON results here (if empty, print to stdout)",
    )
    p.add_argument(
        "--cookies-path",
        default="data/browser_cookies_live.json",
        help="VkusVill cookies.json path (ignored in --dry-run)",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Skip network; validate payload shape + CLI wiring only (safe for CI)",
    )
    return p.parse_args(argv)


def _build_payload(*, product_id, user_id, sessid, is_green=0, price_type=1):
    """Mirror the exact dict literal from VkusVillCart.add()."""
    return {
        "id": product_id,
        "xmlid": product_id,
        "max": 1,
        "delivery_no_set": "N",
        "koef": 1,
        "step": 1,
        "coupon": "",
        "isExperiment": "N",
        "isOnlyOnline": "",
        "isGreen": is_green,
        "user_id": user_id,
        "skip_analogs": "",
        "is_app": "",
        "is_default_button": "Y",
        "cssInited": "N",
        "price_type": price_type,
        # sessid is appended separately by VkusVillCart.add(); it's not
        # part of the 16 ablated fields.
        "sessid": sessid,
    }


def _measure_one(cart_client, *, product_id, drop_field):
    """Issue one add (+ cleanup remove) with an optionally-dropped field.

    Returns (success_bool, elapsed_ms). Exceptions are caught and counted
    as failures so one network hiccup doesn't abort the sweep. Live-mode
    only.
    """
    from cart import vkusvill_api as vv

    payload = _build_payload(
        product_id=product_id,
        user_id=cart_client.user_id,
        sessid=cart_client.sessid,
    )
    if drop_field is not None:
        payload.pop(drop_field, None)

    t0 = time.perf_counter()
    try:
        resp = cart_client._request(vv.BASKET_ADD_URL, payload)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        success_val = resp.get("success") if isinstance(resp, dict) else None
        ok = str(success_val).upper() in ("Y", "TRUE", "1")
    except Exception:
        elapsed_ms = (time.perf_counter() - t0) * 1000
        ok = False

    # Best-effort cleanup so we don't leave phantom items in the
    # operator's test cart. basket_key convention is "<product_id>_0".
    try:
        cart_client.remove(product_id=product_id, basket_key=f"{product_id}_0")
    except Exception:
        pass

    return ok, elapsed_ms


def _summarize(samples):
    n = len(samples)
    if n == 0:
        return {"n": 0, "success_rate": 0.0, "p50_ms": 0.0, "p95_ms": 0.0}
    successes = sum(1 for ok, _ in samples if ok)
    latencies = sorted(ms for _, ms in samples)
    p50 = statistics.median(latencies)
    if n >= 20:
        p95 = statistics.quantiles(latencies, n=20)[18]  # 95th percentile
    else:
        idx = max(0, int(round(0.95 * (n - 1))))
        p95 = latencies[idx]
    return {
        "n": n,
        "success_rate": round(successes / n, 4),
        "p50_ms": round(p50, 2),
        "p95_ms": round(p95, 2),
    }


def _classify(baseline, per_field):
    droppable = []
    required = []
    for field, stats in per_field.items():
        if stats["success_rate"] >= DROPPABLE_SUCCESS_THRESHOLD:
            droppable.append(field)
        else:
            required.append(field)
    return {"droppable": droppable, "required": required}


def _run_dry(args):
    """Validate payload shape + produce synthetic results — no network."""
    ref = _build_payload(
        product_id=args.product_id,
        user_id=args.user_id,
        sessid="DRY_RUN_SESSID",
    )
    declared = set(PAYLOAD_FIELDS)
    in_payload = set(ref.keys()) - {"sessid"}
    missing = declared - in_payload
    extra = in_payload - declared
    assert not missing, f"Dry-run: PAYLOAD_FIELDS missing from _build_payload: {sorted(missing)}"
    assert not extra, f"Dry-run: _build_payload has undeclared fields: {sorted(extra)}"

    baseline = {
        "n": args.n_per_field,
        "success_rate": 1.0,
        "p50_ms": 3600.0,
        "p95_ms": 4800.0,
    }
    per_field = {
        field: {
            "n": args.n_per_field,
            "success_rate": 1.0,
            "p50_ms": 3600.0,
            "p95_ms": 4800.0,
        }
        for field in PAYLOAD_FIELDS
    }
    verdict = _classify(baseline, per_field)
    return {
        "mode": "dry_run",
        "note": "Synthetic output. No VkusVill calls were made.",
        "product_id": args.product_id,
        "user_id": args.user_id,
        "fields_ablated": list(PAYLOAD_FIELDS),
        "baseline": baseline,
        "per_field": per_field,
        "verdict": verdict,
    }


def _run_live(args):
    """Authenticated live sweep — only runs when --dry-run is absent."""
    from cart.vkusvill_api import VkusVillCart  # lazy so dry-run is CI-safe

    cart = VkusVillCart(cookies_path=args.cookies_path)
    cart._ensure_session()
    if not cart.sessid or not cart.user_id:
        raise SystemExit(
            "Ablation aborted: cookies file has no sessid/user_id. "
            "Re-login and re-export cookies, then retry."
        )

    baseline_samples = []
    for _ in range(args.n_per_field):
        baseline_samples.append(_measure_one(cart, product_id=args.product_id, drop_field=None))
    baseline = _summarize(baseline_samples)

    per_field = {}
    for field in PAYLOAD_FIELDS:
        samples = []
        for _ in range(args.n_per_field):
            samples.append(_measure_one(cart, product_id=args.product_id, drop_field=field))
        per_field[field] = _summarize(samples)

    verdict = _classify(baseline, per_field)
    return {
        "mode": "live",
        "product_id": args.product_id,
        "user_id": args.user_id,
        "fields_ablated": list(PAYLOAD_FIELDS),
        "baseline": baseline,
        "per_field": per_field,
        "verdict": verdict,
    }


def main(argv=None):
    args = _parse_args(argv)
    results = _run_dry(args) if args.dry_run else _run_live(args)

    blob = json.dumps(results, indent=2, ensure_ascii=False)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(blob, encoding="utf-8")
        print(f"Wrote {args.output}")
    else:
        print(blob)
    return 0


if __name__ == "__main__":
    sys.exit(main())
