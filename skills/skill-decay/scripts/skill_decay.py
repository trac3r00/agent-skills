#!/usr/bin/env python3
"""skill-decay — measure which declared capabilities are never actually used.

An agent (or any plugin host) declares an inventory of skills/tools/plugins.
Each one is loaded, described, and paid for in the prompt on every turn — but
nobody proves it earns its keep. This tool cross-references a *declared*
inventory against a *usage log* and reports the dead weight: capabilities that
loaded but were invoked zero times, or haven't been touched in N days.

It is deliberately source-agnostic:

  * inventory  = a directory of SKILL.md files (frontmatter `name:` or the
                 containing dir name), OR a flat --names list.
  * usage      = one or more log/transcript files (or stdin), scanned for each
                 inventory name as a whole word, with an optional ISO date per
                 line used as a last-seen timestamp.

Output is a decay report: per-item invocation count, days since last use, and a
`decay` verdict (never / stale / live). Exits non-zero when the number of decay
candidates blows a budget, so "the inventory grew faster than it's used" fails
CI instead of silently taxing every request.

Pure stdlib. Nothing is imported or executed from the inventory — SKILL.md is
read as text, logs are read as text.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Iterable, Optional

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache", "node_modules"}
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")
_FRONT_NAME = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)


@dataclass
class Item:
    name: str
    source: str  # where the declaration was found
    count: int = 0
    last_seen: Optional[date] = None
    _matcher: Optional[re.Pattern] = field(default=None, repr=False)

    def matcher(self) -> re.Pattern:
        if self._matcher is None:
            # whole-word (or path-segment) match so "plan" doesn't hit "planet".
            # hyphens/underscores are word-internal for skill names.
            esc = re.escape(self.name)
            self._matcher = re.compile(rf"(?<![\w-]){esc}(?![\w-])")
        return self._matcher


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def discover_inventory(root: Path) -> list[Item]:
    """Find SKILL.md declarations under ``root``.

    Name resolution: frontmatter ``name:`` if present, else the containing
    directory name. De-duplicated, sorted, stable.
    """
    items: dict[str, Item] = {}
    root = root.resolve()
    if not root.exists():
        return []
    for skill_file in sorted(root.rglob("SKILL.md")):
        if any(part in SKIP_DIRS for part in skill_file.parts):
            continue
        text = _read_text(skill_file)
        m = _FRONT_NAME.search(text)
        name = (m.group(1).strip() if m else skill_file.parent.name).strip()
        # strip quotes some authors wrap the name in
        name = name.strip("'\"")
        if not name:
            continue
        rel = skill_file.parent
        try:
            source = str(rel.relative_to(root))
        except ValueError:
            source = str(rel)
        items.setdefault(name, Item(name=name, source=source or "."))
    return sorted(items.values(), key=lambda i: i.name)


def inventory_from_names(names: Iterable[str]) -> list[Item]:
    items: dict[str, Item] = {}
    for raw in names:
        name = raw.strip().strip("'\"")
        if name:
            items.setdefault(name, Item(name=name, source="--names"))
    return sorted(items.values(), key=lambda i: i.name)


def _line_date(line: str) -> Optional[date]:
    m = _ISO_DATE.search(line)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def scan_usage(items: list[Item], lines: Iterable[str]) -> None:
    """Tally invocations per item across usage lines, tracking last-seen date."""
    for line in lines:
        if not line.strip():
            continue
        line_date = _line_date(line)
        for item in items:
            hits = len(item.matcher().findall(line))
            if hits:
                item.count += hits
                if line_date and (item.last_seen is None or line_date > item.last_seen):
                    item.last_seen = line_date


def _days_since(d: Optional[date], today: date) -> Optional[int]:
    if d is None:
        return None
    return (today - d).days


def classify(item: Item, today: date, stale_days: int) -> str:
    if item.count == 0:
        return "never"
    days = _days_since(item.last_seen, today)
    if days is not None and days > stale_days:
        return "stale"
    return "live"


def build_report(
    items: list[Item],
    today: date,
    stale_days: int,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    for item in items:
        verdict = classify(item, today, stale_days)
        rows.append(
            {
                "name": item.name,
                "source": item.source,
                "count": item.count,
                "last_seen": item.last_seen.isoformat() if item.last_seen else None,
                "days_since_last_use": _days_since(item.last_seen, today),
                "decay": verdict,
            }
        )
    # rank: never first, then stale, then live; within a tier least-used first
    tier = {"never": 0, "stale": 1, "live": 2}
    rows.sort(key=lambda r: (tier[str(r["decay"])], r["count"], str(r["name"])))
    never = [r for r in rows if r["decay"] == "never"]
    stale = [r for r in rows if r["decay"] == "stale"]
    live = [r for r in rows if r["decay"] == "live"]
    return {
        "inventory_size": len(items),
        "stale_days": stale_days,
        "as_of": today.isoformat(),
        "counts": {
            "never": len(never),
            "stale": len(stale),
            "live": len(live),
            "decay_candidates": len(never) + len(stale),
        },
        "items": rows,
        "never_used": [str(r["name"]) for r in never],
        "stale": [str(r["name"]) for r in stale],
    }


def report_text(report: dict[str, object]) -> str:
    out: list[str] = []
    counts = report["counts"]  # type: ignore[index]
    out.append("Skill-decay report")
    out.append("=" * 30)
    out.append(f"inventory: {report['inventory_size']}   as-of: {report['as_of']}   stale>{report['stale_days']}d")
    out.append(
        f"live: {counts['live']}   stale: {counts['stale']}   never: {counts['never']}   "  # type: ignore[index]
        f"decay-candidates: {counts['decay_candidates']}"  # type: ignore[index]
    )
    out.append("")
    name_w = max((len(str(r["name"])) for r in report["items"]), default=8) + 2  # type: ignore[index]
    out.append(f"{'name':<{name_w}}{'calls':>7}  {'last-use':<12} decay")
    out.append("-" * (name_w + 34))
    for r in report["items"]:  # type: ignore[index]
        last = str(r["last_seen"]) if r["last_seen"] else "-"
        ago = f" ({r['days_since_last_use']}d)" if r["days_since_last_use"] is not None else ""
        out.append(f"{str(r['name']):<{name_w}}{r['count']:>7}  {last:<12}{r['decay']}{ago}")
    return "\n".join(out)


def run(
    items: list[Item],
    usage_lines: Iterable[str],
    stale_days: int,
    today: date,
) -> dict[str, object]:
    scan_usage(items, usage_lines)
    return build_report(items, today, stale_days)


def _iter_usage_lines(log_paths: list[str], read_stdin: bool) -> Iterable[str]:
    for p in log_paths:
        path = Path(p).expanduser()
        if path.is_dir():
            for f in sorted(path.rglob("*")):
                if f.is_file() and not any(part in SKIP_DIRS for part in f.parts):
                    yield from _read_text(f).splitlines()
        elif path.exists():
            yield from _read_text(path).splitlines()
    if read_stdin:
        data = sys.stdin.read()
        if data:
            yield from data.splitlines()


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(
        description="Find declared-but-unused skills/tools by cross-referencing an inventory against usage logs.",
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--skills-dir", help="directory of SKILL.md files to treat as the inventory")
    src.add_argument("--names", help="comma-separated inventory names (when you don't have SKILL.md files)")
    ap.add_argument(
        "--logs",
        action="append",
        default=[],
        help="usage log/transcript file or directory (repeatable). Omit to read usage from stdin.",
    )
    ap.add_argument("--stdin", action="store_true", help="also read usage lines from stdin")
    ap.add_argument("--stale-days", type=int, default=30, help="an item unused for more than this many days is 'stale'")
    ap.add_argument("--max-decay", type=int, default=-1, help="fail if decay-candidates (never+stale) exceed this (-1 = no gate)")
    ap.add_argument("--fail-on-never", action="store_true", help="fail if any item was never used")
    ap.add_argument("--as-of", help="reference date YYYY-MM-DD for staleness (default: today)")
    ap.add_argument("--json", action="store_true", help="emit JSON report")
    args = ap.parse_args(argv)

    if args.skills_dir:
        root = Path(args.skills_dir).expanduser()
        if not root.exists():
            print(f"error: skills dir not found: {root}", file=sys.stderr)
            return 2
        items = discover_inventory(root)
    else:
        items = inventory_from_names(args.names.split(","))

    if not items:
        print("error: empty inventory (no SKILL.md found / no names given)", file=sys.stderr)
        return 2

    today = date.today()
    if args.as_of:
        try:
            today = datetime.strptime(args.as_of, "%Y-%m-%d").date()
        except ValueError:
            print(f"error: bad --as-of date: {args.as_of}", file=sys.stderr)
            return 2

    read_stdin = args.stdin or not args.logs
    usage_lines = list(_iter_usage_lines(args.logs, read_stdin))

    report = run(items, usage_lines, args.stale_days, today)

    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(report_text(report))

    counts = report["counts"]  # type: ignore[index]
    decay_candidates = int(counts["decay_candidates"])  # type: ignore[index]
    never = int(counts["never"])  # type: ignore[index]
    failed = False
    if args.max_decay >= 0 and decay_candidates > args.max_decay:
        if not args.json:
            print(f"FAIL: decay_candidates {decay_candidates} > max_decay {args.max_decay}")
        failed = True
    if args.fail_on_never and never > 0:
        if not args.json:
            print(f"FAIL: {never} skill(s) never used: {', '.join(report['never_used'])}")  # type: ignore[index]
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
