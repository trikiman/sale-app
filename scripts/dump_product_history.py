"""Dump the raw API payload for one product so we can see the session shape."""
import json
import sys
import urllib.request

pid = sys.argv[1] if len(sys.argv) > 1 else "731"
url = f"https://vkusvillsale.vercel.app/api/history/product/{pid}"
with urllib.request.urlopen(url, timeout=30) as r:
    data = json.loads(r.read())

print(f"Top-level keys: {list(data.keys())}")
print()
for k, v in data.items():
    if isinstance(v, list):
        print(f"  {k}: list[{len(v)}]")
        if v and isinstance(v[0], dict):
            print(f"    keys: {list(v[0].keys())}")
            print(f"    first item:")
            print(json.dumps(v[0], indent=6, ensure_ascii=False, default=str))
            if len(v) > 1:
                print(f"    last item:")
                print(json.dumps(v[-1], indent=6, ensure_ascii=False, default=str))
    elif isinstance(v, dict):
        print(f"  {k}: dict with keys {list(v.keys())}")
    else:
        print(f"  {k}: {v!r}"[:200])
