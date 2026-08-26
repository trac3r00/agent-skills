---
name: graph-tools
description: Builds and queries directed graphs from JSON edge lists — node/edge counts, in/out degree stats, cycle detection via DFS coloring, and BFS shortest paths. Dependency chains, call graphs, state machines, and org structures are all edge lists until someone makes them queryable. Stdlib-only, deterministic.
when_to_use: "What's the dependency path from X to Y?", "does this DAG actually have no cycles?" (CI gate with --fail-on-cycle), understanding a system's structure from its edges. NOT a graph database or a visualizer; it's the query layer for graph-shaped data.
version: 1.0.0
license: MIT
metadata:
  agentskills:
    tags: [graphs, dependencies, algorithms, ci-gate]
---

# Graph Tools

Every dependency chain is an edge list until someone makes it queryable.

## Commands

```bash
python3 scripts/graph_tools.py deps.json --stats
python3 scripts/graph_tools.py deps.json --path ui database
python3 scripts/graph_tools.py deps.json --fail-on-cycle   # CI: assert DAG
```

## Input

```json
{"edges": [["ui", "api"], ["api", "db"], ["db", "cache"]]}
```

## Reports

- Node/edge counts, in/out degree per node (`--stats`)
- Cycles as readable paths (`a -> b -> c -> a`), exit 1 when found
- Shortest path via BFS (`--path FROM TO`), exit 1 when none
- `--fail-on-cycle` for CI gates on pipelines, imports, migrations

## Pairs with

`gate-graph` (module overlap via AST fingerprints — the code-level view;
this is the structure-level view), `json-diff` (compare two graph snapshots).
