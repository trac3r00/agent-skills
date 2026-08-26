#!/usr/bin/env python3
"""changelog-gen: categorized changelog from conventional commits since a tag.

Reads git history since the last tag (or a named ref) and groups commits by
conventional-commit type into Keep a Changelog sections: Added (feat),
Fixed (fix), Changed (refactor/perf/style), Documentation (docs), Internal
(chore/test/ci/build). Scope annotations are preserved. Deterministic — the
agent writes the prose summary; this provides the honest skeleton.

Usage:
    changelog_gen.py [--repo PATH] [--since-tag v1.2.0]
    changelog_gen.py --since-tag $(git describe --tags --abbrev=0)
    changelog_gen.py --since HEAD~20 --out CHANGELOG.md --json

Exit codes: 0 ok, 2 not a repo / unknown ref.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

CC_RE = re.compile(r"^(feat|fix|docs|style|refactor|perf|test|chore|build|ci|revert)"
                   r"(?:\(([^)]+)\))?(!)?:\s*(.+)$")

SECTIONS = {
    "feat": "Added", "fix": "Fixed", "docs": "Documentation",
    "refactor": "Changed", "perf": "Changed", "style": "Changed",
    "test": "Internal", "chore": "Internal", "build": "Internal",
    "ci": "Internal", "revert": "Fixed",
}


def git(repo: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--repo", default=".")
    ap.add_argument("--since-tag", default="")
    ap.add_argument("--since", default="")
    ap.add_argument("--out", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    repo = Path(args.repo).resolve()
    rc, _ = git(repo, "rev-parse", "--git-dir")
    if rc != 0:
        print(f"not a git repository: {repo}", file=sys.stderr)
        return 2

    ref = args.since or args.since_tag
    if not ref:
        rc, ref = git(repo, "describe", "--tags", "--abbrev=0")
        if rc != 0 or not ref:
            print("no tag found; pass --since or --since-tag", file=sys.stderr)
            return 2
    rc, log = git(repo, "log", f"{ref}..HEAD", "--format=%s")
    if rc != 0:
        print(f"unknown ref: {ref}", file=sys.stderr)
        return 2

    sections: dict[str, list[str]] = {}
    uncategorized = []
    for line in log.splitlines():
        line = line.strip()
        if not line:
            continue
        m = CC_RE.match(line)
        if not m:
            uncategorized.append(line)
            continue
        typ, scope, _bang, subject = m.groups()
        entry = f"{subject.strip()} ({scope})" if scope else subject.strip()
        sections.setdefault(SECTIONS[typ], []).append(entry)

    ordered = ["Added", "Changed", "Fixed", "Documentation", "Internal", "Other"]
    flat_sections = {s: sections.get(s, []) for s in ordered if sections.get(s)}
    if uncategorized:
        flat_sections["Other"] = uncategorized
    count = sum(len(v) for v in flat_sections.values())

    if args.json:
        print(json.dumps({"since": ref, "count": count,
                          "sections": flat_sections}, indent=2))
        return 0

    lines = [f"# Changes since {ref}", ""]
    for name in ordered:
        entries = flat_sections.get(name)
        if not entries:
            continue
        lines.append(f"## {name}")
        lines.append("")
        lines.extend(f"- {e}" for e in entries)
        lines.append("")
    doc = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(doc)
        print(f"changelog written: {args.out} ({count} commits since {ref})")
    else:
        print(doc)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
