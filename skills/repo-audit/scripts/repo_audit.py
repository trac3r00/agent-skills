#!/usr/bin/env python3
"""repo-audit: structural health check for a git repository.

Agents clone, scaffold, and inherit repos with no quick way to answer "is
this thing maintained?" This checks the structural essentials: LICENSE,
README, tests, CI config, .gitignore, large tracked files, and stale
branches (no commits in N days, fully merged). Offline, stdlib + git CLI,
deterministic.

Usage:
    repo_audit.py [PATH] [--json]
    repo_audit.py . --stale-days 60
    repo_audit.py . --fail-on license,tests   # require specific checks

Exit codes: 0 all checks pass (or only warnings), 1 failing check, 2 not a repo.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

LARGE_FILE_BYTES = 5_000_000


def git(repo: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True)
    return p.returncode, p.stdout.strip()


def audit(repo: Path, stale_days: int, require: list[str]) -> dict:
    checks: dict[str, dict] = {}

    def check(name: str, ok: bool, value: str):
        checks[name] = {"status": "pass" if ok else "fail", "value": value}

    check("license", any((repo / n).is_file() for n in
                         ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE")),
          "found" if any((repo / n).is_file() for n in
                         ("LICENSE", "LICENSE.md", "LICENSE.txt", "LICENCE")) else "missing")
    check("readme", any((repo / n).is_file() for n in
                        ("README.md", "README.rst", "README.txt", "README")),
          "found" if any((repo / n).is_file() for n in
                         ("README.md", "README.rst", "README.txt", "README")) else "missing")
    has_tests = any(repo.glob("**/test_*.py")) or any(repo.glob("**/*_test.py")) \
        or any(repo.glob("**/*.test.js")) or any(repo.glob("**/tests/*"))
    check("tests", has_tests, "found" if has_tests else "no test files detected")
    has_ci = (repo / ".github" / "workflows").is_dir() or (repo / ".gitlab-ci.yml").is_file() \
        or (repo / ".circleci").is_dir()
    check("ci", has_ci, "found" if has_ci else "no CI config")
    check("gitignore", (repo / ".gitignore").is_file(),
          "found" if (repo / ".gitignore").is_file() else "missing (untracked junk risk)")

    _, ls = git(repo, "ls-files")
    large = []
    for f in ls.splitlines():
        fp = repo / f
        if fp.is_file() and fp.stat().st_size > LARGE_FILE_BYTES:
            large.append({"path": f, "bytes": fp.stat().st_size})
    checks["large_files"] = {"status": "pass" if not large else "warn",
                             "value": f"{len(large)} file(s) over {LARGE_FILE_BYTES // 1_000_000}MB"}

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=stale_days)
    _, branch_out = git(repo, "branch", "--merged", "HEAD",
                        "--format=%(refname:short)")
    branches = []
    for name in branch_out.splitlines():
        name = name.strip()
        if not name or name in ("main", "master", "develop"):
            continue
        rc, ts = git(repo, "log", "-1", "--format=%cI", name)
        if rc != 0 or not ts:
            continue
        last = datetime.fromisoformat(ts)
        if last < cutoff:
            branches.append({"name": name, "last_commit": ts})
    checks["stale_branches"] = {"status": "pass" if not branches else "warn",
                                "value": f"{len(branches)} merged branch(es) idle >{stale_days}d"}

    rc, _ = git(repo, "rev-parse", "--git-dir")
    if rc != 0:
        return {}

    required_fails = [n for n in require if checks.get(n, {}).get("status") == "fail"]
    any_fail = any(c["status"] == "fail" for c in checks.values())
    return {
        "repo": str(repo), "checks": checks,
        "large_files": large, "branches": branches,
        "failing": required_fails or ([n for n, c in checks.items()
                                       if c["status"] == "fail"] if any_fail else []),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("path", nargs="?", default=".")
    ap.add_argument("--stale-days", type=int, default=90)
    ap.add_argument("--fail-on", default="", help="comma-separated check names that must pass")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    repo = Path(args.path).resolve()
    rc, _ = git(repo, "rev-parse", "--git-dir")
    if rc != 0:
        print(f"not a git repository: {repo}", file=sys.stderr)
        return 2

    require = [n.strip() for n in args.fail_on.split(",") if n.strip()]
    report = audit(repo, args.stale_days, require)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for name, c in report["checks"].items():
            mark = {"pass": "ok", "warn": "!!", "fail": "XX"}[c["status"]]
            print(f"[{mark}] {name}: {c['value']}")
        for f in report["large_files"]:
            print(f"  large: {f['path']} ({f['bytes']:,} bytes)")
        for b in report["branches"]:
            print(f"  stale: {b['name']} (last {b['last_commit'][:10]})")
        print(f"\n{len(report['failing'])} failing check(s)")
    return 1 if report["failing"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
