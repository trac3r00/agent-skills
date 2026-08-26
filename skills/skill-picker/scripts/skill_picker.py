#!/usr/bin/env python3
"""skill-picker: find the right skills for your workload from the catalogue.

Queries catalogue.json (generated from the actual skills/ directory) by
persona, family, keyword, or tag, and outputs matching skills with their
install paths. Use it to answer "what should I install for X" without reading
43 SKILL.md files.

Usage:
    skill_picker.py                          # browse all, grouped by family
    skill_picker.py --persona backend        # skills for a workload
    skill_picker.py --family security        # skills in a family
    skill_picker.py --search "token"         # keyword search
    skill_picker.py --tag security           # skills with a tag
    skill_picker.py --json                   # machine-readable
    skill_picker.py --install backend        # copy-paste install commands

Exit codes: 0 matches found, 1 no matches, 2 catalogue missing/stale.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
if not (REPO / "catalogue.json").is_file():
    REPO = Path(__file__).resolve().parent.parent.parent.parent
CATALOGUE = REPO / "catalogue.json"


def load() -> dict:
    if not CATALOGUE.is_file():
        print("catalogue.json missing — run generate_catalogue.py first", file=sys.stderr)
        sys.exit(2)
    return json.loads(CATALOGUE.read_text())


def install_cmd(skill: dict) -> str:
    return f"cp -r {skill['path']} ~/.claude/skills/{skill['name']}"


def fmt_skill(s: dict, show_install: bool = False) -> str:
    line = f"  {s['name']:<30} [{s['family']}] {s['description'][:70]}"
    if show_install:
        line += f"\n    install: {install_cmd(s)}"
    return line


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--persona", default="")
    ap.add_argument("--family", default="")
    ap.add_argument("--search", default="")
    ap.add_argument("--tag", default="")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--install", default="", metavar="PERSONA",
                    help="show install commands for a persona's skills")
    args = ap.parse_args(argv)

    cat = load()
    skills = cat["skills"]

    if args.install:
        matches = [s for s in skills if args.install in s["personas"]]
        if not matches:
            print(f"no skills for persona: {args.install}", file=sys.stderr)
            return 1
        for s in matches:
            print(install_cmd(s))
        return 0

    matches = skills
    if args.persona:
        matches = [s for s in matches if args.persona in s["personas"]]
    if args.family:
        matches = [s for s in matches if s["family"] == args.family]
    if args.tag:
        matches = [s for s in matches if args.tag in s["tags"]]
    if args.search:
        q = args.search.lower()
        matches = [s for s in matches
                   if q in s["name"].lower() or q in s["description"].lower()
                   or any(q in t for t in s["tags"])]

    if args.json:
        print(json.dumps(matches, indent=2))
        return 0 if matches else 1

    if not matches:
        print("no matching skills", file=sys.stderr)
        return 1

    if args.persona or args.family or args.tag or args.search:
        print(f"{len(matches)} skill(s):\n")
        for s in matches:
            print(fmt_skill(s, show_install=bool(args.persona)))
    else:
        for fam in sorted(cat["families"]):
            members = cat["families"][fam]
            print(f"\n## {fam} ({len(members)})")
            for name in members:
                s = next(x for x in skills if x["name"] == name)
                print(fmt_skill(s))
        print(f"\n{cat['count']} skills total. Filter: --persona, --family, --search, --tag")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
