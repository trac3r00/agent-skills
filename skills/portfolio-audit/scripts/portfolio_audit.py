#!/usr/bin/env python3
"""portfolio-audit: concentration, allocation, and gain/loss from an exported portfolio CSV.

A brokerage export answers "what do I own" but not "am I one bad day away
from a problem". This reads a CSV you exported yourself (no login, offline,
deterministic) and reports total value, per-position weight, allocation by
asset type, overall gain/loss, and concentration warnings.

Expected CSV columns (header, any order, case-insensitive):
    symbol, type, quantity, cost_basis, current_price
`type` is freeform (stock, crypto, etf, cash...). cost_basis and
current_price are per-unit.

Usage:
    portfolio_audit.py portfolio.csv [--json]
    ... --max-position 0.25     # exit 1 when any position exceeds 25%
    ... --max-type crypto=0.15  # exit 1 when an asset type exceeds 15%

Exit codes: 0 within limits, 1 over limit, 2 input error.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def parse_csv(path: Path) -> tuple[list[dict], str | None]:
    if not path.is_file():
        return [], f"missing file: {path}"
    try:
        rows = list(csv.DictReader(path.read_text(errors="replace").splitlines()))
    except (OSError, csv.Error) as exc:
        return [], f"unreadable: {path}: {exc}"
    need = {"symbol", "type", "quantity", "cost_basis", "current_price"}
    if not rows or not need.issubset({k.strip().lower() for k in rows[0]}):
        return [], f"csv must have columns: {', '.join(sorted(need))}"
    out = []
    for i, row in enumerate(rows, 2):
        r = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
        try:
            out.append({
                "symbol": r["symbol"], "type": r["type"] or "unknown",
                "quantity": float(r["quantity"]),
                "cost_basis": float(r["cost_basis"]),
                "current_price": float(r["current_price"]),
            })
        except ValueError:
            return [], f"line {i}: quantity/cost_basis/current_price must be numbers"
    if not out:
        return [], "no positions found"
    return out, None


def audit(positions: list[dict], max_position: float, max_type: dict[str, float]) -> dict:
    total_value = sum(p["quantity"] * p["current_price"] for p in positions)
    total_cost = sum(p["quantity"] * p["cost_basis"] for p in positions)
    for p in positions:
        p["value"] = round(p["quantity"] * p["current_price"], 2)
        p["weight"] = p["value"] / total_value if total_value else 0.0
        p["gain_loss_pct"] = round(
            (p["current_price"] - p["cost_basis"]) / p["cost_basis"] * 100
            if p["cost_basis"] else 0.0, 2)
    positions.sort(key=lambda p: -p["value"])

    by_type: dict[str, float] = {}
    for p in positions:
        by_type[p["type"]] = by_type.get(p["type"], 0.0) + p["value"]
    allocation = sorted(
        ({"type": t, "value": round(v, 2), "weight": v / total_value}
         for t, v in by_type.items()), key=lambda a: -a["value"])

    warnings = []
    for p in positions:
        if p["weight"] > max_position:
            warnings.append(f"{p['symbol']} is {p['weight']:.0%} of the portfolio "
                            f"(limit {max_position:.0%})")
    for a in allocation:
        lim = max_type.get(a["type"].lower())
        if lim is not None and a["weight"] > lim:
            warnings.append(f"{a['type']} allocation is {a['weight']:.0%} "
                            f"(limit {lim:.0%})")
    gl = (total_value - total_cost) / total_cost if total_cost else 0.0
    return {
        "total_value": round(total_value, 2), "total_cost": round(total_cost, 2),
        "gain_loss_pct": round(gl * 100, 2),
        "positions": positions, "allocation": allocation, "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("csv")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--max-position", type=float, default=0.25)
    ap.add_argument("--max-type", action="append", default=[], metavar="TYPE=WEIGHT")
    args = ap.parse_args(argv)

    max_type: dict[str, float] = {}
    for spec in args.max_type:
        if "=" not in spec:
            print(f"bad --max-type: {spec!r} (want TYPE=WEIGHT)", file=sys.stderr)
            return 2
        name, _, w = spec.partition("=")
        try:
            max_type[name.strip().lower()] = float(w)
        except ValueError:
            print(f"bad --max-type weight: {spec!r}", file=sys.stderr)
            return 2

    positions, err = parse_csv(Path(args.csv))
    if err:
        print(err, file=sys.stderr)
        return 2
    report = audit(positions, args.max_position, max_type)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        for p in report["positions"]:
            print(f"{p['symbol']:<8} {p['value']:>12,.2f}  {p['weight']:>6.1%}  "
                  f"{p['gain_loss_pct']:>+8.1f}%")
        print(f"\ntotal: {report['total_value']:,.2f} "
              f"({report['gain_loss_pct']:+.2f}% vs cost)")
        for w in report["warnings"]:
            print(f"WARNING: {w}")
    return 1 if report["warnings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
