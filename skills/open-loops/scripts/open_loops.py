#!/usr/bin/env python3
"""open-loops — extract unresolved commitments, deferrals, decisions, and
open questions from a conversation transcript so a DIFFERENT surface (a cron
job, a trigger, a fresh session) can pick them up instead of dropping them.

The problem this solves: a long-lived agent talks to its owner in a thread,
promises "I'll do X later", then a scheduled job fires with zero knowledge of
that promise — and either repeats a done task or forgets a pending one. This
tool turns the transcript into a small, stable JSON ledger of what is still
*open*, which the scheduled surface can load before it acts.

Pure standard library. Bilingual heuristics (EN + KO). Not an LLM — a fast,
offline, deterministic triage of *which loops are still open*.

Usage:
    # From a JSONL transcript ([{"role","content"}, ...] per line):
    python open_loops.py conversation.jsonl

    # From plain text on stdin ("[speaker] message" lines):
    cat thread.txt | python open_loops.py -

    # Fail (exit 1) when too many loops stay open — gate a session handoff:
    python open_loops.py conversation.jsonl --max-open 5

Exit codes:
    0  open loops within budget
    1  open loops exceed --max-open (a handoff-hygiene failure)
    2  bad input / no transcript
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Iterable


# --- heuristic markers -------------------------------------------------------
# Each pattern is intentionally conservative: we would rather miss a loop than
# flood the ledger with false positives a scheduled job would trip over.

COMMITMENT = re.compile(
    r"(?:\bI['’]?ll\b|\bI will\b|\bwe['’]?ll\b|\blet me\b|\bgoing to\b|"
    r"\bI'?m gonna\b|할게요|할게\b|하겠|만들게|보낼게|추가할게|올릴게|고칠게|정리할게)",
    re.IGNORECASE,
)
DEFERRAL = re.compile(
    r"(?:\blater\b|\btomorrow\b|\bnext time\b|\bafter (?:this|that)\b|"
    r"\bin a bit\b|\bfollow ?up\b|나중에|다음에|이따|보류|미뤄|미룰|이따가)",
    re.IGNORECASE,
)
DECISION = re.compile(
    r"(?:\blet['’]?s\b|\bwe['’]?ll go with\b|\bdecided\b|\bwe should\b|"
    r"\bgo with\b|하자\b|가자\b|정했|결정했|하기로)",
    re.IGNORECASE,
)
# A commitment/deferral is CLOSED if a later message says it is done.
DONE = re.compile(
    r"(?:\bdone\b|\bshipped\b|\bmerged\b|\bfinished\b|\bcompleted\b|\bfixed\b|"
    r"\bdeployed\b|끝났|완료|배포했|머지했|고쳤|끝냈|반영했|올렸|만들었|추가했|등록했)",
    re.IGNORECASE,
)
QUESTION = re.compile(r"[?？]\s*$")


@dataclass
class Loop:
    kind: str          # commitment | deferral | decision | open_question
    speaker: str
    turn: int
    text: str
    closed_by_turn: int | None = None

    @property
    def open(self) -> bool:
        return self.closed_by_turn is None


@dataclass
class Ledger:
    open_loops: list[dict] = field(default_factory=list)
    closed_loops: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)


# --- transcript loading ------------------------------------------------------

def _load_turns(raw: str) -> list[tuple[str, str]]:
    """Return [(speaker, text), ...]. Accepts JSONL or "[speaker] text" lines."""
    turns: list[tuple[str, str]] = []
    stripped = raw.strip()
    if not stripped:
        return turns

    # Try JSONL first (one JSON object per line).
    looks_jsonl = stripped[0] in "[{"
    if looks_jsonl:
        # Could be a single JSON array or line-delimited objects.
        try:
            obj = json.loads(stripped)
            rows = obj if isinstance(obj, list) else [obj]
            for row in rows:
                if isinstance(row, dict):
                    sp = str(row.get("role") or row.get("speaker") or "?")
                    tx = str(row.get("content") or row.get("text") or "").strip()
                    if tx:
                        turns.append((sp, tx))
            if turns:
                return turns
        except json.JSONDecodeError:
            pass
        for line in stripped.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                sp = str(row.get("role") or row.get("speaker") or "?")
                tx = str(row.get("content") or row.get("text") or "").strip()
                if tx:
                    turns.append((sp, tx))
        if turns:
            return turns

    # Plain text: "[speaker] message" or "speaker: message" or bare lines.
    bracket = re.compile(r"^\s*\[([^\]]+)\]\s*(.*)$")
    colon = re.compile(r"^\s*([A-Za-z0-9_가-힣 ]{1,20}?):\s+(.*)$")
    for line in stripped.splitlines():
        if not line.strip():
            continue
        m = bracket.match(line) or colon.match(line)
        if m:
            turns.append((m.group(1).strip(), m.group(2).strip()))
        else:
            turns.append(("?", line.strip()))
    return turns


# --- core --------------------------------------------------------------------

def extract(turns: list[tuple[str, str]]) -> list[Loop]:
    loops: list[Loop] = []
    for i, (speaker, text) in enumerate(turns):
        one_line = " ".join(text.split())
        clipped = one_line[:200]
        if COMMITMENT.search(text):
            loops.append(Loop("commitment", speaker, i, clipped))
        elif DEFERRAL.search(text):
            loops.append(Loop("deferral", speaker, i, clipped))
        if DECISION.search(text):
            loops.append(Loop("decision", speaker, i, clipped))
        if QUESTION.search(text):
            loops.append(Loop("open_question", speaker, i, clipped))

    # Close commitments/deferrals/questions when a LATER turn signals completion
    # or answers. Decisions are recorded but never auto-closed (they persist).
    for loop in loops:
        if loop.kind == "decision":
            continue
        for j in range(loop.turn + 1, len(turns)):
            _, later = turns[j]
            if loop.kind in ("commitment", "deferral") and DONE.search(later):
                loop.closed_by_turn = j
                break
            if loop.kind == "open_question" and not QUESTION.search(later):
                # first substantive non-question reply after the question
                if len(later.split()) >= 2:
                    loop.closed_by_turn = j
                    break
    return loops


def build_ledger(loops: list[Loop]) -> Ledger:
    ledger = Ledger()
    for lp in loops:
        row = asdict(lp)
        row.pop("closed_by_turn", None)
        (ledger.open_loops if lp.open else ledger.closed_loops).append(
            {**row, "closed_by_turn": lp.closed_by_turn}
        )
    kinds = ("commitment", "deferral", "decision", "open_question")
    ledger.counts = {
        "open_total": sum(1 for lp in loops if lp.open),
        "closed_total": sum(1 for lp in loops if not lp.open),
        **{f"open_{k}": sum(1 for lp in loops if lp.open and lp.kind == k) for k in kinds},
    }
    return ledger


def render_text(ledger: Ledger) -> str:
    out: list[str] = []
    c = ledger.counts
    out.append(
        f"OPEN LOOPS: {c['open_total']}  "
        f"(commitments {c['open_commitment']}, deferrals {c['open_deferral']}, "
        f"decisions {c['open_decision']}, questions {c['open_open_question']})  "
        f"| closed {c['closed_total']}"
    )
    if not ledger.open_loops:
        out.append("  ✓ nothing left open — clean handoff")
        return "\n".join(out)
    icon = {"commitment": "→", "deferral": "⏳", "decision": "◆", "open_question": "?"}
    for lp in ledger.open_loops:
        out.append(f"  {icon.get(lp['kind'], '•')} [{lp['kind']}] ({lp['speaker']}) {lp['text']}")
    return "\n".join(out)


def main(argv: Iterable[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Extract open loops from a transcript for a clean cross-surface handoff.")
    ap.add_argument("transcript", help="path to a JSONL/text transcript, or '-' for stdin")
    ap.add_argument("--max-open", type=int, default=None,
                    help="exit 1 if open loops exceed this budget (handoff gate)")
    ap.add_argument("--json", action="store_true", help="emit the ledger as JSON")
    args = ap.parse_args(list(argv) if argv is not None else None)

    if args.transcript == "-":
        raw = sys.stdin.read()
    else:
        try:
            with open(args.transcript, "r", encoding="utf-8") as fh:
                raw = fh.read()
        except OSError as exc:
            print(f"open-loops: cannot read {args.transcript}: {exc}", file=sys.stderr)
            return 2

    turns = _load_turns(raw)
    if not turns:
        print("open-loops: empty or unparseable transcript", file=sys.stderr)
        return 2

    ledger = build_ledger(extract(turns))
    if args.json:
        print(json.dumps(asdict(ledger), ensure_ascii=False, indent=2))
    else:
        print(render_text(ledger))

    if args.max_open is not None and ledger.counts["open_total"] > args.max_open:
        print(
            f"open-loops: {ledger.counts['open_total']} open loops exceed budget of {args.max_open}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
