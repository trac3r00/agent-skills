#!/usr/bin/env python3
"""usage-audit: token and session accounting across every AI agent client.

Each client records what it consumed — Claude Code writes per-message usage
into project JSONL, Codex emits token_count events, OpenCode stores per-session
token columns — but none of them shows you the cross-client total. This reads
the same local stores as session-handoff (read-only, nothing uploaded) and
reports tokens by model, by client, and by project, with an optional budget
gate for CI or a cron check.

Usage:
    usage_audit.py [--since DAYS] [--json]
    usage_audit.py --by project              # group by working directory
    usage_audit.py --budget-tokens N         # exit 1 when total exceeds N

Exit codes: 0 ok, 1 over budget, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = Path.home()


def scan_claude(since: datetime) -> list[dict]:
    rows = []
    projects = HOME / ".claude" / "projects"
    if not projects.is_dir():
        return rows
    for proj in projects.iterdir():
        if not proj.is_dir():
            continue
        for jl in proj.glob("*.jsonl"):
            if datetime.fromtimestamp(jl.stat().st_mtime, tz=timezone.utc) < since:
                continue
            in_t = out_t = cache_t = 0
            model = ""
            for ln in jl.read_text(errors="replace").splitlines():
                try:
                    d = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                usage = d.get("message", {}).get("usage") if d.get("type") == "assistant" else None
                if usage:
                    model = d["message"].get("model", model)
                    in_t += usage.get("input_tokens", 0)
                    out_t += usage.get("output_tokens", 0)
                    cache_t += usage.get("cache_read_input_tokens", 0)
            if in_t or out_t:
                rows.append({"client": "claude", "model": model or "unknown",
                             "project": proj.name, "input_tokens": in_t,
                             "output_tokens": out_t, "cache_tokens": cache_t})
    return rows


def scan_codex(since: datetime) -> list[dict]:
    rows = []
    sessions = HOME / ".codex" / "sessions"
    if not sessions.is_dir():
        return rows
    for jl in sessions.rglob("rollout-*.jsonl"):
        if datetime.fromtimestamp(jl.stat().st_mtime, tz=timezone.utc) < since:
            continue
        in_t = out_t = cache_t = 0
        model = cwd = ""
        last_total = None
        for ln in jl.read_text(errors="replace").splitlines():
            try:
                d = json.loads(ln)
            except json.JSONDecodeError:
                continue
            pl = d.get("payload", {})
            if d.get("type") == "session_meta":
                cwd = pl.get("cwd", "")
            elif d.get("type") == "turn_context":
                model = pl.get("model", model)
            elif pl.get("type") == "token_count":
                info = pl.get("info") or {}
                total = info.get("total_token_usage") or {}
                if total:
                    last_total = total
        if last_total:
            in_t = last_total.get("input_tokens", 0)
            out_t = last_total.get("output_tokens", 0)
            cache_t = last_total.get("cached_input_tokens", 0)
        if in_t or out_t:
            rows.append({"client": "codex", "model": model or "unknown",
                         "project": cwd, "input_tokens": in_t,
                         "output_tokens": out_t, "cache_tokens": cache_t})
    return rows


def scan_opencode(since: datetime) -> list[dict]:
    rows = []
    db = HOME / ".local" / "share" / "opencode" / "opencode.db"
    if not db.is_file():
        return rows
    ts = int(since.timestamp() * 1000)
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        cur = con.execute(
            "SELECT model, directory, tokens_input, tokens_output, tokens_cache_read "
            "FROM session WHERE time_updated > ?", (ts,))
        for model, directory, ti, to, tc in cur.fetchall():
            if ti or to:
                rows.append({"client": "opencode", "model": model or "unknown",
                             "project": directory or "", "input_tokens": ti or 0,
                             "output_tokens": to or 0, "cache_tokens": tc or 0})
        con.close()
    except sqlite3.Error:
        pass
    return rows


def aggregate(rows: list[dict], key: str) -> list[dict]:
    groups: dict[str, dict] = {}
    for r in rows:
        g = groups.setdefault(r[key] or "unknown", {
            key: r[key] or "unknown", "sessions": 0, "input_tokens": 0,
            "output_tokens": 0, "cache_tokens": 0})
        g["sessions"] += 1
        g["input_tokens"] += r["input_tokens"]
        g["output_tokens"] += r["output_tokens"]
        g["cache_tokens"] += r["cache_tokens"]
    return sorted(groups.values(),
                  key=lambda g: -(g["input_tokens"] + g["output_tokens"]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--since", type=int, default=30, metavar="DAYS")
    ap.add_argument("--by", choices=["model", "client", "project"], default="model")
    ap.add_argument("--budget-tokens", type=int, default=None, metavar="N")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    since = datetime.now(tz=timezone.utc) - timedelta(days=args.since)
    rows = scan_claude(since) + scan_codex(since) + scan_opencode(since)
    total_in = sum(r["input_tokens"] for r in rows)
    total_out = sum(r["output_tokens"] for r in rows)
    report = {
        "since_days": args.since,
        "by_model": aggregate(rows, "model"),
        "by_client": aggregate(rows, "client"),
        "by_project": aggregate(rows, "project"),
        "totals": {"sessions": len(rows), "input_tokens": total_in,
                   "output_tokens": total_out,
                   "cache_tokens": sum(r["cache_tokens"] for r in rows)},
    }
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        groups = report[f"by_{args.by}"]
        width = max((len(str(g[args.by])) for g in groups), default=8)
        for g in groups:
            print(f"{str(g[args.by]):<{width}}  sessions={g['sessions']:<4} "
                  f"in={g['input_tokens']:<12,} out={g['output_tokens']:<10,} "
                  f"cache={g['cache_tokens']:,}")
        t = report["totals"]
        print(f"\ntotal: {t['sessions']} sessions, "
              f"{t['input_tokens']:,} in + {t['output_tokens']:,} out tokens "
              f"(last {args.since}d, cache {t['cache_tokens']:,})")
    if args.budget_tokens is not None and total_in + total_out > args.budget_tokens:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
