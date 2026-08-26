#!/usr/bin/env python3
"""session-rules: turn "the user already corrected this" into a RULE.md that prevents it.

Reads a project's AI-session history (same local stores as session-handoff)
and extracts the moments where the human corrected the agent — "no, never do
X", "don't do that again", "we use Y not Z", "always run tests first" —
then writes a RULE.md the next agent session reads before touching the repo.
The highest-leverage context file a project can have is the one generated
from its own history of mistakes.

Usage:
    session_rules.py --cwd /path/to/project [--since DAYS]
    session_rules.py --cwd . --out RULE.md
    session_rules.py --cwd . --json

Extraction is heuristic: it looks for user turns carrying correction signals
(negations, "don't/never/always/stop", "we use X not Y", "you did that wrong")
and keeps the sentence(s) containing the rule. Review the output before
committing RULE.md — corrections are project law, extraction is a draft.

Exit codes: 0 rules written, 1 no corrections found, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

HOME = Path.home()

CORRECTION = re.compile(
    r"(?i)\b(no,?\s+(never|don't|do not)|don't (do that|use|ever)|never (use|add|do|write)|"
    r"we (use|prefer|always|never)|you (should|must|need to) (always|never)|"
    r"stop (doing|using|adding)|that's wrong|not like that|"
    r"always (run|use|write|check|verify)|from now on)\b")

FILLER = re.compile(
    r"(?i)^(ok|okay|sure|thanks|yes|no|nope|correct|right|go ahead|continue|lgtm)\.?\s*$")


def clean_text(t: str) -> str:
    return re.sub(r"\s+", " ", t).strip()


def claude_user_turns(since: datetime, cwd: str) -> list[str]:
    out = []
    projects = HOME / ".claude" / "projects"
    if not projects.is_dir():
        return out
    target = str(Path(cwd).resolve())
    target_alt = target.replace("/private/", "/", 1) if target.startswith("/private/") else target
    target_slugs = {t.lstrip("/").replace("/", "-") for t in (target, target_alt)}
    for proj in projects.iterdir():
        if proj.name.lstrip("-") not in target_slugs:
            continue
        for jl in proj.glob("*.jsonl"):
            if datetime.fromtimestamp(jl.stat().st_mtime, tz=timezone.utc) < since:
                continue
            for ln in jl.read_text(errors="replace").splitlines():
                try:
                    d = json.loads(ln)
                except json.JSONDecodeError:
                    continue
                if d.get("type") != "user":
                    continue
                if d.get("cwd") and not _cwd_matches(d["cwd"], target):
                    continue
                c = d.get("message", {}).get("content")
                text = c if isinstance(c, str) else " ".join(
                    b.get("text", "") for b in c
                    if isinstance(b, dict) and b.get("type") == "text")
                if text:
                    out.append(text)
    return out


def _cwd_matches(session_cwd: str, target: str) -> bool:
    try:
        scwd = str(Path(session_cwd).resolve())
    except OSError:
        scwd = session_cwd
    return scwd == target or scwd.startswith(target + "/")


def codex_user_turns(since: datetime, cwd: str) -> list[str]:
    out = []
    sessions = HOME / ".codex" / "sessions"
    if not sessions.is_dir():
        return out
    target = str(Path(cwd).resolve())
    for jl in sessions.rglob("rollout-*.jsonl"):
        if datetime.fromtimestamp(jl.stat().st_mtime, tz=timezone.utc) < since:
            continue
        sess_cwd = ""
        turns = []
        for ln in jl.read_text(errors="replace").splitlines():
            try:
                d = json.loads(ln)
            except json.JSONDecodeError:
                continue
            pl = d.get("payload", {})
            if d.get("type") == "session_meta":
                sess_cwd = pl.get("cwd", "")
            elif pl.get("type") == "message" and pl.get("role") == "user":
                c = pl.get("content")
                text = c if isinstance(c, str) else " ".join(
                    b.get("text", "") for b in c
                    if isinstance(b, dict) and b.get("type") in ("text", "input_text"))
                if text:
                    turns.append(text)
        if sess_cwd and _cwd_matches(sess_cwd, target):
            out.extend(turns)
    return out


def opencode_user_turns(since: datetime, cwd: str) -> list[str]:
    out = []
    db = HOME / ".local" / "share" / "opencode" / "opencode.db"
    if not db.is_file():
        return out
    target = str(Path(cwd).resolve())
    ts = int(since.timestamp() * 1000)
    try:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True, timeout=5)
        sids = [r[0] for r in con.execute(
            "SELECT id FROM session WHERE time_updated > ? AND (directory = ? OR directory LIKE ?)",
            (ts, target, target + "/%")).fetchall()]
        for sid in sids:
            for (data,) in con.execute(
                    "SELECT data FROM message WHERE session_id = ?", (sid,)).fetchall():
                try:
                    m = json.loads(data)
                except json.JSONDecodeError:
                    continue
                if m.get("role") != "user":
                    continue
                parts = con.execute(
                    "SELECT data FROM part WHERE message_id = ?", (m.get("id"),)).fetchall()
                for (pdata,) in parts:
                    try:
                        p = json.loads(pdata)
                    except json.JSONDecodeError:
                        continue
                    if p.get("type") == "text" and p.get("text"):
                        out.append(p["text"])
        con.close()
    except sqlite3.Error:
        pass
    return out


def extract_rules(turns: list[str]) -> list[dict]:
    rules = []
    seen = set()
    for text in turns:
        text = clean_text(text)
        if FILLER.match(text) or len(text) < 15:
            continue
        sentences = re.split(r"(?<=[.!?])\s+", text)
        hit = False
        for s in sentences:
            if CORRECTION.search(s):
                hit = True
                key = s.lower()[:60]
                if key in seen:
                    continue
                seen.add(key)
                rules.append({"rule": s.strip(), "source": text[:200]})
        if not hit and CORRECTION.search(text) and len(text) < 300:
            key = text.lower()[:60]
            if key not in seen:
                seen.add(key)
                rules.append({"rule": text, "source": text[:200]})
    return rules


def render(rules: list[dict], cwd: str, sessions: int) -> str:
    lines = ["# Project Rules", "",
             f"Extracted from {sessions} session(s) of AI-agent work in `{cwd}`.",
             "Each rule is a place where the human corrected the agent —",
             "read this before making changes in this project.", "",
             "## Rules", ""]
    for i, r in enumerate(rules, 1):
        lines.append(f"{i}. {r['rule']}")
    lines += ["", "## Evidence", "",
              "Corrections these rules came from (verbatim user turns):", ""]
    for i, r in enumerate(rules, 1):
        lines.append(f"{i}. > {r['source']}")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cwd", default=".")
    ap.add_argument("--since", type=int, default=90, metavar="DAYS")
    ap.add_argument("--out", default="")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    cwd = str(Path(args.cwd).resolve())
    since = datetime.now(tz=timezone.utc) - timedelta(days=args.since)
    turns = (claude_user_turns(since, cwd) + codex_user_turns(since, cwd)
             + opencode_user_turns(since, cwd))
    rules = extract_rules(turns)
    sessions_scanned = 1 if turns else 0

    result = {"cwd": cwd, "user_turns": len(turns), "rules": rules,
              "sessions_scanned": sessions_scanned}
    if args.json:
        print(json.dumps(result, indent=2))
    elif rules:
        doc = render(rules, cwd, sessions_scanned)
        if args.out:
            Path(args.out).write_text(doc)
            print(f"RULE.md written: {args.out} ({len(rules)} rules from "
                  f"{len(turns)} user turns)")
        else:
            print(doc)
    if not rules:
        if not args.json:
            print("no corrections found in session history for this project",
                  file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
