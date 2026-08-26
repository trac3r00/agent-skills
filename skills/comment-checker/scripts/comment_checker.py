#!/usr/bin/env python3
"""comment-checker: flag new comments/docstrings in a diff so agents justify or remove them.

Detection patterns and allow-filters adapted from oh-my-opencode's
comment-checker hook (MIT). Re-implemented as a standalone CLI so any agent or
CI can enforce the same discipline: new comments must be justified (BDD, lint
directives, licenses, TODO markers pass automatically), the rest are reported
and can gate with a non-zero exit.

Usage:
    comment_checker.py FILE [FILE...]        # scan whole files
    git diff | comment_checker.py --diff     # scan only added lines
    comment_checker.py --diff < changes.patch
    ... --json                               # machine-readable
    ... --fail-over N                        # exit 1 when > N flagged (default: never fail)

Exit codes: 0 ok, 1 gate failure, 2 usage error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BDD_KEYWORDS = {"given", "when", "then", "arrange", "act", "assert", "when & then", "when&then"}

DIRECTIVE_PREFIXES = [
    "type:", "noqa", "pyright:", "ruff:", "mypy:", "pylint:", "flake8:", "pyre:", "pytype:",
    "eslint-disable", "eslint-enable", "eslint-ignore", "prettier-ignore",
    "ts-ignore", "ts-expect-error", "ts-nocheck", "@ts-ignore", "@ts-expect-error", "@ts-nocheck",
    "clippy::", "allow(", "deny(", "warn(", "forbid(",
    "nolint", "go:generate", "go:build", "go:embed",
    "coverage:", "c8 ignore", "istanbul ignore", "biome-ignore",
    "region", "endregion", "#region", "#endregion",
]

COPYRIGHT_MARKERS = [
    "copyright", "license", "licensed under", "spdx-license-identifier",
    "all rights reserved", "mit license", "apache license", "gnu general public", "bsd license",
]

TODO_MARKERS = ["TODO", "FIXME", "HACK", "XXX", "NOTE", "REVIEW"]

C_STYLE = r"//(?P<c1>.*)$|/\*(?P<c2>[\s\S]*?)\*/"
LANG_PATTERNS: dict[str, str] = {
    "js": C_STYLE, "ts": C_STYLE, "jsx": C_STYLE, "tsx": C_STYLE, "java": C_STYLE,
    "c": C_STYLE, "cpp": C_STYLE, "cs": C_STYLE, "rust": C_STYLE, "swift": C_STYLE,
    "kotlin": C_STYLE, "go": r"//(?P<c1>.*)$",
    "py": r"#(?P<c1>.*)$|'''(?P<c2>[\s\S]*?)'''|\"\"\"(?P<c3>[\s\S]*?)\"\"\"",
    "rb": r"#(?P<c1>.*)$", "sh": r"#(?P<c1>.*)$", "bash": r"#(?P<c1>.*)$", "zsh": r"#(?P<c1>.*)$",
    "yaml": r"#(?P<c1>.*)$", "toml": r"#(?P<c1>.*)$",
    "html": r"<!--(?P<c1>[\s\S]*?)-->", "xml": r"<!--(?P<c1>[\s\S]*?)-->",
    "sql": r"--(?P<c1>.*)$", "lua": r"--(?P<c1>.*)$",
}

EXT_TO_LANG = {
    ".js": "js", ".mjs": "js", ".cjs": "js", ".ts": "ts", ".mts": "ts", ".cts": "ts",
    ".jsx": "jsx", ".tsx": "tsx", ".java": "java", ".c": "c", ".h": "c",
    ".cpp": "cpp", ".cc": "cpp", ".cxx": "cpp", ".hpp": "cpp", ".cs": "cs", ".go": "go",
    ".rs": "rust", ".swift": "swift", ".kt": "kotlin", ".kts": "kotlin",
    ".py": "py", ".pyi": "py", ".rb": "rb", ".sh": "sh", ".bash": "bash", ".zsh": "zsh",
    ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".html": "html", ".htm": "html",
    ".xml": "xml", ".sql": "sql", ".lua": "lua",
}


def allowed(text: str, line_no: int) -> str | None:
    t = text.strip()
    low = t.lower()
    if t.startswith("!") and line_no <= 1:
        return "shebang"
    for kw in BDD_KEYWORDS:
        if low.startswith(kw) or f" {kw} " in f" {low} ":
            return f"bdd:{kw}"
    for p in DIRECTIVE_PREFIXES:
        if p.lower() in low:
            return f"directive:{p}"
    for m in COPYRIGHT_MARKERS:
        if m in low:
            return "copyright"
    up = t.upper()
    for m in TODO_MARKERS:
        if m in up:
            return f"todo:{m}"
    return None


def scan_text(text: str, lang: str, path: str, line_offset: int = 0) -> list[dict]:
    pattern = LANG_PATTERNS.get(lang)
    if not pattern:
        return []
    flagged = []
    rx = re.compile(pattern, re.M)
    for m in rx.finditer(text):
        body = next((g for g in m.groups() if g), "")
        line_no = text[: m.start()].count("\n") + 1 + line_offset
        if not body.strip():
            continue
        if allowed(body, line_no):
            continue
        flagged.append({
            "file": path, "line": line_no,
            "text": body.strip()[:120],
            "docstring": bool(re.match(r"^('''|\"\"\")", m.group(0))),
        })
    return flagged


def scan_diff(diff: str) -> list[dict]:
    flagged = []
    current_file, lang, new_line = "", "", 0
    for raw in diff.splitlines():
        if raw.startswith("+++ "):
            current_file = re.sub(r"^\+\+\+ [ab]/", "", raw).strip()
            lang = EXT_TO_LANG.get(Path(current_file).suffix, "")
        elif raw.startswith("@@"):
            m = re.search(r"\+(\d+)", raw)
            new_line = int(m.group(1)) - 1 if m else 0
        elif raw.startswith("+") and not raw.startswith("+++"):
            new_line += 1
            if lang:
                flagged.extend(scan_text(raw[1:], lang, current_file, new_line - 1))
        elif not raw.startswith("-"):
            new_line += 1
    return flagged


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("files", nargs="*")
    ap.add_argument("--diff", action="store_true", help="read a unified diff from stdin")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-over", type=int, default=None, metavar="N")
    args = ap.parse_args(argv)

    if args.diff:
        flagged = scan_diff(sys.stdin.read())
    elif args.files:
        flagged = []
        for f in args.files:
            p = Path(f)
            lang = EXT_TO_LANG.get(p.suffix, "")
            if lang and p.is_file():
                flagged.extend(scan_text(p.read_text(errors="replace"), lang, str(p)))
    else:
        ap.error("pass FILE arguments or --diff with stdin")

    if args.json:
        print(json.dumps({"flagged": flagged, "count": len(flagged)}, indent=2))
    else:
        for c in flagged:
            kind = "docstring" if c["docstring"] else "comment"
            print(f"{c['file']}:{c['line']}: {kind}: {c['text']}")
        print(f"\n{len(flagged)} unjustified comment(s)/docstring(s) "
              "(BDD, directives, licenses, TODO markers auto-pass)")
    if args.fail_over is not None and len(flagged) > args.fail_over:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
