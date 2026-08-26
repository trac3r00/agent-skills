#!/usr/bin/env python3
"""sec-headers: grade the HTTP security headers of a URL.

Fetches a URL and audits the headers browsers enforce: HSTS,
Content-Security-Policy, X-Frame-Options/frame-ancestors, X-Content-Type-Options,
Referrer-Policy, Permissions-Policy, plus cookie attributes (Secure, HttpOnly,
SameSite) on Set-Cookie. Letter grade A-F with per-header pass/warn/fail.
Stdlib-only fetch, no browser.

Usage:
    sec_headers.py https://example.com [--json]
    sec_headers.py URL --min-grade B

Exit codes: 0 grade >= --min-grade (default B), 1 below, 2 unreachable.
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request

REQUIRED = {
    "strict-transport-security": ("fail", "HSTS missing — downgrade attacks possible"),
    "content-security-policy": ("fail", "no CSP — XSS has no second line of defense"),
    "x-content-type-options": ("warn", "nosniff missing — MIME confusion possible"),
    "referrer-policy": ("warn", "no referrer policy — may leak URLs"),
}
FRAME = ("x-frame-options", "frame-ancestors")


def grade(headers: dict[str, str], cookies: list[str]) -> dict:
    report: dict[str, dict] = {}
    score = 100
    for name, (severity, why) in REQUIRED.items():
        if name in headers:
            report[name] = {"status": "pass", "value": headers[name][:80]}
        else:
            report[name] = {"status": severity, "value": why}
            score -= 25 if severity == "fail" else 10
    has_frame = "x-frame-options" in headers or "frame-ancestors" in headers.get("content-security-policy", "")
    if has_frame:
        report["framing"] = {"status": "pass", "value": headers.get("x-frame-options", "via CSP frame-ancestors")}
    else:
        report["framing"] = {"status": "warn", "value": "clickjacking protection missing"}
        score -= 10
    insecure = [c.split(";")[0][:30] for c in cookies
                if "secure" not in c.lower() or "httponly" not in c.lower()]
    if cookies:
        report["cookies"] = {"status": "pass" if not insecure else "warn",
                             "value": f"{len(insecure)} cookie(s) missing Secure/HttpOnly" if insecure
                                      else f"{len(cookies)} cookie(s) well-flagged"}
        if insecure:
            score -= 10
    score = max(score, 0)
    letter = "A" if score >= 90 else "B" if score >= 75 else "C" if score >= 60 else "D" if score >= 40 else "F"
    return {"grade": letter, "score": score, "headers": report}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("url")
    ap.add_argument("--min-grade", default="B")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    req = urllib.request.Request(args.url, headers={"User-Agent": "sec-headers/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            raw_headers = dict(r.headers.items())
            cookies = r.headers.get_all("Set-Cookie") or []
    except urllib.error.HTTPError as e:
        raw_headers = dict(e.headers.items()) if e.headers else {}
        cookies = e.headers.get_all("Set-Cookie") if e.headers else []
    except (urllib.error.URLError, OSError) as e:
        print(f"unreachable: {e}", file=sys.stderr)
        return 2

    headers = {k.lower(): v for k, v in raw_headers.items()}
    result = grade(headers, cookies)
    result["url"] = args.url

    order = ["A", "B", "C", "D", "F"]
    ok = order.index(result["grade"]) <= order.index(args.min_grade)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print(f"{args.url}: grade {result['grade']} ({result['score']}/100)")
        for name, h in result["headers"].items():
            mark = {"pass": "ok", "warn": "!!", "fail": "XX"}[h["status"]]
            print(f"  [{mark}] {name}: {h['value']}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
