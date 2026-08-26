#!/usr/bin/env python3
"""generate-catalogue: build catalogue.json from the actual skills/ directory.

No hand-maintained duplication — the catalogue is generated from the source
of truth (each skill's SKILL.md frontmatter) and validated against the
directory structure. Run after adding, removing, or renaming any skill.

Usage:
    generate_catalogue.py                    # write catalogue.json to repo root
    generate_catalogue.py --check            # validate without writing (CI gate)
    generate_catalogue.py --json             # print to stdout

Exit codes: 0 ok, 1 catalogue stale/invalid, 2 usage error.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
if not (REPO / "skills").is_dir():
    REPO = Path(__file__).resolve().parent.parent.parent.parent
SKILLS = REPO / "skills"
CATALOGUE = REPO / "catalogue.json"

FM_RE = re.compile(r"^---\n(.*?)\n---\n", re.S)
FIELD_RE = re.compile(r"^(\w+):\s*(.+?)\s*$", re.M)
TAGS_RE = re.compile(r"tags:\s*\[(.+?)\]")

FAMILIES = {
    "guards": ["context-budget", "claim-audit", "open-loops", "subscription-audit",
               "gate-graph", "skill-decay", "comment-checker"],
    "interop": ["skill-sync", "session-handoff", "session-rules", "usage-audit"],
    "security": ["secret-gate", "skill-audit", "usage-audit"],
    "backend": ["env-gate", "diff-review", "portfolio-audit", "doc-reader",
                "seo-audit", "resume-audit", "api-tester", "log-analyzer", "json-diff"],
    "process": ["systematic-debugging", "test-driven-development",
                "verification-before-completion", "using-git-worktrees",
                "blindspot", "verify-ref", "log-deviation", "merge-quiz",
                "grilling", "domain-modeling", "linus-level"],
    "creative": ["design", "algorithmic-art", "webapp-testing", "css-pro-tips",
                 "nbj-write-clearly", "visual-qa"],
    "power": ["git-master", "ultimate-browsing", "lsp-setup", "remove-ai-slops",
              "skill-creator", "skill-optimizer", "apple-suite"],
}

PERSONAS = {
    "coding": ["git-master", "remove-ai-slops", "comment-checker", "secret-gate",
               "systematic-debugging", "test-driven-development", "diff-review",
               "domain-modeling", "grilling", "lsp-setup"],
    "frontend": ["design", "css-pro-tips", "webapp-testing", "visual-qa",
                 "seo-audit", "algorithmic-art"],
    "backend": ["env-gate", "portfolio-audit", "doc-reader", "systematic-debugging",
                "test-driven-development", "git-master", "lsp-setup", "diff-review",
                "api-tester", "log-analyzer", "json-diff"],
    "devops": ["env-gate", "secret-gate", "diff-review", "git-master", "lsp-setup",
               "api-tester", "log-analyzer"],
    "agentic": ["skill-sync", "session-handoff", "session-rules", "skill-audit",
                "skill-decay", "skill-creator", "skill-optimizer", "usage-audit",
                "context-budget", "open-loops", "linus-level", "log-deviation"],
    "design": ["design", "algorithmic-art", "css-pro-tips", "visual-qa",
               "nbj-write-clearly", "seo-audit"],
    "verification": ["verification-before-completion", "claim-audit", "merge-quiz",
                     "verify-ref", "blindspot", "systematic-debugging",
                     "test-driven-development", "comment-checker", "secret-gate",
                     "skill-audit", "gate-graph", "env-gate", "diff-review",
                     "resume-audit", "seo-audit", "portfolio-audit"],
    "career": ["resume-audit", "nbj-write-clearly", "doc-reader"],
    "finance": ["portfolio-audit", "subscription-audit"],
    "macos": ["apple-suite"],
    "research": ["ultimate-browsing", "session-handoff", "usage-audit"],
    "qa": ["webapp-testing", "visual-qa", "verification-before-completion",
           "diff-review", "seo-audit"],
}


def parse_skill(skill_dir: Path) -> dict:
    md = skill_dir / "SKILL.md"
    if not md.is_file():
        return {}
    text = md.read_text(errors="replace")
    m = FM_RE.match(text)
    if not m:
        return {}
    fm = m.group(1)
    fields = dict(FIELD_RE.findall(fm))
    tags_m = TAGS_RE.search(fm)
    tags = [t.strip().strip('"') for t in tags_m.group(1).split(",")] if tags_m else []
    has_scripts = (skill_dir / "scripts").is_dir() and any(
        (skill_dir / "scripts").glob("*.py"))
    family = next((f for f, members in FAMILIES.items() if skill_dir.name in members),
                  "other")
    personas = sorted(p for p, members in PERSONAS.items() if skill_dir.name in members)
    return {
        "name": skill_dir.name,
        "description": fields.get("description", ""),
        "version": fields.get("version", ""),
        "license": fields.get("license", ""),
        "tags": tags,
        "family": family,
        "personas": personas,
        "script_backed": has_scripts,
        "path": f"skills/{skill_dir.name}",
    }


def generate() -> dict:
    skills = []
    for d in sorted(SKILLS.iterdir()):
        if not d.is_dir():
            continue
        entry = parse_skill(d)
        if entry:
            skills.append(entry)
    return {
        "version": "1.0.0",
        "count": len(skills),
        "families": {f: [s["name"] for s in skills if s["family"] == f]
                     for f in sorted({s["family"] for s in skills})},
        "personas": {p: [s["name"] for s in skills if p in s["personas"]]
                     for p in sorted(PERSONAS)},
        "skills": skills,
    }


def main() -> int:
    check = "--check" in sys.argv
    to_stdout = "--json" in sys.argv
    cat = generate()

    if check:
        if not CATALOGUE.is_file():
            print("catalogue.json missing — run generate_catalogue.py", file=sys.stderr)
            return 1
        existing = json.loads(CATALOGUE.read_text())
        if existing != cat:
            stale = set(s["name"] for s in cat["skills"]) - set(
                s["name"] for s in existing["skills"])
            extra = set(s["name"] for s in existing["skills"]) - set(
                s["name"] for s in cat["skills"])
            print(f"catalogue.json stale: new={stale or 'none'} removed={extra or 'none'}",
                  file=sys.stderr)
            return 1
        print(f"catalogue.json valid: {cat['count']} skills")
        return 0

    if to_stdout:
        print(json.dumps(cat, indent=2))
        return 0

    CATALOGUE.write_text(json.dumps(cat, indent=2) + "\n")
    print(f"catalogue.json written: {cat['count']} skills, "
          f"{len(cat['families'])} families, {len(cat['personas'])} personas")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
