#!/usr/bin/env python3
"""session-handoff: carry work context between AI agent clients.

Reads session logs from every installed agent client's native store (Claude
Code JSONL projects, Codex rollout JSONL, OpenCode SQLite, Gemini CLI chat
logs) and produces a portable handoff document, so a session started in one
client can pick up exactly what another client worked on: user asks, what was
done, files touched, and the last state of play.

Usage:
    session_handoff.py list [--cwd DIR] [--since DAYS] [--limit N] [--json]
    session_handoff.py show <session-ref> [--json] [--max-turns N]
    session_handoff.py handoff [--cwd DIR] [--since DAYS] [--sessions N]
                               [--out FILE] [--json]

A <session-ref> is "<provider>:<id-prefix>" from `list` output (e.g.
claude:a3f7e0b9 or codex:01a03b74 or opencode:ses_ffd87d).

`handoff` writes a markdown briefing of recent work (default: sessions
touching --cwd, newest first) that you paste or pipe into the current client.

Exit codes: 0 ok, 1 nothing found, 2 usage error.
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
CLAUDE_PROJECTS = HOME / ".claude" / "projects"
CODEX_SESSIONS = HOME / ".codex" / "sessions"
OPENCODE_DB = HOME / ".local" / "share" / "opencode" / "opencode.db"
GEMINI_TMP = HOME / ".gemini" / "tmp"

MAX_TEXT = 400


def _clip(s: str, n: int = MAX_TEXT) -> str:
    s = re.sub(r"\s+", " ", s).strip()
    return s[: n - 3] + "..." if len(s) > n else s


def _is_noise(text: str) -> bool:
    return text.startswith(("<local-command-caveat>", "<command-name>", "<command-message>",
                            "<local-command-stdout>", "Caveat: The messages below",
                            "Base directory for this skill:", "Stop hook feedback:",
                            "<system-reminder>", "[Request interrupted",
                            "<task-notification>", "<omo-senpi-task>", "Stop hook"))


def _block_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content
                        if isinstance(b, dict)
                        and b.get("type") in ("text", "input_text", "output_text"))
    return ""


def scan_claude(since: datetime) -> list[dict]:
    sessions = []
    if not CLAUDE_PROJECTS.is_dir():
        return sessions
    for proj in CLAUDE_PROJECTS.iterdir():
        if not proj.is_dir():
            continue
        for jl in proj.glob("*.jsonl"):
            mtime = datetime.fromtimestamp(jl.stat().st_mtime, tz=timezone.utc)
            if mtime < since:
                continue
            sessions.append({"provider": "claude", "id": jl.stem, "path": str(jl),
                             "mtime": mtime.isoformat(), "cwd": "",
                             "project": proj.name})
    return sessions


def read_claude(path: Path, max_turns: int) -> dict:
    turns, cwd, files = [], "", set()
    for ln in path.read_text(errors="replace").splitlines():
        try:
            d = json.loads(ln)
        except json.JSONDecodeError:
            continue
        t = d.get("type")
        if t == "user":
            cwd = d.get("cwd", cwd)
            txt = _block_text(d.get("message", {}).get("content"))
            if txt and not _is_noise(txt) and not txt.startswith("[Request interrupted"):
                turns.append(("user", _clip(txt), d.get("timestamp", "")[:19]))
        elif t == "assistant":
            content = d.get("message", {}).get("content", [])
            txt = _block_text(content)
            if isinstance(content, list):
                for b in content:
                    if isinstance(b, dict) and b.get("type") == "tool_use":
                        fp = (b.get("input") or {}).get("file_path") or (b.get("input") or {}).get("path")
                        if fp:
                            files.add(str(fp))
            if txt:
                turns.append(("assistant", _clip(txt), d.get("timestamp", "")[:19]))
    return {"cwd": cwd, "turns": turns[-max_turns:], "files": sorted(files)[:40],
            "total_turns": len(turns)}


def scan_codex(since: datetime) -> list[dict]:
    sessions = []
    if not CODEX_SESSIONS.is_dir():
        return sessions
    for jl in CODEX_SESSIONS.rglob("rollout-*.jsonl"):
        mtime = datetime.fromtimestamp(jl.stat().st_mtime, tz=timezone.utc)
        if mtime < since:
            continue
        sid = jl.stem.split("-")[-5:]
        sessions.append({"provider": "codex", "id": "-".join(sid), "path": str(jl),
                         "mtime": mtime.isoformat(), "cwd": "", "project": ""})
    return sessions


def read_codex(path: Path, max_turns: int) -> dict:
    turns, cwd, files = [], "", set()
    for ln in path.read_text(errors="replace").splitlines():
        try:
            d = json.loads(ln)
        except json.JSONDecodeError:
            continue
        pl = d.get("payload", {})
        pt = pl.get("type")
        if d.get("type") == "session_meta":
            cwd = pl.get("cwd", cwd)
        elif pt == "message":
            role = pl.get("role", "")
            txt = _block_text(pl.get("content"))
            if txt and role in ("user", "assistant") and not _is_noise(txt):
                turns.append((role, _clip(txt), d.get("timestamp", "")[:19]))
        elif pt == "function_call":
            try:
                args = json.loads(pl.get("arguments", "{}"))
                fp = args.get("file_path") or args.get("path")
                if fp:
                    files.add(str(fp))
            except json.JSONDecodeError:
                pass
    return {"cwd": cwd, "turns": turns[-max_turns:], "files": sorted(files)[:40],
            "total_turns": len(turns)}


def scan_opencode(since: datetime) -> list[dict]:
    sessions = []
    if not OPENCODE_DB.is_file():
        return sessions
    ts = int(since.timestamp() * 1000)
    try:
        con = sqlite3.connect(f"file:{OPENCODE_DB}?mode=ro", uri=True, timeout=5)
        rows = con.execute(
            "SELECT id, title, directory, time_updated FROM session "
            "WHERE time_updated > ? ORDER BY time_updated DESC", (ts,)).fetchall()
        con.close()
    except sqlite3.Error:
        return sessions
    for sid, title, directory, tu in rows:
        sessions.append({"provider": "opencode", "id": sid, "path": str(OPENCODE_DB),
                         "mtime": datetime.fromtimestamp(tu / 1000, tz=timezone.utc).isoformat(),
                         "cwd": directory or "", "project": title or ""})
    return sessions


def read_opencode(session_id: str, max_turns: int) -> dict:
    turns, cwd = [], ""
    try:
        con = sqlite3.connect(f"file:{OPENCODE_DB}?mode=ro", uri=True, timeout=5)
        srow = con.execute("SELECT directory, title FROM session WHERE id = ?",
                           (session_id,)).fetchone()
        rows = con.execute(
            "SELECT data, time_created FROM message WHERE session_id = ? ORDER BY time_created",
            (session_id,)).fetchall()
        prows = con.execute(
            "SELECT data FROM part WHERE session_id = ?", (session_id,)).fetchall()
        con.close()
    except sqlite3.Error:
        return {"cwd": "", "turns": [], "files": [], "total_turns": 0}
    cwd = srow[0] if srow else ""
    texts = {}
    files = set()
    for (pdata,) in prows:
        try:
            p = json.loads(pdata)
        except json.JSONDecodeError:
            continue
        if p.get("type") == "text" and p.get("text"):
            texts.setdefault(p.get("messageID"), []).append(p["text"])
        elif p.get("type") == "tool":
            fp = ((p.get("state") or {}).get("input") or {}).get("filePath") or \
                 ((p.get("state") or {}).get("input") or {}).get("path")
            if fp:
                files.add(str(fp))
    for (mdata, tc) in rows:
        try:
            m = json.loads(mdata)
        except json.JSONDecodeError:
            continue
        role = m.get("role", "")
        txt = " ".join(texts.get(m.get("id"), []))
        if txt and role in ("user", "assistant") and not _is_noise(txt):
            ts = datetime.fromtimestamp(tc / 1000, tz=timezone.utc).isoformat()[:19]
            turns.append((role, _clip(txt), ts))
    return {"cwd": cwd, "turns": turns[-max_turns:], "files": sorted(files)[:40],
            "total_turns": len(turns)}


def scan_gemini(since: datetime) -> list[dict]:
    sessions = []
    if not GEMINI_TMP.is_dir():
        return sessions
    for proj in GEMINI_TMP.iterdir():
        chats = proj / "chats"
        if not chats.is_dir():
            continue
        for f in chats.glob("*.json"):
            mtime = datetime.fromtimestamp(f.stat().st_mtime, tz=timezone.utc)
            if mtime < since:
                continue
            sessions.append({"provider": "gemini", "id": f.stem, "path": str(f),
                             "mtime": mtime.isoformat(), "cwd": "", "project": proj.name})
    return sessions


def read_gemini(path: Path, max_turns: int) -> dict:
    turns = []
    try:
        data = json.loads(path.read_text(errors="replace"))
    except json.JSONDecodeError:
        return {"cwd": "", "turns": [], "files": [], "total_turns": 0}
    msgs = data if isinstance(data, list) else data.get("messages", data.get("history", []))
    for m in msgs if isinstance(msgs, list) else []:
        if not isinstance(m, dict):
            continue
        role = m.get("role", m.get("type", ""))
        parts = m.get("parts", m.get("content", ""))
        txt = parts if isinstance(parts, str) else " ".join(
            p.get("text", "") if isinstance(p, dict) else str(p) for p in parts)
        if txt and role in ("user", "model", "assistant"):
            turns.append(("user" if role == "user" else "assistant", _clip(txt), ""))
    return {"cwd": "", "turns": turns[-max_turns:], "files": [], "total_turns": len(turns)}


SCANNERS = {"claude": scan_claude, "codex": scan_codex, "opencode": scan_opencode,
            "gemini": scan_gemini}


def discover(since_days: int) -> list[dict]:
    since = datetime.now(tz=timezone.utc) - timedelta(days=since_days)
    found = []
    for scanner in SCANNERS.values():
        found.extend(scanner(since))
    return sorted(found, key=lambda s: s["mtime"], reverse=True)


def read_session(sess: dict, max_turns: int) -> dict:
    p = sess["provider"]
    if p == "claude":
        return read_claude(Path(sess["path"]), max_turns)
    if p == "codex":
        return read_codex(Path(sess["path"]), max_turns)
    if p == "opencode":
        return read_opencode(sess["id"], max_turns)
    return read_gemini(Path(sess["path"]), max_turns)


def match_cwd(sess: dict, detail: dict, cwd: str) -> bool:
    if not cwd:
        return True
    def norm(p: str) -> str:
        rp = Path(p)
        try:
            return str(rp.resolve()) if rp.exists() else str(rp.absolute())
        except OSError:
            return p
    target = norm(cwd)
    scwd = detail.get("cwd") or sess.get("cwd") or ""
    if scwd:
        scwd = norm(scwd)
        if scwd == target or scwd.startswith(target + "/"):
            return True
    proj_slug = sess.get("project", "")
    return bool(proj_slug) and target.replace("/", "-") in proj_slug


def cmd_list(args) -> int:
    sessions = discover(args.since)
    rows = []
    for s in sessions:
        if len(rows) >= args.limit * 3 and not args.cwd:
            break
        detail = read_session(s, 1) if args.cwd else {}
        if args.cwd and not match_cwd(s, detail, args.cwd):
            continue
        rows.append(s | {"cwd": (detail.get("cwd") or s.get("cwd", ""))})
        if len(rows) >= args.limit:
            break
    if args.json:
        print(json.dumps(rows, indent=2))
    else:
        for s in rows:
            label = s["cwd"] or s["project"]
            print(f"{s['provider']}:{s['id'][:12]}  {s['mtime'][:16]}  {label[-50:]}")
        print(f"\n{len(rows)} session(s) shown (use 'show <provider>:<id-prefix>')")
    return 0 if rows else 1


def _resolve(ref: str) -> dict | None:
    if ":" not in ref:
        return None
    prov, prefix = ref.split(":", 1)
    for s in discover(365):
        if s["provider"] == prov and s["id"].startswith(prefix):
            return s
    return None


def cmd_show(args) -> int:
    sess = _resolve(args.ref)
    if not sess:
        print(f"session not found: {args.ref}", file=sys.stderr)
        return 1
    detail = read_session(sess, args.max_turns)
    if args.json:
        print(json.dumps(sess | detail, indent=2))
        return 0
    print(f"# {sess['provider']}:{sess['id']}")
    print(f"updated: {sess['mtime']}  cwd: {detail['cwd'] or sess['project']}")
    print(f"turns: {detail['total_turns']}  files touched: {len(detail['files'])}\n")
    for role, txt, ts in detail["turns"]:
        print(f"[{role} {ts}] {txt}\n")
    if detail["files"]:
        print("## Files touched")
        for f in detail["files"]:
            print(f"- {f}")
    return 0


def cmd_handoff(args) -> int:
    sessions = discover(args.since)
    picked = []
    for s in sessions:
        detail = read_session(s, args.max_turns)
        if not detail["turns"]:
            continue
        if args.cwd and not match_cwd(s, detail, args.cwd):
            continue
        picked.append((s, detail))
        if len(picked) >= args.sessions:
            break
    if not picked:
        print("no sessions with content found", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps([s | d for s, d in picked], indent=2))
        return 0
    lines = ["# Session Handoff", "",
             f"Generated {datetime.now(tz=timezone.utc).isoformat()[:19]}Z; "
             f"{len(picked)} recent session(s)"
             + (f" for {args.cwd}" if args.cwd else "") + ".", "",
             "Paste this into your current agent client to continue the work below.", ""]
    for s, d in picked:
        lines.append(f"## {s['provider']}:{s['id'][:12]} ({s['mtime'][:16]})")
        lines.append(f"- workdir: `{d['cwd'] or s['project'] or 'unknown'}`")
        lines.append(f"- {d['total_turns']} conversation turns")
        user_asks = [t for r, t, _ in d["turns"] if r == "user"][:5]
        if user_asks:
            lines.append("- what was asked:")
            lines.extend(f"  - {a}" for a in user_asks)
        last_asst = next((t for r, t, _ in reversed(d["turns"]) if r == "assistant"), "")
        if last_asst:
            lines.append(f"- last assistant state: {last_asst}")
        if d["files"]:
            lines.append(f"- files touched: {', '.join(f'`{f}`' for f in d['files'][:12])}")
        lines.append("")
    doc = "\n".join(lines)
    if args.out:
        Path(args.out).write_text(doc)
        print(f"handoff written: {args.out} ({len(doc)} chars, {len(picked)} sessions)")
    else:
        print(doc)
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    lp = sub.add_parser("list")
    lp.add_argument("--cwd", default="")
    lp.add_argument("--since", type=int, default=7, metavar="DAYS")
    lp.add_argument("--limit", type=int, default=20)
    lp.add_argument("--json", action="store_true")
    sp = sub.add_parser("show")
    sp.add_argument("ref")
    sp.add_argument("--json", action="store_true")
    sp.add_argument("--max-turns", type=int, default=30)
    hp = sub.add_parser("handoff")
    hp.add_argument("--cwd", default="")
    hp.add_argument("--since", type=int, default=3, metavar="DAYS")
    hp.add_argument("--sessions", type=int, default=5)
    hp.add_argument("--max-turns", type=int, default=30)
    hp.add_argument("--out", default="")
    hp.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)
    return {"list": cmd_list, "show": cmd_show, "handoff": cmd_handoff}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
