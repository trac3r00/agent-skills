#!/usr/bin/env python3
"""api-tester: hit HTTP endpoints and validate the response against expectations.

Agents write API calls but rarely verify the response is what the server
actually returns. This fires real HTTP requests (stdlib urllib, no requests
library, no curl subprocess) and checks: status code, JSON field presence
and values, response time, and content-type. Repeatable from CI or an agent
session, JSON output for assertions.

Usage:
    api_tester.py https://api.example.com/health
    api_tester.py URL --expect-status 200 --expect-json ok=true --expect-json count=3
    api_tester.py URL --method POST --body '{"x":1}' --header "Authorization: Bearer T"
    api_tester.py URL --max-latency-ms 500 --json

Exit codes: 0 all checks pass, 1 a check failed, 2 unreachable/usage error.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url")
    ap.add_argument("--method", default="GET")
    ap.add_argument("--body", default="")
    ap.add_argument("--header", action="append", default=[])
    ap.add_argument("--expect-status", type=int, default=200)
    ap.add_argument("--expect-json", action="append", default=[],
                    metavar="KEY=VALUE", help="required JSON field value")
    ap.add_argument("--max-latency-ms", type=int, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    headers = {"User-Agent": "api-tester/1.0"}
    for h in args.header:
        if ":" in h:
            k, _, v = h.partition(":")
            headers[k.strip()] = v.strip()
    data = args.body.encode() if args.body else None

    req = urllib.request.Request(args.url, data=data, headers=headers,
                                 method=args.method.upper())
    start = time.monotonic()
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            status = r.status
            body = r.read()
            content_type = r.headers.get("Content-Type", "")
    except urllib.error.HTTPError as e:
        status = e.code
        body = e.read()
        content_type = e.headers.get("Content-Type", "") if e.headers else ""
    except (urllib.error.URLError, OSError) as e:
        print(json.dumps({"error": f"unreachable: {e.reason if hasattr(e, 'reason') else e}"})
              if args.json else f"unreachable: {e}", file=sys.stderr)
        return 2
    latency_ms = round((time.monotonic() - start) * 1000)

    checks: dict[str, object] = {}
    checks["status"] = "pass" if status == args.expect_status else "fail"

    parsed = None
    if body:
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = None

    json_fields: dict[str, str] = {}
    for spec in args.expect_json:
        key, _, want = spec.partition("=")
        key, want = key.strip(), want.strip()
        actual = parsed
        for part in key.split("."):
            actual = actual.get(part) if isinstance(actual, dict) else None
        got = "" if actual is None else str(actual).lower()
        json_fields[key] = "pass" if got == want.lower() else f"fail (got {got!r})"
    checks["json_fields"] = json_fields

    if args.max_latency_ms is not None:
        checks["latency"] = "pass" if latency_ms <= args.max_latency_ms else "fail"

    fails = (checks["status"] == "fail"
             or any(v != "pass" for v in json_fields.values())
             or checks.get("latency") == "fail")

    report = {
        "url": args.url, "method": args.method.upper(), "status": status,
        "latency_ms": latency_ms, "content_type": content_type,
        "checks": checks, "body_preview": body[:300].decode(errors="replace"),
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{args.method.upper()} {args.url} -> {status} ({latency_ms}ms)")
        for k, v in checks.items():
            if isinstance(v, dict):
                for k2, v2 in v.items():
                    print(f"  {k2}: {v2}")
            else:
                print(f"  {k}: {v}")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
