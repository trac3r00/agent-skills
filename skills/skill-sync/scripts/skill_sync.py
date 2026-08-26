#!/usr/bin/env python3
"""skill-sync: discover skills across AI provider installs, unify for universal use.

Scans the local skill directories of every known agent provider (Claude Code,
Codex, OMO, gjc, OpenCode, Gemini, Cursor, Factory, plugin caches, ...) for
SKILL.md-based skills, dedupes them by resolved path and name, and can sync
them into one universal directory (default ~/.agents/skills) via symlinks so
any agent reads one location and every skill stays a single source of truth.

Usage:
    skill_sync.py list [--json]              # inventory with provenance
    skill_sync.py sync [--target DIR] [--copy] [--dry-run] [--json]
    skill_sync.py doctor                     # show which provider roots exist

Common flags:
    --root DIR       extra scan root (repeatable)
    --exclude NAME   skip a skill by name (repeatable)
    --fail-on-conflict   exit 1 when two providers ship different skills
                         under the same name (default: highest-priority wins)

Exit codes: 0 ok, 1 gate failure (--fail-on-conflict), 2 usage error.
"""

from __future__ import annotations

import argparse
import glob
import json
import re
import shutil
import sys
from pathlib import Path

HOME = Path.home()

PROVIDER_ROOTS: list[tuple[str, str]] = [
    ("agents", str(HOME / ".agents/skills")),
    ("claude", str(HOME / ".claude/skills")),
    ("codex", str(HOME / ".codex/skills")),
    ("omo", str(HOME / ".omo/skills")),
    ("omo-plugin", "/opt/homebrew/lib/node_modules/omo-ai/plugin/skills"),
    ("omo-plugin", "/usr/local/lib/node_modules/omo-ai/plugin/skills"),
    ("gjc", str(HOME / ".gjc/skills")),
    ("opencode", str(HOME / ".config/opencode/skills")),
    ("gemini", str(HOME / ".gemini/skills")),
    ("cursor", str(HOME / ".cursor/skills")),
    ("factory", str(HOME / ".factory/skills")),
    ("claude-plugins", str(HOME / ".claude/plugins/cache/*/*/*/skills")),
]

FM_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def _natural_desc(path: str) -> list:
    """Sort key: numeric segments compared numerically, descending (newest version first)."""
    return [(-int(t), "") if t.isdigit() else (0, t) for t in re.split(r"(\d+)", path)]


def parse_frontmatter(text: str) -> dict[str, str]:
    m = FM_RE.match(text)
    if not m:
        return {}
    out: dict[str, str] = {}
    for line in m.group(1).splitlines():
        km = re.match(r"^(name|description|version|license):\s*(.+?)\s*$", line)
        if km:
            out[km.group(1)] = km.group(2)
    return out


def discover(extra_roots: list[str], exclude: set[str],
             defaults: bool = True) -> tuple[list[dict], list[dict]]:
    """Returns (skills, conflicts). Priority order dedupes; realpath dedupes symlinks."""
    seen_paths: set[str] = set()
    by_name: dict[str, dict] = {}
    conflicts: list[dict] = []
    roots = [("custom", r) for r in extra_roots] + (PROVIDER_ROOTS if defaults else [])
    for provider, pattern in roots:
        for root in sorted(glob.glob(str(Path(pattern).expanduser())), key=_natural_desc):
            rootp = Path(root)
            if not rootp.is_dir():
                continue
            for sk in sorted(rootp.iterdir()):
                md = sk / "SKILL.md"
                if not md.is_file():
                    continue
                real = str(sk.resolve())
                fm = parse_frontmatter(md.read_text(errors="replace"))
                name = fm.get("name", sk.name)
                if name in exclude:
                    continue
                entry = {
                    "name": name,
                    "provider": provider,
                    "path": str(sk),
                    "realpath": real,
                    "description": fm.get("description", "")[:200],
                    "version": fm.get("version", ""),
                }
                if real in seen_paths:
                    continue
                seen_paths.add(real)
                if name in by_name:
                    conflicts.append({"name": name, "kept": by_name[name]["path"],
                                      "shadowed": str(sk), "provider": provider})
                    continue
                by_name[name] = entry
    return sorted(by_name.values(), key=lambda e: e["name"]), conflicts


def cmd_list(args: argparse.Namespace) -> int:
    skills, conflicts = discover(args.root, set(args.exclude), not args.no_default_roots)
    if args.json:
        print(json.dumps({"skills": skills, "conflicts": conflicts}, indent=2))
    else:
        width = max((len(s["name"]) for s in skills), default=4)
        for s in skills:
            print(f"{s['name']:<{width}}  [{s['provider']}]  {s['description'][:80]}")
        print(f"\n{len(skills)} skills from "
              f"{len(set(s['provider'] for s in skills))} providers; "
              f"{len(conflicts)} name conflict(s)")
        for c in conflicts:
            print(f"  conflict: {c['name']} — kept {c['kept']}, shadowed {c['shadowed']}")
    return 1 if (args.fail_on_conflict and conflicts) else 0


def cmd_sync(args: argparse.Namespace) -> int:
    target = Path(args.target).expanduser()
    skills, conflicts = discover(args.root, set(args.exclude), not args.no_default_roots)
    if args.fail_on_conflict and conflicts:
        for c in conflicts:
            print(f"conflict: {c['name']}: {c['kept']} vs {c['shadowed']}", file=sys.stderr)
        return 1
    target.mkdir(parents=True, exist_ok=True)
    target_real = str(target.resolve())
    actions = []
    for s in skills:
        if s["realpath"].startswith(target_real + "/") or s["realpath"] == target_real:
            actions.append({"name": s["name"], "action": "already-universal"})
            continue
        dest = target / s["name"]
        if dest.is_symlink() or dest.exists():
            if str(dest.resolve()) == s["realpath"]:
                actions.append({"name": s["name"], "action": "up-to-date"})
                continue
            actions.append({"name": s["name"], "action": "skip-exists", "dest": str(dest)})
            continue
        actions.append({"name": s["name"], "action": "copy" if args.copy else "link",
                        "src": s["path"], "dest": str(dest)})
        if not args.dry_run:
            if args.copy:
                shutil.copytree(s["realpath"], dest)
            else:
                dest.symlink_to(s["realpath"])
    if args.json:
        print(json.dumps({"target": str(target), "dry_run": args.dry_run,
                          "actions": actions}, indent=2))
    else:
        counts: dict[str, int] = {}
        for a in actions:
            counts[a["action"]] = counts.get(a["action"], 0) + 1
            if a["action"] in ("link", "copy", "skip-exists"):
                print(f"{a['action']:<14} {a['name']}")
        print(f"\ntarget: {target}  " + "  ".join(f"{k}={v}" for k, v in sorted(counts.items()))
              + ("  (dry run)" if args.dry_run else ""))
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    roots = [("custom", r) for r in args.root] + (
        [] if args.no_default_roots else PROVIDER_ROOTS)
    for provider, pattern in roots:
        matches = [m for m in glob.glob(str(Path(pattern).expanduser())) if Path(m).is_dir()]
        for m in matches:
            n = sum(1 for d in Path(m).iterdir() if (d / "SKILL.md").is_file())
            print(f"FOUND  [{provider:<14}] {m}  ({n} skills)")
        if not matches:
            print(f"absent [{provider:<14}] {pattern}")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--root", action="append", default=[])
    common.add_argument("--exclude", action="append", default=[])
    common.add_argument("--json", action="store_true")
    common.add_argument("--fail-on-conflict", action="store_true")
    common.add_argument("--no-default-roots", action="store_true")
    sub.add_parser("list", parents=[common])
    sp = sub.add_parser("sync", parents=[common])
    sp.add_argument("--target", default=str(HOME / ".agents/skills"))
    sp.add_argument("--copy", action="store_true")
    sp.add_argument("--dry-run", action="store_true")
    sub.add_parser("doctor", parents=[common])
    args = ap.parse_args(argv)
    return {"list": cmd_list, "sync": cmd_sync, "doctor": cmd_doctor}[args.cmd](args)


if __name__ == "__main__":
    raise SystemExit(main())
