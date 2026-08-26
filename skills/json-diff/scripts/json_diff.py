#!/usr/bin/env python3
"""json-diff: semantic diff between two JSON documents, reported by path.

`diff` on JSON is useless — one reordered key and everything flags. This
parses both documents and reports structural changes by JSON path: added,
removed, changed (with old/new values), recursing through nested objects and
comparing arrays by position. Deterministic, stdlib-only.

Usage:
    json_diff.py old.json new.json [--json]
    json_diff.py a.json b.json --max-changes 0   # CI: fail on any change
    json_diff.py - b.json < a.json               # stdin for the left side

Exit codes: 0 identical, 1 differences found (or over --max-changes), 2 input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def diff(a, b, path: str, out: list[dict]) -> None:
    if isinstance(a, dict) and isinstance(b, dict):
        for k in a.keys() - b.keys():
            out.append({"path": f"{path}.{k}".lstrip("."), "kind": "removed",
                        "old": a[k]})
        for k in b.keys() - a.keys():
            out.append({"path": f"{path}.{k}".lstrip("."), "kind": "added",
                        "new": b[k]})
        for k in a.keys() & b.keys():
            diff(a[k], b[k], f"{path}.{k}".lstrip("."), out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out.append({"path": path or "<root>", "kind": "changed",
                        "old": f"array[{len(a)}]", "new": f"array[{len(b)}]"})
        for i, (x, y) in enumerate(zip(a, b)):
            diff(x, y, f"{path}[{i}]", out)
    elif a != b:
        out.append({"path": path or "<root>", "kind": "changed",
                    "old": a, "new": b})


def load(source: str) -> tuple[object, str | None]:
    try:
        text = sys.stdin.read() if source == "-" else Path(source).read_text(errors="replace")
        return json.loads(text), None
    except OSError as exc:
        return None, f"unreadable: {source}: {exc}"
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON in {source}: {exc}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("left")
    ap.add_argument("right")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-changes", type=int, default=None, metavar="N")
    args = ap.parse_args(argv)

    a, err = load(args.left)
    if err:
        print(err, file=sys.stderr)
        return 2
    b, err = load(args.right)
    if err:
        print(err, file=sys.stderr)
        return 2

    changes: list[dict] = []
    diff(a, b, "", changes)

    if args.json:
        print(json.dumps({"changes": changes, "count": len(changes)}, indent=2))
    else:
        for c in changes:
            if c["kind"] == "changed":
                print(f"~ {c['path']}: {json.dumps(c['old'])[:60]} -> {json.dumps(c['new'])[:60]}")
            elif c["kind"] == "added":
                print(f"+ {c['path']}: {json.dumps(c['new'])[:60]}")
            else:
                print(f"- {c['path']}: {json.dumps(c['old'])[:60]}")
        print(f"\n{len(changes)} change(s)")

    if args.max_changes is not None and len(changes) > args.max_changes:
        print(f"over budget: {len(changes)} > {args.max_changes}", file=sys.stderr)
        return 1
    return 1 if changes else 0


if __name__ == "__main__":
    raise SystemExit(main())
