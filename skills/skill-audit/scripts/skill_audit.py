#!/usr/bin/env python3
"""skill-audit: security-scan third-party agent skills before trusting them.

A SKILL.md is executable authority: agents follow its instructions with your
credentials and filesystem. Skill marketplaces and sync tools install them
from strangers. This audit scans skill directories for prompt-injection
patterns (instruction overrides, concealment directives), data-exfiltration
signatures (sensitive paths piped to the network), and dangerous script
patterns (pipe-to-shell, eval-on-download) — offline, deterministic, stdlib.

It flags candidates for human review; a clean report is not proof of safety,
and a finding is not proof of malice. Read what it flags.

Usage:
    skill_audit.py SKILLS_DIR [SKILLS_DIR...]   # dirs containing skill subdirs
    skill_audit.py --skill DIR                  # audit one skill dir
    ... --json                                  # machine-readable
    ... --fail-over N                           # exit 1 when > N findings (default 0)

Exit codes: 0 clean/within budget, 1 findings over budget, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

INSTRUCTION_OVERRIDE = re.compile(
    r"(?i)\b(ignore|disregard|forget|override)\b.{0,40}\b(previous|prior|above|earlier|system)\b"
    r".{0,40}\b(instruction|prompt|rule|directive)s?\b")

CONCEALMENT = re.compile(
    r"(?i)\b(do not|don't|never|without)\b.{0,30}\b(tell|inform|notify|mention|reveal|show|alert)\b"
    r".{0,30}\b(the )?(user|human|owner)\b")

SENSITIVE_PATH = re.compile(
    r"(?i)(~/\.ssh|id_rsa|id_ed25519|\.aws/credentials|\.env\b|/etc/passwd|\.netrc"
    r"|\.gnupg|keychain|\.npmrc|\.pypirc|\.git-credentials|auth\.json|cookies)")

NETWORK_SEND = re.compile(
    r"(?i)\b(curl|wget|fetch|requests\.(?:post|put)|urlopen|httpx?|nc |netcat|POST )\b")

PIPE_TO_SHELL = re.compile(
    r"(?i)(curl|wget)\b[^\n|;&]{0,200}\|\s*(?:sudo\s+)?(?:ba|z|fi|da)?sh\b")

EVAL_DOWNLOAD = re.compile(
    r"(?i)\b(eval|exec)\s*\(\s*[^)]*\b(urlopen|requests\.get|fetch|download)")

ENCODED_BLOB = re.compile(r"(?:[A-Za-z0-9+/]{4}){20,}={0,2}")

CREDENTIAL_HARVEST = re.compile(
    r"(?i)\b(env|printenv|os\.environ|process\.env)\b.{0,60}"
    r"\b(curl|wget|post|send|upload|requests|fetch)\b")


def audit_text(text: str, skill: str, source: str) -> list[dict]:
    findings = []
    lines = text.splitlines()

    def hit(kind: str, line_no: int, evidence: str):
        findings.append({"skill": skill, "file": source, "line": line_no,
                         "kind": kind, "evidence": evidence.strip()[:140]})

    for i, line in enumerate(lines, 1):
        if INSTRUCTION_OVERRIDE.search(line):
            hit("instruction-override", i, line)
        if CONCEALMENT.search(line):
            hit("concealment", i, line)
        if SENSITIVE_PATH.search(line) and NETWORK_SEND.search(line):
            hit("sensitive-path-exfil", i, line)
        if PIPE_TO_SHELL.search(line):
            hit("pipe-to-shell", i, line)
        if EVAL_DOWNLOAD.search(line):
            hit("eval-on-download", i, line)
        if CREDENTIAL_HARVEST.search(line):
            hit("credential-harvest", i, line)
        m = ENCODED_BLOB.search(line)
        if m and len(m.group(0)) > 120 and "base64" not in source:
            hit("large-encoded-blob", i, m.group(0)[:40] + "...")
    window = 3
    for i in range(len(lines) - window):
        chunk = " ".join(lines[i:i + window + 1])
        if SENSITIVE_PATH.search(chunk) and NETWORK_SEND.search(chunk):
            if not any(f["kind"] == "sensitive-path-exfil" and abs(f["line"] - (i + 1)) <= window
                       for f in findings):
                hit("sensitive-path-exfil", i + 1, chunk)
    return findings


def audit_skill_dir(d: Path) -> list[dict]:
    findings = []
    for f in sorted(d.rglob("*")):
        if not f.is_file() or f.stat().st_size > 1_000_000:
            continue
        if f.suffix in (".png", ".jpg", ".gif", ".pdf", ".ttf", ".woff2", ".zip"):
            continue
        if "LICENSE" in f.name or "ATTRIBUTION" in f.name:
            continue
        findings.extend(audit_text(f.read_text(errors="replace"), d.name,
                                   str(f.relative_to(d.parent))))
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("dirs", nargs="*", help="directories containing skill subdirectories")
    ap.add_argument("--skill", action="append", default=[], help="audit one skill directory")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-over", type=int, default=0, metavar="N")
    args = ap.parse_args(argv)

    targets: list[Path] = [Path(s) for s in args.skill]
    for root in args.dirs:
        rp = Path(root)
        if not rp.is_dir():
            print(f"not a directory: {root}", file=sys.stderr)
            return 2
        targets.extend(sorted(d for d in rp.iterdir()
                              if d.is_dir() and (d / "SKILL.md").is_file()))
    if not targets:
        ap.error("no skill directories found; pass SKILLS_DIR or --skill DIR")

    findings = []
    for t in targets:
        findings.extend(audit_skill_dir(t))

    if args.json:
        print(json.dumps({"audited": len(targets), "findings": findings,
                          "count": len(findings)}, indent=2))
    else:
        for f in findings:
            print(f"{f['skill']} {f['file']}:{f['line']}: {f['kind']}: {f['evidence']}")
        print(f"\n{len(targets)} skill(s) audited, {len(findings)} finding(s) — "
              "review flagged lines; findings are candidates, not verdicts")
    return 1 if len(findings) > args.fail_over else 0


if __name__ == "__main__":
    raise SystemExit(main())
