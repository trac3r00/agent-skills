#!/usr/bin/env python3
"""graph-tools: build and query directed graphs from JSON edge lists.

Dependency chains, call graphs, org structures, state machines — they are
all edge lists until someone makes them queryable. Reads {"edges": [[a, b],
...]} and reports node/edge counts, degree stats, cycle detection, and
shortest paths (BFS). Stdlib-only, deterministic.

Usage:
    graph_tools.py edges.json [--json]
    graph_tools.py edges.json --path start end
    graph_tools.py edges.json --stats
    graph_tools.py edges.json --fail-on-cycle     # CI gate for DAGs

Exit codes: 0 acyclic / path found, 1 cycles found / no path, 2 input error.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict, deque
from pathlib import Path


def load(path: Path) -> dict:
    data = json.loads(path.read_text(errors="replace"))
    edges = data.get("edges", data if isinstance(data, list) else [])
    return {"edges": [(str(a), str(b)) for a, b in edges]}


def build(edges: list[tuple[str, str]]):
    adj: dict[str, set[str]] = defaultdict(set)
    nodes: set[str] = set()
    for a, b in edges:
        adj[a].add(b)
        nodes.update((a, b))
    return adj, nodes


def find_cycles(adj: dict[str, set[str]], nodes: set[str]) -> list[list[str]]:
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {n: WHITE for n in nodes}
    cycles: list[list[str]] = []
    stack: list[str] = []

    def dfs(u: str) -> None:
        color[u] = GRAY
        stack.append(u)
        for v in adj.get(u, ()):
            if color.get(v) == GRAY:
                i = stack.index(v)
                cycles.append(stack[i:] + [v])
            elif color.get(v) == WHITE:
                dfs(v)
        stack.pop()
        color[u] = BLACK

    for n in nodes:
        if color[n] == WHITE:
            dfs(n)
    return cycles


def shortest_path(adj: dict[str, set[str]], start: str, end: str) -> list[str] | None:
    if start == end:
        return [start]
    seen = {start}
    queue = deque([(start, [start])])
    while queue:
        node, path = queue.popleft()
        for nxt in adj.get(node, ()):
            if nxt == end:
                return path + [nxt]
            if nxt not in seen:
                seen.add(nxt)
                queue.append((nxt, path + [nxt]))
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("graph_file")
    ap.add_argument("--path", nargs=2, metavar=("FROM", "TO"))
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--fail-on-cycle", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    p = Path(args.graph_file)
    if not p.is_file():
        print(f"missing: {args.graph_file}", file=sys.stderr)
        return 2
    try:
        data = load(p)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        print(f"invalid graph JSON: {exc}", file=sys.stderr)
        return 2

    adj, nodes = build(data["edges"])
    cycles = find_cycles(adj, nodes)

    report: dict = {
        "nodes": len(nodes), "edges": len(data["edges"]),
        "cycles": [" -> ".join(c) for c in cycles[:10]],
    }
    if args.stats:
        in_deg: dict[str, int] = defaultdict(int)
        for a in adj:
            for b in adj[a]:
                in_deg[b] += 1
        report["stats"] = {
            "out_degree": {n: len(adj.get(n, ())) for n in sorted(nodes)},
            "in_degree": {n: in_deg.get(n, 0) for n in sorted(nodes)},
        }
    rc = 1 if cycles else 0

    if args.path:
        start, end = args.path
        path = shortest_path(adj, start, end)
        report["path"] = path
        report["path_found"] = path is not None
        rc = 0 if path else 1
    if args.fail_on_cycle:
        rc = 1 if cycles else 0

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(f"nodes={report['nodes']} edges={report['edges']} cycles={len(cycles)}")
        for c in report["cycles"]:
            print(f"  cycle: {c}")
        if args.path:
            print("path: " + (" -> ".join(path) if path else "none"))
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
