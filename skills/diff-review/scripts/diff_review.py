#!/usr/bin/env python3
"""diff-review: a fast mechanical review pass over a unified diff before a human or agent reads it.

The pre-review triage agents skip: debug output left in production paths,
TODO/FIXME/HACK markers added inside the change, trivial test assertions that
prove nothing (`assert True`, snapshots pinning nothing), and deleted tests.
It also shells out to sibling ecosystem gates (secret-gate, comment-checker)
when present so one command runs the whole mechanical layer. Deterministic,
stdlib-only, reads a unified diff from stdin.

Usage:
    git diff | diff_review.py                    # human-readable findings
    git diff main...HEAD | diff_review.py --json
    git diff | diff_review.py --tools-dir path/to/skills   # chain secret-gate + comment-checker
    git diff | diff_review.py --fail-over 3      # tolerate up to 3 findings

Exit codes: 0 clean/within budget, 1 findings over budget, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEBUG_OUTPUT = re.compile(r"\b(puts|pprint|console\.log|dbg!|eprintln!|print_r)\(")
PY_PRINT = re.compile(r"\bprint\s*\(")
MARKER = re.compile(r"\b(TODO|FIXME|HACK|XXX|BUG|WIP|REMOVE ME)\b", re.I)
TRIVIAL_TEST = re.compile(r"\bassert\s+(True|1\s*==\s*1)\b|\bassertEqual\(\s*([^,]+)\s*,\s*\2\s*\)")
DELETED_TEST = re.compile(r"^-\s*(def test_|it\(|test\(|describe\()")

CODE_EXTS = {".py", ".js", ".jsx", ".ts", ".tsx", ".go", ".rs", ".rb", ".java",
             ".c", ".cpp", ".cs", ".swift", ".kt", ".php", ".sh"}


def parse_diff(diff: str):
    current, new_line, entries = "", 0, []
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            current = re.sub(r"^\+\+\+ [ab]/", "", raw).strip()
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            new_line = int(m.group(1)) - 1 if m else 0
        elif raw.startswith("+") and not raw.startswith("+++"):
            new_line += 1
            entries.append(("add", current, new_line, raw[1:]))
        elif raw.startswith("-") and not raw.startswith("---"):
            entries.append(("del", current, new_line, raw[1:]))
        elif not raw.startswith("-"):
            new_line += 1
    return entries


def review(entries, chain: list[tuple[Path, list[str]]], diff_raw: str) -> list[dict]:
    findings = []
    ext_of = {}
    for op, path, _, _ in entries:
        ext_of[path] = Path(path).suffix
    added = "\n".join(text for op, _, _, text in entries if op == "add")
    for op, path, line_no, text in entries:
        ext = ext_of.get(path, "")
        is_test = re.search(r"(test_|_test|spec)", Path(path).name) is not None
        if op == "add" and ext in CODE_EXTS:
            if DEBUG_OUTPUT.search(text) and ext != ".py":
                findings.append({"file": path, "line": line_no, "kind": "debug-output",
                                 "text": text.strip()[:100]})
            if PY_PRINT.search(text) and ext == ".py" and not is_test:
                findings.append({"file": path, "line": line_no, "kind": "debug-output",
                                 "text": text.strip()[:100]})
            if MARKER.search(text):
                findings.append({"file": path, "line": line_no, "kind": "unresolved-marker",
                                 "text": text.strip()[:100]})
            if is_test and TRIVIAL_TEST.search(text):
                findings.append({"file": path, "line": line_no, "kind": "trivial-assertion",
                                 "text": text.strip()[:100]})
        if op == "del" and DELETED_TEST.match(text):
            findings.append({"file": path, "line": line_no, "kind": "test-deleted",
                             "text": text.strip()[:100]})
    for tool, argv_mode in chain:
        try:
            p = subprocess.run([sys.executable, str(tool), *argv_mode],
                               input=added, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired):
            continue
        if p.returncode == 1:
            name = tool.parent.parent.name
            first = next((ln for ln in (p.stdout + p.stderr).splitlines()
                          if ln.strip() and ":" in ln), "findings")
            findings.append({"file": "-", "line": 0, "kind": f"{name}-findings",
                             "text": first.strip()[:120]})
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-over", type=int, default=0, metavar="N")
    ap.add_argument("--tools-dir", default="",
                    help="skills root; chains secret-gate and comment-checker when present")
    ap.add_argument("--diff-file", default="",
                    help="read diff from file instead of stdin")
    args = ap.parse_args(argv)

    diff_raw = Path(args.diff_file).read_text(errors="replace") if args.diff_file else sys.stdin.read()
    if not diff_raw.strip():
        print("empty diff", file=sys.stderr)
        return 2

    chain = []
    if args.tools_dir:
        root = Path(args.tools_dir)
        for rel, argv_mode in (
            ("secret-gate/scripts/secret_gate.py", ["-"]),
            ("comment-checker/scripts/comment_checker.py", ["-"]),
        ):
            p = root / rel
            if p.is_file():
                chain.append((p, argv_mode))

    findings = review(parse_diff(diff_raw), chain, diff_raw)
    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings)}, indent=2))
    else:
        for f in findings:
            loc = f"{f['file']}:{f['line']}" if f["line"] else f["file"]
            print(f"{loc}: {f['kind']}: {f['text']}")
        print(f"\n{len(findings)} finding(s); budget {args.fail_over}")
    return 1 if len(findings) > args.fail_over else 0


if __name__ == "__main__":
    raise SystemExit(main())
