#!/usr/bin/env python3
"""cron-audit: parse a crontab, explain every schedule, flag what is broken.

Crontab lines are write-only for most humans. This parses them, expands each
field into concrete values (minute=0, hour=2, weekdays=[1..5]), explains the
schedule in plain words, and flags invalid lines, impossible schedules
(minute>59, day>31), and suspiciously frequent jobs. Stdlib-only.

Usage:
    cron_audit.py crontab.txt [--json]
    crontab -l | cron_audit.py -
    cron_audit.py crontab.txt --max-freq-min 5   # flag jobs more frequent than 5min

Exit codes: 0 all valid, 1 invalid lines found, 2 input error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

FIELDS = ["minute", "hour", "day", "month", "weekday"]
RANGES = {"minute": (0, 59), "hour": (0, 23), "day": (1, 31),
          "month": (1, 12), "weekday": (0, 7)}
NAMES = {"minute": "minute", "hour": "hour", "day": "day of month",
         "month": "month", "weekday": "weekday"}


def parse_field(spec: str, field: str) -> tuple[list[int] | str, str | None]:
    lo, hi = RANGES[field]
    if spec == "*":
        return "*", None
    out: set[int] = set()
    for part in spec.split(","):
        m = re.fullmatch(r"\*/(\d+)", part)
        if m:
            step = int(m.group(1))
            if step < 1:
                return [], f"bad step in {field}: {part}"
            out.update(range(lo, hi + 1, step))
            continue
        m = re.fullmatch(r"(\d+)-(\d+)(?:/(\d+))?", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            step = int(m.group(3)) if m.group(3) else 1
            if a > b or a < lo or b > hi:
                return [], f"range {part} outside {field} {lo}-{hi}"
            out.update(range(a, b + 1, step))
            continue
        if part.isdigit():
            v = int(part)
            if v < lo or v > hi:
                return [], f"value {part} outside {field} {lo}-{hi}"
            out.add(v)
            continue
        return [], f"unparseable {field} field: {part}"
    return sorted(out), None


def explain(vals: list[int] | str, field: str) -> str:
    if vals == "*":
        return f"every {NAMES[field]}"
    if len(vals) > 4:
        return f"{NAMES[field]}s {vals[0]}-{vals[-1]} ({len(vals)} values)"
    return f"{NAMES[field]} {vals}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("crontab", help="file path or - for stdin")
    ap.add_argument("--max-freq-min", type=int, default=None)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    text = sys.stdin.read() if args.crontab == "-" else (
        Path(args.crontab).read_text(errors="replace")
        if Path(args.crontab).is_file() else None)
    if text is None:
        print(f"missing: {args.crontab}", file=sys.stderr)
        return 2

    entries, invalid, frequent = [], 0, []
    for i, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 5)
        if len(parts) < 6:
            invalid += 1
            entries.append({"line": i, "raw": line, "valid": False,
                            "error": "need 5 schedule fields + command"})
            continue
        schedule: dict = {}
        errors = []
        for spec, field in zip(parts[:5], FIELDS):
            vals, err = parse_field(spec, field)
            if err:
                errors.append(err)
            schedule[field] = vals
        if errors:
            invalid += 1
            entries.append({"line": i, "raw": line, "valid": False,
                            "error": "; ".join(errors)})
            continue
        if schedule["minute"] != "*" and schedule["hour"] == "*" and args.max_freq_min:
            mins = [m for m in schedule["minute"]]
            if len(mins) * 24 > (24 * 60) // args.max_freq_min:
                frequent.append(i)
        entries.append({
            "line": i, "valid": True, "command": parts[5],
            "schedule": schedule,
            "explain": ", ".join(explain(schedule[f], f) for f in FIELDS),
        })

    jobs = sum(1 for e in entries if e.get("valid"))
    report = {"jobs": jobs, "invalid": invalid, "entries": entries}
    if frequent:
        report["frequent_lines"] = frequent
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for e in entries:
            if e.get("valid"):
                print(f"  line {e['line']}: {e['explain']}")
                print(f"           -> {e['command'][:60]}")
            else:
                print(f"X line {e['line']}: {e['error']}")
        print(f"\n{jobs} valid job(s), {invalid} invalid line(s)")
    return 1 if invalid else 0


if __name__ == "__main__":
    raise SystemExit(main())
