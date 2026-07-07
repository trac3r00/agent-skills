#!/usr/bin/env python3
"""context_budget.py — audit an AI agent's context window like a cost center.

Point it at the files/dirs that get loaded into an agent's context every turn
(system prompt, skills, memory, tool schemas, gate code, prompt templates) and
it tells you *where the tokens actually go* — ranked, with a budget verdict.

The problem this solves: autonomous agents accrete context. A skill here, a
memory note there, another gate module — each cheap alone, together a tax paid
on EVERY request. Nobody measures it because there's no ruler. This is the ruler.

Usage:
    context_budget.py PATH [PATH ...] [--budget N] [--model MODEL] [--json]
    context_budget.py ~/.hermes/memories ~/.hermes/skills --budget 20000

Exit code is non-zero when the measured total blows the budget, so it drops
straight into CI or a pre-commit hook ("fail the build if the agent got fatter").
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path

# ── token counting ────────────────────────────────────────────────────────
# tiktoken when available (accurate for GPT-family + close enough elsewhere),
# else a calibrated chars/4 fallback so the tool never hard-fails on a fresh box.
try:
    import tiktoken

    _ENC = tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        return len(_ENC.encode(text, disallowed_special=()))

    _COUNTER = "tiktoken/cl100k_base"
except Exception:  # pragma: no cover - fallback path

    def count_tokens(text: str) -> int:
        # 4 chars/token is the well-worn English approximation; slightly
        # conservative for code (which tokenizes denser).
        return max(1, round(len(text) / 4))

    _COUNTER = "approx(chars/4)"


TEXT_EXT = {
    ".md", ".txt", ".py", ".js", ".ts", ".tsx", ".jsx", ".json", ".yaml",
    ".yml", ".toml", ".sh", ".rst", ".cfg", ".ini", ".xml", ".html", ".css",
}
SKIP_DIRS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".mypy_cache"}


@dataclass
class Entry:
    path: str
    tokens: int
    chars: int


@dataclass
class Report:
    entries: list[Entry] = field(default_factory=list)
    counter: str = _COUNTER

    @property
    def total_tokens(self) -> int:
        return sum(e.tokens for e in self.entries)

    @property
    def total_chars(self) -> int:
        return sum(e.chars for e in self.entries)


def _iter_text_files(root: Path):
    if root.is_file():
        yield root
        return
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            if p.suffix.lower() in TEXT_EXT:
                yield p


def scan(paths: list[str]) -> Report:
    rep = Report()
    seen: set[str] = set()
    for raw in paths:
        root = Path(raw).expanduser()
        if not root.exists():
            print(f"warn: path not found: {root}", file=sys.stderr)
            continue
        for f in _iter_text_files(root):
            rp = str(f.resolve())
            if rp in seen:
                continue
            seen.add(rp)
            try:
                text = f.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            rep.entries.append(Entry(str(f), count_tokens(text), len(text)))
    rep.entries.sort(key=lambda e: e.tokens, reverse=True)
    return rep


def _bar(frac: float, width: int = 24) -> str:
    filled = round(frac * width)
    return "█" * filled + "░" * (width - filled)


def render(rep: Report, budget: int | None, model: str, top: int = 20) -> str:
    if not rep.entries:
        return "no text files found in the given paths."
    total = rep.total_tokens
    lines = []
    lines.append(f"Context budget audit  ·  counter={rep.counter}  ·  model={model}")
    lines.append("=" * 68)
    lines.append(f"{'tokens':>9}  {'share':>6}  file")
    lines.append("-" * 68)
    for e in rep.entries[:top]:
        share = e.tokens / total if total else 0
        lines.append(f"{e.tokens:>9,}  {share*100:>5.1f}%  {e.path}")
    if len(rep.entries) > top:
        rest = sum(e.tokens for e in rep.entries[top:])
        lines.append(f"{rest:>9,}  {rest/total*100:>5.1f}%  … +{len(rep.entries)-top} more files")
    lines.append("-" * 68)
    lines.append(f"{total:>9,}  100.0%  TOTAL  ({rep.total_chars:,} chars, {len(rep.entries)} files)")
    if budget:
        frac = total / budget
        verdict = "OK" if total <= budget else "OVER BUDGET"
        lines.append("")
        lines.append(f"budget {budget:,}  [{_bar(min(frac,1.0))}] {frac*100:.0f}%  → {verdict}")
        if total > budget:
            over = total - budget
            lines.append(f"  {over:,} tokens over. Heaviest file is "
                         f"{rep.entries[0].tokens:,} tok — start there.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Audit an agent's per-turn context token budget.")
    ap.add_argument("paths", nargs="+", help="files/dirs loaded into context every turn")
    ap.add_argument("--budget", type=int, default=None, help="token budget; exit!=0 if exceeded")
    ap.add_argument("--model", default="generic", help="label only (counter is cl100k)")
    ap.add_argument("--top", type=int, default=20, help="how many files to list")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    args = ap.parse_args(argv)

    rep = scan(args.paths)
    if args.json:
        print(json.dumps({
            "counter": rep.counter,
            "total_tokens": rep.total_tokens,
            "total_chars": rep.total_chars,
            "file_count": len(rep.entries),
            "budget": args.budget,
            "over_budget": bool(args.budget and rep.total_tokens > args.budget),
            "entries": [{"path": e.path, "tokens": e.tokens, "chars": e.chars}
                        for e in rep.entries],
        }, indent=2))
    else:
        print(render(rep, args.budget, args.model, args.top))

    if args.budget and rep.total_tokens > args.budget:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
