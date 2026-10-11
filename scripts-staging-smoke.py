#!/usr/bin/env python3
"""Non-destructive smoke checks for a deployed staging web/API origin."""
import argparse
import sys
import urllib.error
import urllib.request


def get(url: str, timeout: float = 5.0):
    request = urllib.request.Request(url, headers={"User-Agent": "fitness-staging-smoke/1.0"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = response.read().decode("utf-8", errors="replace")
        return response.status, {key.lower(): value for key, value in response.headers.items()}, body


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("base_url", help="Origin, e.g. https://staging.example.com")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")
    checks = [
        ("web root", f"{base}/", lambda status, headers, body: status == 200 and "<html" in body.lower()),
        ("API liveness", f"{base}/api/health", lambda status, headers, body: status == 200 and '"status":"ok"' in body.replace(" ", "")),
        ("API/database readiness", f"{base}/api/health/ready", lambda status, headers, body: status == 200 and '"status":"ready"' in body.replace(" ", "")),
        ("OpenAPI docs proxy", f"{base}/openapi.json", lambda status, headers, body: status == 200 and '"openapi"' in body),
    ]
    failed = 0
    for label, url, predicate in checks:
        try:
            status, headers, body = get(url)
            ok = predicate(status, headers, body)
            print(f"{'PASS' if ok else 'FAIL'} {label} (HTTP {status})")
            if label == "web root":
                for header in ("x-content-type-options", "x-frame-options", "referrer-policy"):
                    if header not in headers:
                        print(f"WARN missing security header: {header}")
            if not ok:
                failed += 1
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            print(f"FAIL {label}: {exc}")
            failed += 1
    print(f"Result: {len(checks) - failed}/{len(checks)} smoke checks passed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
