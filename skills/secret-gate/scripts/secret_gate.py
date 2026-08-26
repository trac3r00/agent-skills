#!/usr/bin/env python3
"""secret-gate: block credentials from entering code, diffs, or agent output.

Agents paste keys into examples, commit .env values, and echo tokens into
logs. This gate scans files or a unified diff for known credential formats
(AWS, GitHub, OpenAI/Anthropic-style, Slack, GCP, private keys, JWTs,
assigned passwords) plus high-entropy assigned strings, entirely offline with
the standard library — no gitleaks binary, no network.

Usage:
    secret_gate.py FILE [FILE...]            # scan files
    git diff | secret_gate.py --diff         # scan only added lines
    ... --json                               # machine-readable
    ... --allow PATTERN                      # extra allowlist regex (repeatable)

Suppress a known-safe line with an inline `gitleaks:allow` or
`secret-gate:allow` comment.

Exit codes: 0 clean, 1 findings, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

RULES: list[tuple[str, re.Pattern]] = [
    ("aws-access-key", re.compile(r"\b(?:AKIA|ASIA|ABIA|ACCA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_]{20,255}\b")),
    ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b")),
    ("anthropic-key", re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("gcp-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("private-key-block", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA |PGP )?PRIVATE KEY(?: BLOCK)?-----")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    ("assigned-password", re.compile(
        r"""(?i)\b(?:password|passwd|pwd|secret|api_key|apikey|auth_token|access_token)\b"""
        r"""\s*[:=]\s*["']([^"'\s]{8,})["']""")),
]

ASSIGNED_STRING = re.compile(
    r"""(?i)\b(?:[A-Z0-9_]*(?:secret|token|key|credential)[A-Z0-9_]*)\s*[:=]\s*["']([A-Za-z0-9+/=_-]{24,})["']""")

ALLOW_MARKERS = ("gitleaks:allow", "secret-gate:allow", "pragma: allowlist secret")

PLACEHOLDER = re.compile(
    r"(?i)(example|sample|placeholder|your[_-]?|xxx|redacted|changeme|dummy|<[^>]+>|\$\{|%s|\{\})")


def entropy(s: str) -> float:
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    return -sum((n / len(s)) * math.log2(n / len(s)) for n in freq.values())


def scan_line(line: str, path: str, line_no: int, allows: list[re.Pattern]) -> list[dict]:
    if any(m in line for m in ALLOW_MARKERS):
        return []
    if any(a.search(line) for a in allows):
        return []
    findings = []
    for kind, rx in RULES:
        for m in rx.finditer(line):
            token = m.group(1) if m.groups() else m.group(0)
            if PLACEHOLDER.search(token):
                continue
            findings.append({"file": path, "line": line_no, "kind": kind,
                             "match": token[:6] + "..." + token[-4:] if len(token) > 14 else token})
    if not findings:
        for m in ASSIGNED_STRING.finditer(line):
            token = m.group(1)
            if PLACEHOLDER.search(token) or entropy(token) < 4.0:
                continue
            findings.append({"file": path, "line": line_no, "kind": "high-entropy",
                             "match": token[:6] + "..." + token[-4:]})
    return findings


def scan_file(path: Path, allows: list[re.Pattern]) -> list[dict]:
    findings = []
    try:
        text = path.read_text(errors="replace")
    except OSError as exc:
        print(f"unreadable: {path}: {exc}", file=sys.stderr)
        return findings
    for i, line in enumerate(text.splitlines(), 1):
        findings.extend(scan_line(line, str(path), i, allows))
    return findings


def scan_diff(diff: str, allows: list[re.Pattern]) -> list[dict]:
    findings, current, new_line = [], "", 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            current = re.sub(r"^\+\+\+ [ab]/", "", raw).strip()
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            new_line = int(m.group(1)) - 1 if m else 0
        elif raw.startswith("+") and not raw.startswith("+++"):
            new_line += 1
            findings.extend(scan_line(raw[1:], current, new_line, allows))
        elif not raw.startswith("-"):
            new_line += 1
    return findings


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--diff", action="store_true", help="read a unified diff from stdin")
    ap.add_argument("--allow", action="append", default=[], metavar="REGEX")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    try:
        allows = [re.compile(a) for a in args.allow]
    except re.error as exc:
        print(f"bad --allow regex: {exc}", file=sys.stderr)
        return 2

    if args.diff:
        findings = scan_diff(sys.stdin.read(), allows)
    elif args.files:
        findings = []
        for f in args.files:
            p = Path(f)
            if p.is_dir():
                for sub in sorted(p.rglob("*")):
                    if sub.is_file() and sub.stat().st_size < 1_000_000:
                        findings.extend(scan_file(sub, allows))
            else:
                findings.extend(scan_file(p, allows))
    else:
        ap.error("pass FILE arguments or --diff with stdin")

    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings)}, indent=2))
    else:
        for h in findings:
            print(f"{h['file']}:{h['line']}: {h['kind']}: {h['match']}")
        print(f"\n{len(findings)} potential secret(s) found")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
