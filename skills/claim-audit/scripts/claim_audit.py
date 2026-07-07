#!/usr/bin/env python3
"""claim_audit.py — make an AI answer show its work, or flag where it didn't.

The idea (from the "state your reasoning to cut hallucination" school): a model
is far likelier to be wrong on a *factual claim it asserted without any evidence*
than on one it hedged, cited, or derived. This tool reads an agent's answer and
separates:

  • GROUNDED   — claim carries a citation / source / quoted evidence nearby
  • HEDGED     — claim is explicitly uncertain ("likely", "I'm not sure", "~")
  • BARE       — a hard factual assertion with no evidence and no hedge  ← risk

It's a linter for answers, not a fact-checker: it can't tell you a grounded claim
is *true*, but it reliably surfaces the bare assertions most worth verifying — the
ones that hallucinate. Use it as a self-check gate before an agent ships a reply,
or in CI over saved transcripts.

Usage:
    claim_audit.py answer.txt
    echo "The capital of Australia is Sydney. It was founded in 1788." | claim_audit.py -
    claim_audit.py answer.txt --json --fail-over 0.5   # exit!=0 if >50% bare
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, asdict
from enum import Enum


class Kind(str, Enum):
    GROUNDED = "grounded"
    HEDGED = "hedged"
    BARE = "bare"
    OPINION = "opinion"  # not a checkable factual claim; excluded from risk ratio


# ── signal lexicons ───────────────────────────────────────────────────────
HEDGE = re.compile(
    r"\b(maybe|perhaps|possibly|probably|likely|unlikely|might|may|could|"
    r"seems?|appears?|suggests?|roughly|approximately|around|about|"
    r"i think|i believe|i'?m not sure|as far as i know|afaik|to my knowledge|"
    r"estimate[ds]?|estimated|allegedly|reportedly|presumably)\b",
    re.I,
)
# evidence markers: citations, urls, quoted spans, code/file refs, "according to"
GROUND = re.compile(
    r"(https?://|www\.|\[\d+\]|\baccording to\b|\bper \b|\bsource:|\bciting\b|"
    r"\bref(?:erence)?\b|\bdocumented\b|\bas shown\b|\bsee \b|`[^`]+`|"
    r'"[^"]{6,}"|\bfig(?:ure)?\.?\s*\d|\btable\s*\d|\bline\s*\d+)',
    re.I,
)
# first-person opinion / meta / instruction — not a world-fact to verify
OPINION = re.compile(
    r"\b(i recommend|i suggest|i'?d|you should|let'?s|we should|in my opinion|"
    r"i'?ll|i will|i can|i'?ve|please|consider|note that|here'?s|below|above)\b",
    re.I,
)
# a "hard factual assertion" heuristic: declaratives with is/are/was/were/has/
# numbers/dates/proper-noun equalities. Deliberately simple + transparent.
HARD_FACT = re.compile(
    r"\b(is|are|was|were|has|have|had|will be|equals?|contains?|consists?|"
    r"released|founded|created|invented|located|born|died|costs?|measures?)\b"
    r"|\b\d{3,}\b|\b\d{4}\b|\b\d+(\.\d+)?\s?(%|kb|mb|gb|tb|ms|km|kg)\b",
    re.I,
)

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'`])")


@dataclass
class Claim:
    text: str
    kind: Kind
    reason: str


def classify(sentence: str) -> Claim:
    s = sentence.strip()
    if GROUND.search(s):
        return Claim(s, Kind.GROUNDED, "carries citation/quote/source marker")
    if HEDGE.search(s):
        return Claim(s, Kind.HEDGED, "explicitly hedged / uncertain")
    is_fact = bool(HARD_FACT.search(s))
    is_op = bool(OPINION.search(s))
    if is_fact and not is_op:
        return Claim(s, Kind.BARE, "hard assertion, no evidence, no hedge")
    return Claim(s, Kind.OPINION, "not a checkable world-fact (opinion/meta/instruction)")


def audit(text: str) -> list[Claim]:
    # split into sentences, keep only sentence-like spans
    parts = [p for p in SENT_SPLIT.split(text.strip()) if len(p.strip()) > 3]
    if not parts and text.strip():
        parts = [text.strip()]
    return [classify(p) for p in parts]


def risk_ratio(claims: list[Claim]) -> float:
    checkable = [c for c in claims if c.kind != Kind.OPINION]
    if not checkable:
        return 0.0
    bare = sum(1 for c in checkable if c.kind == Kind.BARE)
    return bare / len(checkable)


_ICON = {Kind.GROUNDED: "✓", Kind.HEDGED: "~", Kind.BARE: "⚠", Kind.OPINION: "·"}


def render(claims: list[Claim]) -> str:
    lines = ["Claim audit  ·  ✓ grounded  ~ hedged  ⚠ bare(verify!)  · opinion/meta",
             "=" * 70]
    for c in claims:
        t = c.text if len(c.text) <= 88 else c.text[:85] + "…"
        lines.append(f"{_ICON[c.kind]} [{c.kind.value:8}] {t}")
    counts = {k: sum(1 for c in claims if c.kind == k) for k in Kind}
    rr = risk_ratio(claims)
    lines.append("-" * 70)
    lines.append(
        f"grounded={counts[Kind.GROUNDED]}  hedged={counts[Kind.HEDGED]}  "
        f"bare={counts[Kind.BARE]}  opinion={counts[Kind.OPINION]}  "
        f"|  BARE risk = {rr*100:.0f}% of checkable claims"
    )
    bare = [c for c in claims if c.kind == Kind.BARE]
    if bare:
        lines.append("\nVerify these before shipping:")
        for c in bare:
            t = c.text if len(c.text) <= 88 else c.text[:85] + "…"
            lines.append(f"  ⚠ {t}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Flag unverified factual claims in an AI answer.")
    ap.add_argument("file", help="answer text file, or - for stdin")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--fail-over", type=float, default=None,
                    help="exit!=0 if BARE risk ratio exceeds this (0..1)")
    args = ap.parse_args(argv)

    text = sys.stdin.read() if args.file == "-" else open(args.file, encoding="utf-8").read()
    claims = audit(text)
    rr = risk_ratio(claims)

    if args.json:
        print(json.dumps({
            "risk_ratio": round(rr, 4),
            "counts": {k.value: sum(1 for c in claims if c.kind == k) for k in Kind},
            "claims": [asdict(c) | {"kind": c.kind.value} for c in claims],
        }, indent=2))
    else:
        print(render(claims))

    if args.fail_over is not None and rr > args.fail_over:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
