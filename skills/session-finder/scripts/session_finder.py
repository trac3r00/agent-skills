#!/usr/bin/env python3
"""session-finder: detect and administer running AI agent sessions.

Fast, reliable process-level detection of AI agent clients running on this
machine — Claude Code, Codex, OMO/Senpi, gjc (gajae-code), Hermes, and
others — with admin actions: status summary, watch mode, and safe kill
(SIGTERM only, refuses non-agent PIDs). Complements session-handoff (which
reads completed session LOGS) — this watches LIVE processes.

Usage:
    session_finder.py                 # one-shot scan, human-readable
    session_finder.py --json          # machine-readable
    session_finder.py --match PATTERN # extra process pattern to match
    session_finder.py --kill PID      # SIGTERM an agent process (validated)
    session_finder.py --watch N       # re-scan every N seconds (until Ctrl-C)

Exit codes: 0 sessions found (or action ok), 1 none found, 2 usage/safety error.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time

AGENT_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("claude-code", re.compile(r"\bclaude\b(?!.*\bgrep\b)", re.I)),
    ("codex", re.compile(r"\bcodex\b", re.I)),
    ("omo", re.compile(r"\b(omo|senpi)\b", re.I)),
    ("gjc", re.compile(r"(gajae-code|gjc)", re.I)),
    ("hermes", re.compile(r"hermes", re.I)),
    ("opencode", re.compile(r"\bopencode\b", re.I)),
    ("aider", re.compile(r"\baider\b", re.I)),
    ("cursor", re.compile(r"cursor(?!.*grep)", re.I)),
    ("gemini-cli", re.compile(r"gemini", re.I)),
]

EXCLUDE = re.compile(r"(session_finder|grep|agent-skills|pytest)", re.I)


def detect(match_extra: str = "") -> list[dict]:
    p = subprocess.run(["ps", "-eo", "pid,ppid,etime,command"],
                       capture_output=True, text=True)
    sessions = []
    patterns = list(AGENT_PATTERNS)
    if match_extra:
        patterns.append(("custom", re.compile(match_extra, re.I)))
    for line in p.stdout.splitlines()[1:]:
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        pid, ppid, etime, cmd = parts[0], parts[1], parts[2], parts[3]
        if EXCLUDE.search(cmd):
            continue
        for client, pat in patterns:
            if pat.search(cmd):
                sessions.append({
                    "pid": int(pid), "ppid": int(ppid), "client": client,
                    "uptime": etime, "command": cmd[:200],
                })
                break
    return sessions


def summarize(sessions: list[dict]) -> dict:
    clients: dict[str, int] = {}
    for s in sessions:
        clients[s["client"]] = clients.get(s["client"], 0) + 1
    return {"count": len(sessions), "clients": clients, "sessions": sessions}


def is_agent_pid(pid: int) -> bool:
    return any(s["pid"] == pid for s in detect())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--match", default="", help="extra regex pattern to match")
    ap.add_argument("--kill", type=int, metavar="PID")
    ap.add_argument("--watch", type=int, default=0, metavar="SECS")
    args = ap.parse_args(argv)

    if args.kill:
        if not is_agent_pid(args.kill):
            print(f"refused: PID {args.kill} is not an agent process "
                  "(safe-kill only terminates detected AI agents)", file=sys.stderr)
            return 2
        os.kill(args.kill, signal.SIGTERM)
        print(f"SIGTERM sent to {args.kill}")
        return 0

    def scan_and_report() -> int:
        sessions = detect(args.match)
        report = summarize(sessions)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            if not sessions:
                print("no AI agent sessions running")
                return 1
            for s in sessions:
                print(f"{s['client']:<12} pid={s['pid']:<7} up={s['uptime']:<10} "
                      f"{s['command'][:60]}")
            print(f"\n{report['count']} session(s): "
                  + ", ".join(f"{k}={v}" for k, v in sorted(report["clients"].items())))
        return 0 if sessions else 1

    if args.watch:
        try:
            while True:
                scan_and_report()
                print(f"--- next scan in {args.watch}s (Ctrl-C to stop) ---")
                time.sleep(args.watch)
        except KeyboardInterrupt:
            return 0
    return scan_and_report()


if __name__ == "__main__":
    raise SystemExit(main())
