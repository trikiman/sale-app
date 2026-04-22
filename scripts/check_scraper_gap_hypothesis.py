"""Test the hypothesis: Were the banana's Apr 11 gaps caused by scraper downtime?

Logic:
  v1.14's SESSION_GAP_MINUTES=60 keeps sessions open when the scraper is known
  to be broken (counted_for_continuity=False). The ONLY way the user's scenario
  can happen is if the scraper reports itself as successful but specifically
  misses the product for > 60min.

Test:
  If the scraper was DOWN during banana's gaps (09:45-11:33 and 13:11-14:21
  on Apr 11), then OTHER continuously-on-sale products would ALSO show session
  boundaries aligned with those gap edges. In particular, we'd expect many
  products to have sessions that START right at 11:33 or 14:21 (scraper
  resumed and caught them).

  If banana was the only one with gaps in those windows, the scraper was
  healthy and banana genuinely went off-sale and back.

Output:
  - For each of the top-N most-frequent products, list sessions on Apr 11
  - Flag sessions that START within 10min of banana's gap-end times
  - Flag sessions that END within 10min of banana's gap-start times
  - Summary: how many products corroborate scraper-downtime vs. banana-real-absence
"""
from __future__ import annotations

import json
import re
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta
from urllib.parse import urlencode

API_BASE = "https://vkusvillsale.vercel.app"
TARGET_DATE = "2026-04-11"

# Banana's gap boundaries (from the earlier audit)
# Gaps: 09:45 -> 11:33 (108min) and 13:11 -> 14:21 (70min)
GAP_WINDOWS = [
    {"label": "gap1", "end_prev": "09:45", "start_next": "11:33"},
    {"label": "gap2", "end_prev": "13:11", "start_next": "14:21"},
]
ALIGN_TOLERANCE_MIN = 10  # consider session boundary "aligned" if within this many minutes

_WINDOW_NUM = re.compile(r"(\d+)")


def fetch_json(path: str, params: dict | None = None) -> dict:
    qs = f"?{urlencode(params)}" if params else ""
    url = f"{API_BASE}{path}{qs}"
    req = urllib.request.Request(url, headers={"User-Agent": "gap-hypothesis/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def parse_window_min(s: str | None) -> int:
    if not s:
        return 0
    m = _WINDOW_NUM.search(str(s))
    return int(m.group(1)) if m else 0


def time_diff_min(hhmm_a: str, hhmm_b: str) -> float:
    """Minutes between two HH:MM strings on the same day."""
    ha, ma = map(int, hhmm_a.split(":"))
    hb, mb = map(int, hhmm_b.split(":"))
    return abs((ha * 60 + ma) - (hb * 60 + mb))


def main():
    top_n = int(sys.argv[1]) if len(sys.argv) > 1 else 30

    listing = fetch_json("/api/history/products", {
        "sort": "most_frequent",
        "per_page": top_n,
    })
    products = listing.get("products", [])
    print(f"Fetched top-{len(products)} products, analyzing Apr 11 sessions...")

    # Per-product: get sessions on target date
    apr11_sessions = []  # list of (pid, name, sessions_on_apr11)
    for p in products:
        pid = p["id"]
        name = p.get("name", "?")
        try:
            detail = fetch_json(f"/api/history/product/{pid}")
        except Exception as e:
            print(f"  [skip {pid}] {e}")
            continue
        sessions = detail.get("sessions") or []
        apr11 = []
        for s in sessions:
            if s.get("date_raw") != TARGET_DATE:
                continue
            t = s.get("time", "00:00")
            dur = parse_window_min(s.get("window"))
            # compute end HH:MM (may cross midnight — clamp to same-day for display)
            hh, mm = map(int, t.split(":"))
            end_total = hh * 60 + mm + dur
            end_h = (end_total // 60) % 24
            end_m = end_total % 60
            apr11.append({
                "start": t,
                "end_same_day": f"{end_h:02d}:{end_m:02d}",
                "duration_min": dur,
                "type": s.get("type"),
                "crosses_midnight": end_total >= 24 * 60,
            })
        if apr11:
            apr11_sessions.append({"pid": pid, "name": name[:50], "sessions": apr11})

    print(f"\n{'=' * 100}")
    print(f"All Apr 11 sessions for top-{top_n} products:")
    print(f"{'=' * 100}\n")
    for entry in apr11_sessions:
        lines = []
        for s in entry["sessions"]:
            flag = ""
            # Check alignment with banana's gap edges
            for gw in GAP_WINDOWS:
                if time_diff_min(s["start"], gw["start_next"]) <= ALIGN_TOLERANCE_MIN:
                    flag += f" <-ALIGNED-START-{gw['label']}({gw['start_next']})"
                if time_diff_min(s["end_same_day"], gw["end_prev"]) <= ALIGN_TOLERANCE_MIN:
                    flag += f" <-ALIGNED-END-{gw['label']}({gw['end_prev']})"
            lines.append(f"    {s['start']} -> {s['end_same_day']} ({s['duration_min']}m, {s['type']}){flag}")
        print(f"{entry['pid']:<8} {entry['name']}")
        for line in lines:
            print(line)
        print()

    # Count alignment hits
    aligned_hits = 0
    aligned_hit_products = set()
    for entry in apr11_sessions:
        if entry["pid"] == "731":  # skip banana itself
            continue
        for s in entry["sessions"]:
            for gw in GAP_WINDOWS:
                if time_diff_min(s["start"], gw["start_next"]) <= ALIGN_TOLERANCE_MIN:
                    aligned_hits += 1
                    aligned_hit_products.add(entry["pid"])
                if time_diff_min(s["end_same_day"], gw["end_prev"]) <= ALIGN_TOLERANCE_MIN:
                    aligned_hits += 1
                    aligned_hit_products.add(entry["pid"])

    # KEY CHECK: Find products whose SINGLE session spans right THROUGH a
    # banana gap. If any such product exists, it proves the scraper was
    # running and seeing products during the gap — so banana was genuinely
    # absent, not a scraper artifact.
    def to_minutes(hhmm: str) -> int:
        hh, mm = map(int, hhmm.split(":"))
        return hh * 60 + mm

    through_gap_proofs = []  # (pid, name, session, which_gap)
    for entry in apr11_sessions:
        if entry["pid"] == "731":
            continue
        for s in entry["sessions"]:
            # Convert session span to minutes-of-day on Apr 11.
            # Session belongs to Apr 11 (date_raw=Apr 11), start time is Apr 11.
            # If it crosses midnight, end is on Apr 12 — so on Apr 11 it spans
            # from start to 24:00.
            start_min = to_minutes(s["start"])
            if s["crosses_midnight"]:
                end_min = 24 * 60
            else:
                end_min = start_min + s["duration_min"]

            for gw in GAP_WINDOWS:
                gap_start = to_minutes(gw["end_prev"])   # e.g. 09:45
                gap_end = to_minutes(gw["start_next"])   # e.g. 11:33
                # Session must START before gap and END after gap — covering it
                if start_min <= gap_start and end_min >= gap_end:
                    through_gap_proofs.append({
                        "pid": entry["pid"],
                        "name": entry["name"],
                        "session": s,
                        "gap_label": gw["label"],
                        "gap_window": f"{gw['end_prev']}-{gw['start_next']}",
                    })

    print(f"{'=' * 100}")
    print("VERDICT on scraper-downtime hypothesis")
    print(f"{'=' * 100}")
    print(f"Products examined (excluding banana): {len(apr11_sessions) - 1}")
    print(f"Session boundaries aligning with banana's gap edges "
          f"(within {ALIGN_TOLERANCE_MIN}min): {aligned_hits} across {len(aligned_hit_products)} products")
    print(f"Products with a SINGLE session spanning THROUGH one of banana's gaps "
          f"(= proof scraper was running): {len(through_gap_proofs)}")
    print()

    if through_gap_proofs:
        print("DECISIVE EVIDENCE that scraper was running during banana's gap(s):")
        print()
        for p in through_gap_proofs:
            s = p["session"]
            print(f"  {p['pid']:<8} {p['name']}")
            print(f"    single session {s['start']} -> {s['end_same_day']} ({s['duration_min']}m, {s['type']})")
            print(f"    covers banana's {p['gap_label']} ({p['gap_window']}) continuously")
            print(f"    => if scraper had been down, this session would have broken too. It didn't.")
            print(f"    => banana genuinely went off-sale during {p['gap_window']}")
            print()
        print("Scraper-downtime hypothesis: REJECTED for the covered gap(s).")
    else:
        print("No product has a single session covering banana's gap windows.")
        print("This doesn't definitively reject the downtime hypothesis, but also")
        print(f"doesn't support it — no product started/ended aligned with the gap edges either.")

    if aligned_hits >= 3:
        print()
        print("ALIGNMENT NOTE: multiple products DID have session starts/ends near banana's")
        print("gap edges. Worth reviewing in case of a partial scraper failure.")
        print(f"  Aligned products: {sorted(aligned_hit_products)}")


if __name__ == "__main__":
    main()
