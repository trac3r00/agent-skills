# PROJECT KNOWLEDGE BASE

**Generated:** 2026-08-26
**Commit:** 184b217
**Branch:** main

## OVERVIEW
51 agent skills (SKILL.md standard) in five families; 27 are script-backed stdlib-only Python CLIs with exit-code gates, 22 are instruction-only. Installable as a Claude Code / Codex plugin or used from a clone by any SKILL.md-reading agent.

## STRUCTURE
```
agent-skills/
├── .claude-plugin/   # marketplace.json (catalog) + plugin.json (metadata), version-locked together
├── .codex-plugin/    # Codex manifest; skills path ./skills/, no version field
├── .agents/plugins/  # generic marketplace manifest
├── skills/<name>/    # SKILL.md [+ scripts/*.py] [+ references/] [+ LICENSE.txt]
└── tests/test_skills.py  # single test module for ALL skill CLIs + repo-wide frontmatter validation
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Add a skill | `skills/<name>/SKILL.md` | frontmatter contract in skills/AGENTS.md; validated by tests |
| Add CLI tests | `tests/test_skills.py` | script const near `CB`..`SH`, use `run()` helper |
| Bump release | `.claude-plugin/*.json`, `.codex-plugin/plugin.json` | keep versions + descriptions in sync across all three |
| Skill families / inventory | `README.md` tables | update when adding a skill; counts are asserted nowhere — keep honest |
| CI | `.github/workflows/tests.yml` | pytest matrix 3.9/3.11/3.12 + 2 smoke tests |

## CODE MAP
| Symbol | Type | Location | Role |
|--------|------|----------|------|
| `run(script,*args,stdin)` | helper | tests/test_skills.py:19 | subprocess runner all CLI tests share |
| `test_every_skill_has_valid_frontmatter` | test | tests/test_skills.py | repo-wide gate: name==dir, description present |
| `discover()` | fn | skills/skill-sync/scripts/skill_sync.py | provider-root scan, priority dedupe |
| `SCANNERS` | dict | skills/session-handoff/scripts/session_handoff.py | per-client session store readers |
| `PROVIDER_ROOTS` | const | skills/skill-sync/scripts/skill_sync.py | priority-ordered skill dirs per provider |

## CONVENTIONS
- CLI contract (all 27 script-backed skills): argparse, positional input or `-` stdin, `--json`, gates are strict `>` comparisons; rc 0 ok / 1 gate breach / 2 usage-or-input error.
- Stdlib-only; sole exception: `context-budget` optionally uses `tiktoken` (chars/4 fallback).
- Frontmatter: `name` (== dirname), `description`, `version`, `license` (with upstream attribution), `metadata.agentskills.tags`.
- Ported skills keep upstream LICENSE.txt in-dir and a `license:` frontmatter line naming the source repo.
- De-brand ported content: harness-specific tools named only as examples with plain-text fallbacks.

## ANTI-PATTERNS (THIS PROJECT)
- No network/credentials/LLM calls inside guard CLIs — offline and deterministic, always.
- Never overwrite user files in sync-type tools (skill-sync `skip-exists`; session-handoff is read-only).
- Tool claims stay honest: claim-audit is NOT a fact-checker; skill-decay "never used" is a review prompt, not proof; gate-graph overlap is a candidate, not semantic equivalence.
- Don't hand-edit one manifest: `.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` move together.

## COMMANDS
```bash
uvx pytest tests/ -q                 # full suite (93 tests)
python3 skills/<s>/scripts/<s>.py --help
```

## NOTES
- `skills/ultimate-browsing/engine/AGENTS.md` documents the vendored fetch engine — leave it upstream-shaped.
- macOS: session-handoff normalizes `/tmp` -> `/private/tmp`; cwd matching is target-or-child, never parent.
- CI tests Python 3.9 while README floor is 3.9 too — keep them aligned when bumping.
