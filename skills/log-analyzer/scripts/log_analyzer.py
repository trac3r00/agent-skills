#!/usr/bin/env python3
"""log-analyzer: group a log file's errors by pattern and rank the offenders.

A 50,000-line log is not a report. This normalizes volatile tokens (numbers,
IDs, timestamps, paths) out of ERROR/WARN lines, groups near-identical
messages into patterns, and ranks them by frequency — so "connection refused
to db-01:5432" and "connection refused to db-99:5432" count as ONE problem
seen 47 times, not 47 problems. Offline, stdlib-only, deterministic.

Usage:
    log_analyzer.py app.log [--json]
    log_analyzer.py app.log --level ERROR --top 10
    log_analyzer.py app.log --max-patterns 5   # exit 1 when more patterns
    log_analyzer.py app.log --budget-errors 0  # CI gate: fail on any error

Exit codes: 0 within budgets, 1 over budget, 2 input error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

LEVEL_RE = re.compile(r"\b(TRACE|DEBUG|INFO|WARN(?:ING)?|ERROR|FATAL|CRITICAL)\b")
EXCEPTION_RE = re.compile(r"(\w*(?:Error|Exception|Failure)|\bFAILED\b|\bTraceback\b)")
WARN_RE = re.compile(r"\bwarn(?:ing)?\b", re.I)
VOLATILE = [
    (re.compile(r"\b\d{4}[-/]\d{2}[-/]\d{2}[T ]\d{2}:\d{2}(:\d{2})?(\.\d+)?(Z|[+-]\d{2}:?\d{2})?\b"), "<ts>"),
    (re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.I), "<uuid>"),
    (re.compile(r"\b0x[0-9a-f]+\b", re.I), "<hex>"),
    (re.compile(r"\b\d+\.\d+\.\d+\.\d+(:\d+)?\b"), "<ip>"),
    (re.compile(r"(/[\w.\-]+)+"), "<path>"),
    (re.compile(r"\b[\w.-]+:\d{2,5}\b"), "<host:port>"),
    (re.compile(r"\b\d+\b"), "<n>"),
]


def normalize(message: str) -> str:
    for rx, token in VOLATILE:
        message = rx.sub(token, message)
    return re.sub(r"\s+", " ", message).strip()[:120]


def analyze(path: Path, level: str, top: int) -> dict:
    lines = path.read_text(errors="replace").splitlines()
    errors = warnings = 0
    patterns: Counter[str] = Counter()
    examples: dict[str, str] = {}
    want_levels = {level} if level else {"ERROR", "FATAL", "CRITICAL", "WARN", "WARNING"}
    for ln in lines:
        m = LEVEL_RE.search(ln)
        if m:
            lvl = "WARN" if m.group(1) in ("WARN", "WARNING") else m.group(1)
        elif EXCEPTION_RE.search(ln):
            lvl = "ERROR"
        elif WARN_RE.search(ln):
            lvl = "WARN"
        else:
            continue
        if lvl in ("ERROR", "FATAL", "CRITICAL"):
            if lvl in want_levels or not level:
                errors += 1
                pat = normalize(ln)
                patterns[pat] += 1
                examples.setdefault(pat, ln.strip()[:160])
        elif lvl == "WARN" and lvl in want_levels:
            warnings += 1
            if not level or level == "WARN":
                pat = normalize(ln)
                patterns[pat] += 1
                examples.setdefault(pat, ln.strip()[:160])
    ranked = [{"pattern": p, "count": c, "example": examples[p]}
              for p, c in patterns.most_common(top)]
    return {
        "file": str(path), "total_lines": len(lines),
        "errors": errors, "warnings": warnings,
        "distinct_patterns": len(patterns), "patterns": ranked,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("logfile")
    ap.add_argument("--level", choices=["ERROR", "WARN", "FATAL", "CRITICAL"], default="")
    ap.add_argument("--top", type=int, default=20)
    ap.add_argument("--budget-errors", type=int, default=None, metavar="N")
    ap.add_argument("--max-patterns", type=int, default=None, metavar="N")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    p = Path(args.logfile)
    if not p.is_file():
        print(f"missing: {args.logfile}", file=sys.stderr)
        return 2
    report = analyze(p, args.level, args.top)

    over = []
    if args.budget_errors is not None and report["errors"] > args.budget_errors:
        over.append(f"errors {report['errors']} > budget {args.budget_errors}")
    if args.max_patterns is not None and report["distinct_patterns"] > args.max_patterns:
        over.append(f"patterns {report['distinct_patterns']} > max {args.max_patterns}")

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"{report['file']}: {report['total_lines']} lines, "
              f"{report['errors']} errors, {report['warnings']} warnings, "
              f"{report['distinct_patterns']} distinct patterns")
        for i, pat in enumerate(report["patterns"], 1):
            print(f"  {i:>2}. [{pat['count']:>4}x] {pat['pattern'][:90]}")
    if over:
        for o in over:
            print(f"OVER BUDGET: {o}", file=sys.stderr)
        return 1
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
