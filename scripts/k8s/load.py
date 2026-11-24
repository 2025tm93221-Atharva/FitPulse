#!/usr/bin/env python3
"""Continuous GETs against a URL; reports status and version counts (stdlib only)."""
import argparse
import collections
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

parser = argparse.ArgumentParser()
parser.add_argument("url")
parser.add_argument("--seconds", type=float, default=30)
parser.add_argument("--workers", type=int, default=4)
parser.add_argument("--header", action="append", default=[], help='e.g. "X-Canary: always"')
args = parser.parse_args()
headers = {k.strip(): v.strip() for k, _, v in (h.partition(":") for h in args.header)}
deadline = time.monotonic() + args.seconds


def worker(_: int) -> collections.Counter:
    seen: collections.Counter = collections.Counter()
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(urllib.request.Request(args.url, headers=headers), timeout=5) as r:
                seen[(r.status, r.headers.get("X-App-Version"), r.headers.get("X-Deploy-Track"))] += 1
        except urllib.error.HTTPError as exc:
            seen[(exc.code, exc.headers.get("X-App-Version"), exc.headers.get("X-Deploy-Track"))] += 1
        except OSError as exc:
            seen[("FAILED", type(exc).__name__, str(exc))] += 1
        time.sleep(0.02)
    return seen


with ThreadPoolExecutor(args.workers) as pool:
    total = sum(pool.map(worker, range(args.workers)), collections.Counter())
count = sum(total.values())
bad = sum(n for key, n in total.items() if key[0] != 200)
for key, n in sorted(total.items(), key=str):
    print(f"{n:6d} ({n / count:6.1%}) status={key[0]} version={key[1]} track={key[2]}")
print(f"total={count} failed={bad}")
raise SystemExit(1 if bad else 0)
