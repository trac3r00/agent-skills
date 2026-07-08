#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", ".mypy_cache", ".pytest_cache"}


@dataclass(frozen=True)
class GateProfile:
    name: str
    path: str
    fingerprints: frozenset[str]


def _iter_constant(node: Optional[ast.AST]) -> Optional[str]:
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        parts: list[str] = []
        for value in node.values:
            if not isinstance(value, ast.Constant) or not isinstance(value.value, str):
                return None
            parts.append(value.value)
        return "".join(parts)
    return None


def _norm(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    normalized = " ".join(value.split())
    return normalized if normalized else None


class GateFingerprinter(ast.NodeVisitor):
    REGEX_CALLS = {"compile", "search", "match", "findall", "finditer", "fullmatch", "sub", "subn"}
    SUBSTRING_CALLS = {"find", "startswith", "endswith", "contains", "replace", "count"}

    def __init__(self) -> None:
        self.fps: set[str] = set()

    def _add(self, prefix: str, node: Optional[ast.AST]) -> None:
        value = _norm(_iter_constant(node))
        if value:
            self.fps.add(f"{prefix}:{value}")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.fps.add(f"func:{node.name}")
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.fps.add(f"func:{node.name}")
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.fps.add(f"class:{node.name}")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if isinstance(node.ctx, ast.Load):
            self.fps.add(f"attr:{node.attr}")
        self.generic_visit(node)

    def visit_Compare(self, node: ast.Compare) -> None:
        if node.ops:
            op = node.ops[0].__class__.__name__
            if op in {"In", "NotIn"}:
                self._add("substr", node.left)
                for comparator in node.comparators:
                    self._add("substr", comparator)
        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise) -> None:
        if node.exc is not None:
            for exc in _iter_exception_types(node.exc):
                self.fps.add(f"raise:{exc}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func = node.func
        fn_name: Optional[str] = None
        is_re = False
        if isinstance(func, ast.Name):
            fn_name = func.id
            is_re = fn_name in self.REGEX_CALLS
        elif isinstance(func, ast.Attribute):
            fn_name = func.attr
            self.fps.add(f"attr_method:{fn_name}")
            if isinstance(func.value, ast.Name):
                self.fps.add(f"attr:{func.value.id}")
                is_re = func.value.id == "re"

        if is_re and node.args:
            self._add("regex", node.args[0])
        elif fn_name in self.SUBSTRING_CALLS and node.args:
            self._add("substr", node.args[0])
        self.generic_visit(node)


def _iter_exception_types(node: ast.AST) -> Iterable[str]:
    if isinstance(node, ast.Call):
        fn = node.func
        if isinstance(fn, ast.Name):
            yield fn.id
            return
        if isinstance(fn, ast.Attribute):
            yield fn.attr
            return
    if isinstance(node, ast.Name):
        yield node.id
    elif isinstance(node, ast.Attribute):
        yield node.attr
    elif isinstance(node, ast.Tuple):
        for child in node.elts:
            for exc in _iter_exception_types(child):
                yield exc


def discover_modules(root: Path) -> list[tuple[str, Path]]:
    files: list[tuple[str, Path]] = []
    root = root.resolve()
    if not root.exists():
        return files
    for file in root.rglob("*.py"):
        if file.name == "__init__.py":
            continue
        if any(part in SKIP_DIRS for part in file.parts):
            continue
        rel = file.relative_to(root).with_suffix("")
        files.append((".".join(rel.parts), file))
    files.sort(key=lambda item: item[0])
    return files


def collect_fingerprints(path: Path) -> frozenset[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except (OSError, SyntaxError):
        return frozenset()
    visitor = GateFingerprinter()
    visitor.visit(tree)
    return frozenset(visitor.fps)


def collect_imports(source: str, current_module: str) -> set[str]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()
    imports: set[str] = set()
    base_parts = current_module.split(".")
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name:
                    imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name == "*":
                    if node.module:
                        imports.add(node.module)
                    continue
                if node.level == 0:
                    module_name = node.module or ""
                else:
                    package = base_parts[:-node.level]
                    if node.module:
                        package.append(node.module)
                    module_name = ".".join(package)
                if module_name:
                    imports.add(module_name)
                    imports.add(f"{module_name}.{alias.name}")
                else:
                    imports.add(alias.name)
    return imports


def is_orphan(module_name: str, import_refs: set[str]) -> bool:
    top = module_name.split(".")[0]
    for ref in import_refs:
        if ref == module_name or ref.startswith(f"{module_name}.") or module_name.startswith(f"{ref}.") or ref == top:
            return False
    return True


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def build_matrix(
    gates: list[GateProfile]
) -> tuple[list[list[float]], list[dict[str, object]]]:
    """Return the full similarity matrix plus a LIGHTWEIGHT pair list.

    The pair list carries only ``left``/``right``/``overlap`` — no per-pair
    fingerprint diffs. Dumping the shared/left_only/right_only sets for every
    one of the O(n^2) pairs is exactly the token-bloat this tool exists to
    catch, so the heavy diff is computed lazily (see ``enrich_pair``) and only
    for the handful of pairs that actually breach the overlap threshold.
    """
    size = len(gates)
    matrix = [[0.0 for _ in range(size)] for _ in range(size)]
    overlap_pairs: list[dict[str, object]] = []
    for i in range(size):
        matrix[i][i] = 1.0
        for j in range(i + 1, size):
            score = jaccard(gates[i].fingerprints, gates[j].fingerprints)
            matrix[i][j] = matrix[j][i] = score
            overlap_pairs.append(
                {
                    "left": gates[i].name,
                    "right": gates[j].name,
                    "overlap": round(score, 4),
                }
            )
    return matrix, overlap_pairs


def enrich_pair(pair: dict[str, object], gates_by_name: dict[str, GateProfile]) -> dict[str, object]:
    """Attach the shared / left_only / right_only fingerprint sets to a pair.

    Called only for high-overlap pairs so an operator can see *what* two gates
    duplicate. Keeping this lazy is what stops the JSON report from exploding.
    """
    left = gates_by_name.get(str(pair.get("left", "")))
    right = gates_by_name.get(str(pair.get("right", "")))
    if left is None or right is None:
        return dict(pair)
    enriched = dict(pair)
    enriched["shared"] = sorted(left.fingerprints & right.fingerprints)
    enriched["left_only"] = sorted(left.fingerprints - right.fingerprints)
    enriched["right_only"] = sorted(right.fingerprints - left.fingerprints)
    return enriched


def overlap_value(pair: dict[str, object]) -> float:
    raw = pair.get("overlap")
    if isinstance(raw, (int, float)):
        return float(raw)
    return 0.0


def report_text(
    gates: list[GateProfile],
    matrix: list[list[float]],
    overlaps: list[dict[str, object]],
    orphans: list[str],
    max_gates: int,
    max_overlap: float,
) -> str:
    names = [p.name for p in gates]
    max_len = max((len(name) for name in names), default=10) + 2
    out: list[str] = []
    out.append("Gate-graph overlap report")
    out.append("=" * 30)
    out.append(f"gates: {len(gates)}")
    out.append(f"max-gates: {max_gates}")
    out.append(f"max-overlap: {max_overlap}")
    out.append("")
    out.append("Fingerprints:")
    for gate in gates:
        out.append(f"  {gate.name}: {len(gate.fingerprints)} fingerprints")
    out.append("")
    out.append("Overlap matrix:")
    header = " " * max_len + "".join(f"{name[:7]:>8}" for name in names)
    out.append(header.rstrip())
    for i, gate in enumerate(gates):
        row = "".join(f"{matrix[i][j]:>8.2f}" for j in range(len(gates)))
        out.append(f"{gate.name:<{max_len}}" + row)
    out.append("")
    out.append("High-overlap candidate pairs:")
    over_pairs = [p for p in overlaps if overlap_value(p) > max_overlap]
    if over_pairs:
        for item in sorted(
            over_pairs, key=lambda item: (-overlap_value(item), str(item.get("left", "")), str(item.get("right", "")))
        ):
            left_name = str(item.get("left", ""))
            right_name = str(item.get("right", ""))
            out.append(f"  {left_name} <-> {right_name}: {overlap_value(item):.2f}")
    else:
        out.append("  none")
    out.append("")
    out.append("Orphan gates:")
    if orphans:
        for name in sorted(orphans):
            out.append(f"  - {name}")
    else:
        out.append("  none")
    return "\n".join(out)


def run(
    root_dir: Path,
    max_gates: int,
    max_overlap: float
) -> tuple[
    int,
    list[GateProfile],
    list[list[float]],
    list[dict[str, object]],
    list[str],
    bool,
    bool,
]:
    modules = discover_modules(root_dir)
    gates = [GateProfile(name, str(path), collect_fingerprints(path)) for name, path in modules]
    all_imports: set[str] = set()
    for name, path in modules:
        try:
            source = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        all_imports |= collect_imports(source, name)

    orphans = [gate.name for gate in gates if is_orphan(gate.name, all_imports)]
    matrix, overlaps = build_matrix(gates)
    over_gate_limit = len(gates) > max_gates
    over_overlap = any(overlap_value(item) > max_overlap for item in overlaps)
    return (
        1 if (over_gate_limit or over_overlap) else 0,
        gates,
        matrix,
        overlaps,
        orphans,
        over_gate_limit,
        over_overlap,
    )


def main(argv: Optional[list[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="Compute AST overlap between Python gate modules and detect dead gates.")
    ap.add_argument("dir", help="target directory containing gate modules")
    ap.add_argument("--max-gates", type=int, default=49, help="fail if gate count exceeds this")
    ap.add_argument("--max-overlap", type=float, default=0.5, help="fail if overlap > threshold")
    ap.add_argument("--top", type=int, default=20, help="how many ranked overlap pairs to include in JSON (name+score only)")
    ap.add_argument("--full-matrix", action="store_true", help="include the full NxN matrix and per-gate fingerprint sets in JSON (large)")
    ap.add_argument("--json", action="store_true", help="emit JSON report")
    args = ap.parse_args(argv)

    root = Path(args.dir).expanduser()
    if not root.exists():
        print(f"error: directory not found: {root}")
        return 2

    exit_code, gate_profiles, matrix, overlap_pairs, orphans, over_gate_limit, over_overlap = run(
        root,
        args.max_gates,
        args.max_overlap,
    )

    if args.json:
        gates_by_name = {g.name: g for g in gate_profiles}
        high_overlaps = [
            enrich_pair(item, gates_by_name)
            for item in overlap_pairs
            if overlap_value(item) > args.max_overlap
        ]
        # Rank all pairs by score but keep only the lightweight name+score rows,
        # capped, so the report never balloons on a large gate layer.
        top_pairs = sorted(overlap_pairs, key=lambda p: -overlap_value(p))[: args.top]
        payload = {
            "target_dir": str(root),
            "gate_count": len(gate_profiles),
            "max_gates": args.max_gates,
            "max_overlap": args.max_overlap,
            "gates": [
                {
                    "name": g.name,
                    "path": g.path,
                    "fingerprint_count": len(g.fingerprints),
                }
                for g in gate_profiles
            ],
            "gate_names": [g.name for g in gate_profiles],
            "top_overlap_pairs": top_pairs,
            "high_overlap_pairs": high_overlaps,
            "orphan_gates": orphans,
        }
        if args.full_matrix:
            payload["matrix"] = matrix
            payload["gates"] = [
                {**gate_dict, "fingerprints": sorted(g.fingerprints)}
                for gate_dict, g in zip(payload["gates"], gate_profiles)
            ]
        payload["overlap_violations"] = high_overlaps
        payload["violations"] = {
            "over_gate_limit": over_gate_limit,
            "overlap_threshold": over_overlap,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
        return exit_code

    text = report_text(
        gate_profiles,
        matrix,
        overlap_pairs,
        orphans,
        args.max_gates,
        args.max_overlap,
    )
    print(text)
    if over_gate_limit:
        print(f"FAIL: gate_count {len(gate_profiles)} > max_gates {args.max_gates}")
    if over_overlap:
        for item in [p for p in overlap_pairs if overlap_value(p) > args.max_overlap]:
            print(f"FAIL: {item['left']} <-> {item['right']} overlap {item['overlap']}")
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
