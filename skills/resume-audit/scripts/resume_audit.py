#!/usr/bin/env python3
"""resume-audit: structural and ATS checks for a resume, optionally against a job description.

Reads a resume as markdown or plain text (convert PDF/docx first with
doc-reader) and scores what recruiters and ATS software actually filter on:
contact info present, standard sections, quantified bullet ratio, action-verb
openers, weak-phrase detection ("responsible for", "worked on"), and — when
given a job description — keyword coverage of the JD's hard requirements.
Offline, stdlib-only, deterministic.

Usage:
    resume_audit.py resume.md [--json]
    resume_audit.py resume.md --jd job-posting.txt --json
    ... --min-bullet-ratio 0.5

Exit codes: 0 checks pass, 1 failures found, 2 input error.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ACTION_VERBS = re.compile(
    r"(?i)^(led|launched|built|designed|shipped|grew|cut|reduced|increased|saved|"
    r"drove|owned|created|scaled|migrated|automated|mentored|hired|architected|"
    r"delivered|improved|won|negotiated|founded|spearheaded)\b")

WEAK_PHRASES = re.compile(
    r"(?i)\b(responsible for|worked on|helped with|was involved in|"
    r"participated in|assisted with|duties included)\b")

QUANTIFIED = re.compile(r"(\d+%|\$\d|\d+x\b|\d+k\b|#\d|\b\d{2,}\+?\s+(engineers?|"
                        r"users?|customers?|projects?|teams?|people|developers?|"
                        r"clients?|hours?|days?|months?|years?))")

SECTION_PATTERNS = {
    "experience": r"(?i)experience|employment|work history",
    "skills": r"(?i)skills|technologies|competencies",
    "education": r"(?i)education|academic",
}

CONTACT = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+|linkedin\.com|github\.com|\(?\d{3}\)?[-. ]\d{3}[-. ]\d{4}")

TECH_WORDS = re.compile(r"\b(python|java|javascript|typescript|golang|rust|c\+\+|sql|"
                        r"postgresql|mysql|mongodb|redis|kubernetes|docker|aws|gcp|azure|"
                        r"react|vue|node|django|flask|fastapi|terraform|linux|graphql)\b",
                        re.I)


def bullets_of(text: str) -> list[str]:
    return [ln.strip().lstrip("-*• ").strip()
            for ln in text.splitlines()
            if ln.strip().startswith(("- ", "* ", "• "))]


def audit(text: str, jd_text: str | None, min_ratio: float) -> dict:
    bullets = bullets_of(text)
    quantified = [b for b in bullets if QUANTIFIED.search(b)]
    action = [b for b in bullets if ACTION_VERBS.search(b)]
    weak = [b for b in bullets if WEAK_PHRASES.search(b)]
    sections = {name: bool(re.search(pat, text)) for name, pat in SECTION_PATTERNS.items()}

    ratio = len(quantified) / len(bullets) if bullets else 0.0
    checks = {
        "contact_info": {"status": "pass" if CONTACT.search(text) else "fail",
                         "value": "found" if CONTACT.search(text) else "missing email/phone/profile"},
        "sections": {"status": "pass" if sections["experience"] and sections["skills"] else "warn",
                     "value": ", ".join(k for k, v in sections.items() if v) or "none detected"},
        "quantified_bullets": {
            "status": "pass" if ratio >= min_ratio else "fail",
            "ratio": round(ratio, 2),
            "value": f"{len(quantified)}/{len(bullets)} bullets quantified"},
        "action_verbs": {
            "status": "pass" if bullets and len(action) / len(bullets) >= 0.5 else "warn",
            "value": f"{len(action)}/{len(bullets)} bullets open with an action verb"},
        "weak_phrases": {
            "status": "pass" if not weak else "fail",
            "value": f"{len(weak)} weak-phrase bullet(s)" if weak else "none",
            "examples": weak[:3]},
    }

    result: dict = {"checks": checks, "bullet_count": len(bullets)}

    if jd_text is not None:
        jd_words = set(re.findall(r"[a-z][a-z+#./-]{2,}", jd_text.lower()))
        stop = {"the", "and", "for", "with", "you", "your", "our", "are", "will",
                "have", "has", "this", "that", "from", "into", "their", "they",
                "who", "what", "where", "when", "how", "about", "work", "team",
                "years", "experience", "ability", "strong", "plus", "bonus"}
        keywords = sorted(jd_words - stop)
        resume_lower = text.lower()
        significant = [k for k in keywords
                       if len(k) > 3 or TECH_WORDS.match(k)]
        seen: dict[str, bool] = {}
        for k in significant:
            if k in seen:
                continue
            seen[k] = bool(re.search(rf"\b{re.escape(k)}\b", resume_lower))
        present = [k for k, v in seen.items() if v]
        tech_jd = sorted({m.group(0).lower() for m in TECH_WORDS.finditer(jd_text)})
        kw_list = [{"keyword": k, "present": seen[k]} for k in sorted(seen)]
        tech_missing = [t for t in tech_jd if t not in resume_lower]
        coverage = len(present) / len(seen) if seen else 1.0
        result["ats"] = {
            "coverage": round(coverage, 2),
            "keywords": kw_list,
            "tech_missing": tech_missing,
            "verdict": "strong" if coverage >= 0.7 and not tech_missing
                       else "partial" if coverage >= 0.4 else "weak",
        }
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("resume")
    ap.add_argument("--jd", default="")
    ap.add_argument("--min-bullet-ratio", type=float, default=0.4)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args(argv)

    p = Path(args.resume)
    if not p.is_file():
        print(f"missing: {args.resume}", file=sys.stderr)
        return 2
    text = p.read_text(errors="replace")
    jd_text = None
    if args.jd:
        jp = Path(args.jd)
        if not jp.is_file():
            print(f"missing: {args.jd}", file=sys.stderr)
            return 2
        jd_text = jp.read_text(errors="replace")

    result = audit(text, jd_text, args.min_bullet_ratio)
    result["file"] = str(p)
    fails = sum(1 for c in result["checks"].values() if c["status"] == "fail")

    if args.json:
        print(json.dumps(result, indent=2))
    else:
        for name, ck in result["checks"].items():
            mark = {"pass": "ok", "warn": "!!", "fail": "XX"}[ck["status"]]
            print(f"[{mark}] {name}: {ck['value']}")
        for ex in result["checks"]["weak_phrases"].get("examples", []):
            print(f"     weak: {ex[:80]}")
        if "ats" in result:
            a = result["ats"]
            print(f"ATS coverage: {a['coverage']:.0%} ({a['verdict']})")
            if a["tech_missing"]:
                print(f"  missing tech keywords: {', '.join(a['tech_missing'])}")
        print(f"\n{fails} failing check(s)")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
