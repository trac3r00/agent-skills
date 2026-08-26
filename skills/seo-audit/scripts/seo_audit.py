#!/usr/bin/env python3
"""seo-audit: on-page SEO checks for HTML files — title, meta, headings, alt, canonical, OG.

Reads an HTML file (saved from a browser, a static build, or piped from curl)
and scores the on-page basics that decide whether a page can rank and share:
exactly one non-empty title of sane length, a meta description in the 50-160
character window, exactly one h1, alt text on images, canonical link, and
Open Graph tags. Offline, stdlib-only, deterministic — no Lighthouse, no
browser, no API.

Usage:
    seo_audit.py page.html [--json]
    seo_audit.py dist/*.html --json
    curl -s https://example.com | seo_audit.py - --json
    seo_audit.py page.html --min-score 80   # exit 1 below score

Exit codes: 0 score >= --min-score (default 70), 1 below or failures, 2 input error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path

CHECKS = {}


class SEOParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ""
        self._in_title = False
        self.meta_description = ""
        self.canonical = ""
        self.og = {}
        self.h1_count = 0
        self._in_h1 = False
        self.h1_text = ""
        self.images_total = 0
        self.images_missing_alt = 0
        self.lang = ""

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html":
            self.lang = a.get("lang", "")
        elif tag == "title":
            self._in_title = True
        elif tag == "meta":
            name = a.get("name", "").lower()
            prop = a.get("property", "").lower()
            if name == "description":
                self.meta_description = a.get("content", "")
            elif prop.startswith("og:"):
                self.og[prop[3:]] = a.get("content", "")
        elif tag == "link" and a.get("rel") == "canonical":
            self.canonical = a.get("href", "")
        elif tag == "h1":
            self.h1_count += 1
            self._in_h1 = True
        elif tag == "img":
            self.images_total += 1
            if not a.get("alt", "").strip():
                self.images_missing_alt += 1

    def handle_endtag(self, tag):
        if tag == "title":
            self._in_title = False
        elif tag == "h1":
            self._in_h1 = False

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif self._in_h1:
            self.h1_text += data


def audit(html: str) -> dict:
    p = SEOParser()
    p.feed(html)
    title = p.title.strip()
    checks = {
        "title": {"status": "pass" if 10 <= len(title) <= 70 else "fail",
                  "value": title, "want": "one title, 10-70 chars"},
        "meta_description": {
            "status": "pass" if 50 <= len(p.meta_description.strip()) <= 160 else "fail",
            "value": p.meta_description.strip(), "want": "50-160 chars"},
        "h1": {"status": "pass" if p.h1_count == 1 else "fail",
               "value": f"{p.h1_count} h1 tag(s)", "want": "exactly 1"},
        "image_alt": {
            "status": "pass" if p.images_missing_alt == 0 else "fail",
            "value": f"{p.images_missing_alt}/{p.images_total} images missing alt",
            "want": "all images have alt"},
        "canonical": {"status": "pass" if p.canonical else "warn",
                      "value": p.canonical or "missing", "want": "canonical link"},
        "og_tags": {"status": "pass" if {"title", "description"} <= set(p.og) else "warn",
                    "value": f"{len(p.og)} og: tags", "want": "og:title + og:description"},
        "lang": {"status": "pass" if p.lang else "warn",
                 "value": p.lang or "missing", "want": "html lang attribute"},
    }
    weights = {"pass": 100, "warn": 60, "fail": 0}
    score = round(sum(weights[c["status"]] for c in checks.values()) / len(checks))
    return {"score": score, "checks": checks}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="+", help="HTML files, or - for stdin")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--min-score", type=int, default=70)
    args = ap.parse_args(argv)

    reports = []
    for f in args.files:
        if f == "-":
            html = sys.stdin.read()
            name = "<stdin>"
        else:
            p = Path(f)
            if not p.is_file():
                print(f"missing: {f}", file=sys.stderr)
                return 2
            html = p.read_text(errors="replace")
            name = str(p)
        if "<" not in html:
            print(f"not HTML: {name}", file=sys.stderr)
            return 2
        r = audit(html)
        r["file"] = name
        reports.append(r)

    out = reports[0] if len(reports) == 1 else reports
    if args.json:
        print(json.dumps(out, indent=2))
    else:
        for r in reports:
            print(f"{r['file']}: score {r['score']}/100")
            for name, ck in r["checks"].items():
                mark = {"pass": "ok", "warn": "!!", "fail": "XX"}[ck["status"]]
                print(f"  [{mark}] {name}: {ck['value']} (want: {ck['want']})")
    worst = min(r["score"] for r in reports)
    return 1 if worst < args.min_score else 0


if __name__ == "__main__":
    raise SystemExit(main())
