#!/usr/bin/env python3
"""env-gate: stop broken deploys from .env drift before they ship.

The backend incident shape: a new key lands in .env.example, somebody deploys
without adding it to the deployed .env, and the crash surfaces in production
logs. This gate diffs the two files: which required keys are missing from the
deployed env, which required keys exist but are empty, and which stale keys
linger in the deployed env that the example no longer declares. Also flags
placeholder values left in the deployed file. Offline, stdlib-only.

Usage:
    env_gate.py .env --example .env.example            # the classic check
    env_gate.py .env --example .env.example --json
    env_gate.py .env.production --example .env.example --required-prefix DATABASE --required-prefix REDIS
    env_gate.py .env --example .env.example --ignore-extra   # deployed extras are fine

Key semantics: a key with a non-placeholder value in the example is "required
with default" (its value is documented); a key with an EMPTY value in the
example is "required, caller must supply". A deployed key counts as satisfied
when present with a non-empty value. --required-prefix restricts the missing/
empty checks to keys starting with the prefix (repeatable).

Exit codes: 0 clean, 1 drift found, 2 usage/input error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

PLACEHOLDER = re.compile(r"(?i)^(<[^>]*>|\$\{[^}]*\}|your[_-].*|change.*me|xxx+|todo|placeholder|example.*|replace.*)$")

COMMENT = re.compile(r"^\s*(#|$)")
ENTRY = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_.]*)\s*=\s*(.*)$")


def parse_env(path: Path) -> tuple[dict[str, str], str | None]:
    if not path.is_file():
        return {}, f"missing file: {path}"
    out = {}
    try:
        lines = path.read_text(errors="replace").splitlines()
    except OSError as exc:
        return {}, f"unreadable: {path}: {exc}"
    for i, line in enumerate(lines, 1):
        if COMMENT.match(line):
            continue
        m = ENTRY.match(line)
        if not m:
            continue
        key, raw = m.group(1), m.group(2).strip()
        if len(raw) >= 2 and raw[0] in "\"'" and raw[-1] == raw[0]:
            raw = raw[1:-1]
        out[key] = raw
    return out, None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("env_file")
    ap.add_argument("--example", required=True)
    ap.add_argument("--required-prefix", action="append", default=[], metavar="PREFIX")
    ap.add_argument("--ignore-extra", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    deployed, err = parse_env(Path(args.env_file))
    if err:
        print(err, file=sys.stderr)
        return 2
    example, err = parse_env(Path(args.example))
    if err:
        print(err, file=sys.stderr)
        return 2

    def in_scope(key: str) -> bool:
        return not args.required_prefix or any(
            key.startswith(p) for p in args.required_prefix)

    missing = sorted(({"key": k, "declared_default": example[k]}
                      for k in example if k not in deployed and in_scope(k)),
                     key=lambda d: d["key"])
    empty_required = sorted(({"key": k} for k in example
                             if k in deployed and not deployed[k].strip()
                             and in_scope(k)), key=lambda d: d["key"])
    placeholder = sorted(({"key": k, "value": deployed[k]} for k in example
                          if k in deployed and PLACEHOLDER.match(deployed[k].strip())),
                         key=lambda d: d["key"])
    extra = sorted(({"key": k} for k in deployed if k not in example),
                   key=lambda d: d["key"])

    problems = missing or empty_required or placeholder
    status = "clean" if not problems and (not extra or args.ignore_extra) else "drift"
    rc = 1 if problems or (extra and not args.ignore_extra) else 0

    if args.json:
        print(json.dumps({
            "status": status, "env_file": args.env_file, "example": args.example,
            "deployed_keys": len(deployed), "example_keys": len(example),
            "missing": missing, "empty_required": empty_required,
            "placeholder": placeholder,
            "extra": [] if args.ignore_extra else extra,
            "scope_prefixes": args.required_prefix,
        }, indent=2))
    else:
        for k in missing:
            print(f"MISSING   {k['key']}  (declared in example, not in {args.env_file})")
        for k in empty_required:
            print(f"EMPTY     {k['key']}  (present but no value)")
        for k in placeholder:
            print(f"PLACEHOLDER {k['key']} = {k['value']}")
        if not args.ignore_extra:
            for k in extra:
                print(f"EXTRA     {k['key']}  (deployed, not declared in example)")
        print(f"\n{status}: {len(deployed)} deployed vs {len(example)} declared "
              f"({len(missing)} missing, {len(empty_required)} empty, "
              f"{len(placeholder)} placeholder, {len(extra)} extra)")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
