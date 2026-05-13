#!/usr/bin/env python3
"""Count event kinds in data/proxy_events.jsonl for admin-endpoint design."""
import json
from collections import Counter
from pathlib import Path

c = Counter()
path = Path("/home/ubuntu/saleapp/data/proxy_events.jsonl")
with path.open() as f:
    for line in f:
        try:
            c[json.loads(line).get("event", "?")] += 1
        except Exception:
            c["?PARSE_ERROR"] += 1

for event, count in c.most_common(30):
    print(f"{count:7d}  {event}")
