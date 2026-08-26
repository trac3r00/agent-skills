# skills/ — CONTRIBUTOR CONTRACT

34 dirs, one contract. Score for this file: uniform structure across many dirs (root covers the rest).

## OVERVIEW
Each skill = `skills/<name>/SKILL.md` (+ optional `scripts/`, `references/`, `LICENSE.txt`). Instruction-only skills need no code; script-backed skills ship a stdlib-only Python CLI.

## ADDING A SKILL
1. `SKILL.md` frontmatter — required, test-enforced (`tests/test_skills.py`):
   ```yaml
   ---
   name: <exactly-the-dirname>
   description: <what + when-to-use, >=40 chars; this is the routing surface>
   version: 1.0.0
   license: <SPDX or "MIT (from owner/repo; see LICENSE.txt)">
   metadata:
     agentskills:
       tags: [a, b, c]
   ---
   ```
2. Ported skill: copy upstream LICENSE into `<name>/LICENSE.txt`; de-brand (harness tools as examples only, plain-text fallback); drop binaries >100K and eval artifacts.
3. Script-backed: follow the CLI contract (argparse, `-` stdin, `--json`, rc 0/1/2, gates strict `>`); add tests in `tests/test_skills.py` using the `run()` helper; isolate HOME-touching tools with a `tmp_path` HOME env.
4. Register: three manifests (`.claude-plugin/marketplace.json`, `.claude-plugin/plugin.json`, `.codex-plugin/plugin.json` — same version bump) + README family table + count.

## WHERE TO LOOK
| Need | Skill |
|------|-------|
| CLI + gate reference implementation | claim-audit, skill-decay (cleanest argparse/gate patterns) |
| Multi-store filesystem scanning | skill-sync, session-handoff |
| Verbatim-upstream reference style | design (references/ ARE the skill; router SKILL.md stays thin) |
| Large engine vendored in-skill | ultimate-browsing (has own engine/AGENTS.md + ATTRIBUTION.md) |

## ANTI-PATTERNS
- Overlapping skill purposes: every skill must answer a question no existing skill answers (secret-gate=credentials-in-diffs vs comment-checker=comments-in-diffs; usage-audit=token-totals vs session-handoff=conversation-content vs context-budget=static-estimate). Check the inventory before adding; shared helper NAMES are fine (skills are copy-portable and never import each other), shared PURPOSE is not.
- Frontmatter `name` != dirname (test fails).
- Description under 40 chars (test fails) or missing when-to-use routing cues.
- Adding pip dependencies to a guard CLI.
- Editing `design/references/*` prose — it is verbatim Anthropic guidance; patch only portability seams.
