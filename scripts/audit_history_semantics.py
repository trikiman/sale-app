"""Triple-check v1.14's history-semantics fix against live production data.

Asks the live API for the most-frequent products and, for each, fetches the
full session timeline. Then scans for suspicious patterns:

1. Same-day sessions separated by < 60 min (v1.14's SESSION_GAP_MINUTES was
   supposed to merge these into one session)
2. Sessions with duration_minutes (== window) == 0 or < 5 min (orphan appearances)
3. More than N sessions on a single calendar day (high density may be real
   for price-cycling products, or may be residual fragmentation from v1.14)

Session shape from the live API:
    date_raw: "2026-04-11"
    time: "14:12"   (HH:MM, MSK-assumed)
    window: "109м" or "12447м" (minutes, Russian \"м\" suffix)
    type, discount, price, old_price, is_active

Usage:
    python scripts/audit_history_semantics.py [--top N] [--target-date YYYY-MM-DD]
    python scripts/audit_history_semantics.py --pid 731   # just audit banana
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlencode

API_BASE = "https://vkusvillsale.vercel.app"
SESSION_GAP_MINUTES = 60  # Must match database/sale_history.py

_WINDOW_NUM = re.compile(r"(\d+)")


def fetch_json(path: str, params: dict | None = None) -> dict:
    qs = f"?{urlencode(params)}" if params else ""
    url = f"{API_BASE}{path}{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "history-audit/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def parse_window_min(s: str | None) -> int:
    """Parse `window` string like '109м' or '12447м' into an int minute count."""
    if not s:
        return 0
    m = _WINDOW_NUM.search(str(s))
    return int(m.group(1)) if m else 0


def session_start_end(s: dict) -> tuple[datetime, datetime] | None:
    """Compute (first_seen, last_seen) as datetimes from the API session shape."""
    date_raw = s.get("date_raw")
    time_str = s.get("time") or "00:00"
    if not date_raw:
        return None
    try:
        first = datetime.fromisoformat(f"{date_raw}T{time_str}:00")
    except ValueError:
        return None
    dur = parse_window_min(s.get("window"))
    last = first + timedelta(minutes=dur)
    return first, last


def analyze_product(pid: str, name: str, target_date: str | None = None) -> dict:
    try:
        detail = fetch_json(f"/api/history/product/{pid}")
    except Exception as e:
        return {"error": str(e)}

    sessions = detail.get("sessions") or []
    if not sessions:
        return {"error": "no sessions returned"}

    # Normalize + sort ascending by first_seen
    parsed = []
    for s in sessions:
        se = session_start_end(s)
        if not se:
            continue
        first, last = se
        parsed.append({
            "first": first,
            "last": last,
            "duration_min": parse_window_min(s.get("window")),
            "type": s.get("type"),
            "price": s.get("price"),
            "old_price": s.get("old_price"),
            "discount": s.get("discount"),
            "is_active": s.get("is_active"),
            "date_raw": s.get("date_raw"),
            "time": s.get("time"),
            "window_raw": s.get("window"),
        })
    parsed.sort(key=lambda x: x["first"])

    by_day: dict[str, list[dict]] = defaultdict(list)
    zero_dur = 0
    sub_5min = 0
    fragments = []

    for i, s in enumerate(parsed):
        by_day[s["first"].date().isoformat()].append(s)
        if s["duration_min"] == 0:
            zero_dur += 1
        elif s["duration_min"] < 5:
            sub_5min += 1
        if i > 0:
            prev = parsed[i - 1]
            gap = (s["first"] - prev["last"]).total_seconds() / 60
            # Gap between sessions that v1.14 would have merged (within 60min)
            # but ONLY suspicious if gap is short AND positive (real break)
            if 0 < gap < SESSION_GAP_MINUTES:
                fragments.append({
                    "gap_min": round(gap, 1),
                    "prev_end": prev["last"].isoformat(),
                    "curr_start": s["first"].isoformat(),
                    "prev_type": prev["type"],
                    "curr_type": s["type"],
                    "same_type": prev["type"] == s["type"],
                })

    same_day_multi = {d: len(ss) for d, ss in by_day.items() if len(ss) > 1}

    total_dur = sum(x["duration_min"] for x in parsed if x["duration_min"] > 0)
    dur_count = sum(1 for x in parsed if x["duration_min"] > 0)

    target_detail = None
    if target_date and target_date in by_day:
        target_detail = [
            {
                "start": s["first"].strftime("%H:%M"),
                "end": s["last"].strftime("%H:%M (%d %b)"),
                "duration_min": s["duration_min"],
                "type": s["type"],
                "price": s["price"],
                "old_price": s["old_price"],
            }
            for s in by_day[target_date]
        ]

    return {
        "pid": pid,
        "name": name,
        "sessions": parsed,
        "total_sessions": len(parsed),
        "days_on_sale": len(by_day),
        "avg_duration_min": round(total_dur / dur_count, 1) if dur_count else 0,
        "zero_duration": zero_dur,
        "sub_5min_duration": sub_5min,
        "suspicious_fragments": fragments,
        "same_day_multi_session": same_day_multi,
        "target_day": target_detail,
    }


def print_product_report(r: dict, target_date: str | None) -> None:
    if "error" in r:
        print(f"   [ERROR] {r['error']}")
        return
    print(f"   sessions={r['total_sessions']}  "
          f"days_on_sale={r['days_on_sale']}  "
          f"avg_duration_min={r['avg_duration_min']}")

    if r["zero_duration"]:
        print(f"   !! {r['zero_duration']} sessions with duration=0m (orphan/fake appearances)")
    if r["sub_5min_duration"]:
        print(f"   !! {r['sub_5min_duration']} sessions with 0 < duration < 5m (suspiciously short)")

    frags = r["suspicious_fragments"]
    if frags:
        same_type = sum(1 for f in frags if f["same_type"])
        print(f"   !! {len(frags)} session pair(s) < {SESSION_GAP_MINUTES}m apart "
              f"(v1.14 should have merged — {same_type} with same sale_type):")
        for f in frags[:5]:
            mark = "[SAME-TYPE FRAGMENT]" if f["same_type"] else "[diff-type transition, probably fine]"
            print(f"      gap={f['gap_min']:>5}m  "
                  f"{f['prev_end']} ({f['prev_type']}) -> {f['curr_start']} ({f['curr_type']})  {mark}")
        if len(frags) > 5:
            print(f"      ...and {len(frags) - 5} more")

    multi = r["same_day_multi_session"]
    if multi:
        hot = sorted(multi.items(), key=lambda kv: -kv[1])[:5]
        print(f"   i  days with >1 session:")
        for day, n in hot:
            print(f"      {day}: {n} sessions"
                  + ("  <<< >=3 warrants a look" if n >= 3 else ""))

    if r.get("target_day"):
        print(f"\n   === TARGET DATE {target_date} — all sessions ===")
        for i, s in enumerate(r["target_day"], 1):
            print(f"      #{i}  {s['start']} -> {s['end']}  "
                  f"dur={s['duration_min']}m  {s['type']}  "
                  f"{s['price']}/{s['old_price']}")
        if len(r["target_day"]) >= 3:
            print(f"   >>> user concern: {len(r['target_day'])} sessions on {target_date}")
            print(f"   >>> legit only if product truly left+returned to sale that many times")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--target-date", default=None, help="YYYY-MM-DD to zoom into")
    ap.add_argument("--pid", default=None, help="Audit just this product id, skip top-N listing")
    args = ap.parse_args()

    if args.pid:
        # Single-product mode
        print(f"Auditing product {args.pid} from {API_BASE}")
        r = analyze_product(args.pid, name=f"pid={args.pid}", target_date=args.target_date)
        print(f"\n-- {args.pid}  (target-date: {args.target_date or 'n/a'})")
        print_product_report(r, args.target_date)
        return 0

    print(f"Fetching top-{args.top} most-frequent products from {API_BASE} ...")
    listing = fetch_json("/api/history/products", {
        "sort": "most_frequent",
        "per_page": args.top,
    })
    products = listing.get("products", [])
    if not products:
        print("API returned no products", file=sys.stderr)
        return 1

    print(f"\nTop {len(products)} products by total_sale_count:")
    print(f"{'count':<6} {'pid':<8} {'name'}")
    for p in products:
        print(f"{p.get('total_sale_count', 0):<6} {p['id']:<8} {p.get('name','?')[:70]}")

    print(f"\n{'=' * 100}")
    print("PER-PRODUCT SESSION AUDIT")
    print(f"{'=' * 100}")

    total_same_type_fragments = 0
    total_multi_day_hot = 0
    for p in products:
        pid = p["id"]
        name = p.get("name", "?")
        print(f"\n-- {pid}  {name[:80]}")
        r = analyze_product(pid, name, target_date=args.target_date)
        print_product_report(r, args.target_date)
        if "suspicious_fragments" in r:
            total_same_type_fragments += sum(
                1 for f in r["suspicious_fragments"] if f["same_type"]
            )
        if "same_day_multi_session" in r:
            total_multi_day_hot += sum(
                1 for n in r["same_day_multi_session"].values() if n >= 3
            )

    print(f"\n{'=' * 100}")
    print("VERDICT")
    print(f"{'=' * 100}")
    if total_same_type_fragments == 0:
        print("OK: No same-type session fragments under 60min detected in audited products.")
        print("    v1.14's session-gap merging is holding for these cases.")
    else:
        print(f"WARN: {total_same_type_fragments} same-type session pair(s) < 60min apart.")
        print("      These are likely v1.14 regressions (should be ONE session, not two).")
    if total_multi_day_hot:
        print(f"INFO: {total_multi_day_hot} (product, day) pair(s) show >= 3 sessions.")
        print("      Use --target-date to inspect — legitimate only if product truly")
        print("      left+returned to sale that many times in one day.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
