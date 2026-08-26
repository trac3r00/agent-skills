# Agent Skills

Dependency-light Python tools for auditing AI-agent context, output, handoffs, recurring costs, gate overlap, and capability usage — plus portable creative skills for design, generative art, and browser testing.

[![Python 3.9+](https://img.shields.io/badge/python-3.9%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Overview

Agent Skills is a collection of 31 [Agent Skills](https://agentskills.io) in five families:

- **Guards** — runnable audit skills (plus the interop CLIs), each combining an instruction file (`SKILL.md`) with a standalone Python CLI that produces human-readable or JSON output and can return a non-zero status when a configured threshold is exceeded. They run locally, accept files or standard input, and need no credentials or network access.
- **Interop** — `skill-sync` unifies custom skills across every AI provider install into one universal directory, and `session-handoff` carries work context (session logs, history, files touched) between clients so any agent can continue work started in another.
- **Creative** — design, art, frontend, and writing skills: three derived from [anthropics/skills](https://github.com/anthropics/skills) (Apache-2.0), consolidated and de-branded so any SKILL.md-reading agent can use them outside Claude Code, plus community CSS and technical-writing skills.
- **Process** — engineering-discipline skills from [obra/superpowers](https://github.com/obra/superpowers) (MIT) and [hiendinhngoc/unknowns](https://github.com/hiendinhngoc/unknowns) (MIT): root-cause debugging, TDD, evidence-before-claims verification, git worktrees, pre-work blindspot recon, reference comprehension gates, deviation logging, and pre-merge quizzes.
- **Power tools** — heavyweight skills ported from [oh-my-opencode / omo-ai](https://github.com/code-yeongyu/oh-my-opencode) and anthropics/skills: git mastery, escalation web browsing with WAF bypass, LSP setup for 20 languages, AI-slop removal, and skill authoring/evaluation.

The repository can be used directly from a clone or installed as the `agent-skills` plugin for Claude Code or Codex.

## Features

| Skill | Purpose | Optional gate |
| --- | --- | --- |
| [`context-budget`](skills/context-budget/) | Ranks text files by estimated token usage and reports total context size. | `--budget` |
| [`claim-audit`](skills/claim-audit/) | Classifies statements as grounded, hedged, bare, or opinion/meta to identify claims that need verification. It is a linter, not a fact-checker. | `--fail-over` |
| [`open-loops`](skills/open-loops/) | Extracts unresolved commitments, deferrals, decisions, and questions from plain-text or JSON transcripts. | `--max-open` |
| [`subscription-audit`](skills/subscription-audit/) | Detects repeated charges in exported bank or card CSV files and estimates monthly and yearly recurring spend. | `--budget` |
| [`gate-graph`](skills/gate-graph/) | Compares Python modules by AST-derived fingerprints and reports overlap and modules with no detected imports. | `--max-gates`, `--max-overlap` |
| [`skill-decay`](skills/skill-decay/) | Compares a declared skill inventory with usage logs and classifies capabilities as live, stale, or never used. | `--max-decay`, `--fail-on-never` |
| [`skill-sync`](skills/skill-sync/) | Discovers skills across all AI provider installs, reports provenance and conflicts, and symlinks or copies the union into one universal directory. | `--fail-on-conflict` |
| [`comment-checker`](skills/comment-checker/) | Flags unjustified new comments/docstrings in files or diffs; BDD markers, lint directives, licenses, and TODOs auto-pass. | `--fail-over` |
| [`session-handoff`](skills/session-handoff/) | Reads session logs from Claude Code, Codex, OpenCode/OMO, and Gemini CLI stores and produces a portable handoff briefing so any client can continue another's work. | — |

### Creative skills

| Skill | Purpose |
| --- | --- |
| [`design`](skills/design/) | Claude-grade visual design direction for any agent: web/UI design principles, canvas/poster art philosophy, and a 10-theme styling library, with an on-demand OFL font fetcher instead of vendored binaries. |
| [`algorithmic-art`](skills/algorithmic-art/) | Generative art with p5.js: seeded randomness, flow fields, particle systems, and an interactive parameter-exploration viewer. |
| [`webapp-testing`](skills/webapp-testing/) | Playwright-based browser QA for local web apps: frontend verification, UI debugging, screenshots, and console-log capture. |
| [`css-pro-tips`](skills/css-pro-tips/) | Source-validated modern CSS/Tailwind patterns: resets, focus styles, container queries, Baseline-aware features. |
| [`nbj-write-clearly`](skills/nbj-write-clearly/) | Reader-first technical writing grounded in the Google Developer Documentation Style Guide. |

### Process skills

| Skill | Purpose |
| --- | --- |
| [`systematic-debugging`](skills/systematic-debugging/) | Four-phase root-cause-first debugging discipline with references on root-cause tracing, defense-in-depth fixes, and condition-based waiting. |
| [`test-driven-development`](skills/test-driven-development/) | Red-green-refactor discipline: watch the test fail first, write minimal code to pass, with a guide to writing good tests. |
| [`verification-before-completion`](skills/verification-before-completion/) | Evidence before claims: run the verification commands and confirm output before declaring work complete. |
| [`using-git-worktrees`](skills/using-git-worktrees/) | Parallel development with git worktrees: isolation for risky work, safe directory selection, and cleanup. |
| [`blindspot`](skills/blindspot/) | Read-only reconnaissance pass over unfamiliar code to surface hidden risks before writing anything. |
| [`verify-ref`](skills/verify-ref/) | Comprehension gate before porting or adapting reference code: prove understanding first. |
| [`log-deviation`](skills/log-deviation/) | Records where implementation was forced to deviate from the plan; feeds future planning. |
| [`merge-quiz`](skills/merge-quiz/) | Pre-merge gate that quizzes the human on the riskiest parts of the branch diff. |
| [`grilling`](skills/grilling/) | Relentless interview that stress-tests a plan, decision, or design before building. |
| [`domain-modeling`](skills/domain-modeling/) | Builds and sharpens a project's domain model: terminology, CONTEXT.md, ADRs. |
| [`linus-level`](skills/linus-level/) | A 1.0-10.0 engineering working-mode dial tuning agency, verification depth, questioning, and security posture. |

### Power tools

| Skill | Purpose |
| --- | --- |
| [`git-master`](skills/git-master/) | Mode-gated git operations: atomic commits, rebase/squash/autosquash, blame, bisect, reflog, and history forensics. |
| [`ultimate-browsing`](skills/ultimate-browsing/) | Tiered escalation web access: headless extraction with WAF bypass (curl_cffi, yt-dlp, archives), platform-native APIs, and stealth-browser interaction. |
| [`lsp-setup`](skills/lsp-setup/) | Configure the right language server for 20 languages: detection, per-OS install, config for multiple harnesses, and diagnostics verification. |
| [`remove-ai-slops`](skills/remove-ai-slops/) | Behavior-preserving cleanup of AI-generated code smells: regression tests first, categorized passes, quality gates. |
| [`skill-creator`](skills/skill-creator/) | Author, validate, package, and eval-test new agent skills, with grader/comparator agent prompts. |
| [`skill-optimizer`](skills/skill-optimizer/) | Refines existing skills through real usage: saves tokens, eliminates redundancy, tightens instructions. |

All guard CLIs support JSON output, operate offline, and require no credentials or network access.

## Architecture

```text
Claude Code / Codex / compatible Agent Skills host
                        |
               plugin manifests
                        |
                skills/<name>/
                |             |
             SKILL.md     [scripts/*.py]
                                |
                 files or stdin input
                                |
            text or JSON output + exit status
```

The plugin manifests in `.claude-plugin/` and `.codex-plugin/` expose the directories under `skills/`. Nine skills are script-backed (guards plus `skill-sync`, `session-handoff`); the rest are instruction-only — the `SKILL.md` is the skill. Every script is directly executable with Python and does not depend on an agent host.

## Installation

### Run from a clone

Python 3.9 or later is required (CI tests 3.9, 3.11, and 3.12).

```bash
git clone https://github.com/Trac3r00/agent-skills.git
cd agent-skills
```

All script-backed skills use only the Python standard library. `context-budget` also runs without third-party packages, but uses the `cl100k_base` tokenizer when `tiktoken` is installed and otherwise falls back to an approximate character-based count.

```bash
python3 -m pip install tiktoken  # optional, for tokenizer-based context counts
```

### Install as a plugin

Claude Code:

```bash
claude plugin marketplace add Trac3r00/agent-skills
claude plugin install agent-skills@agent-skills
```

Codex:

```bash
codex plugin marketplace add Trac3r00/agent-skills
codex plugin add agent-skills@agent-skills
```

The plugin installs all 31 skills together. To use individual skills without the plugin, copy the relevant directory from `skills/` into the skills directory supported by your agent host, or use the bundled `skill-sync` skill to link them into a universal directory.

## Usage

Run commands from the repository root.

### Audit context size

```bash
python3 skills/context-budget/scripts/context_budget.py \
  path/to/system-prompt.md path/to/skills/ \
  --budget 40000 --top 15
```

### Identify unsupported claims

```bash
printf '%s\n' 'The service was launched in 2024.' \
  | python3 skills/claim-audit/scripts/claim_audit.py - --fail-over 0.4
```

### Extract unresolved conversation items

```bash
python3 skills/open-loops/scripts/open_loops.py thread.jsonl --json
```

The transcript may be a JSON array, JSONL records containing `role` and `content`, or plain text using `[speaker] message` or `speaker: message` lines.

### Audit recurring charges

```bash
python3 skills/subscription-audit/scripts/subscription_audit.py statement.csv \
  --budget 80 --json
```

The CSV must contain date, description or merchant, and amount data. Header names and common delimiters are detected automatically; use `-` as the input path to read CSV data from standard input.

### Compare Python gate modules

```bash
python3 skills/gate-graph/scripts/gate_graph.py path/to/gates/ \
  --max-gates 49 --max-overlap 0.5 --json
```

### Find unused or stale skills

```bash
python3 skills/skill-decay/scripts/skill_decay.py \
  --skills-dir path/to/skills/ \
  --logs path/to/agent-logs/ \
  --stale-days 30 --max-decay 20
```

Use `python3 skills/<skill>/scripts/<script>.py --help` for the complete interface of any tool.

## Configuration

The project does not read environment variables or a shared configuration file. Behavior is configured through command-line arguments:

| Tool | Main options |
| --- | --- |
| `context_budget.py` | `--budget`, `--model`, `--top`, `--json` |
| `claim_audit.py` | `--fail-over`, `--json` |
| `open_loops.py` | `--max-open`, `--json` |
| `subscription_audit.py` | `--budget`, `--min-charges`, `--stale-days`, `--currency`, `--json` |
| `gate_graph.py` | `--max-gates`, `--max-overlap`, `--top`, `--full-matrix`, `--json` |
| `skill_decay.py` | `--skills-dir` or `--names`, `--logs`, `--stdin`, `--stale-days`, `--max-decay`, `--fail-on-never`, `--as-of`, `--json` |

When a configured threshold is exceeded, the relevant command exits with status `1`, making it suitable for local automation or CI. Input and usage errors handled by the scripts exit with status `2`.

## Development

The test suite requires [pytest](https://docs.pytest.org/).

```bash
python3 -m pip install pytest
pytest tests/test_skills.py
```

The suite covers every script-backed CLI end-to-end and validates every skill's `SKILL.md` frontmatter (name matches directory, discoverable description). CI (`.github/workflows/tests.yml`) runs it on Python 3.9, 3.11, and 3.12 for pushes to `main` and pull requests.

To add a skill, follow the contributor contract in [`skills/AGENTS.md`](skills/AGENTS.md): frontmatter requirements, the CLI and gate conventions, and the manifest registration checklist.

## Project structure

```text
.
├── .claude-plugin/       # Claude Code marketplace and plugin metadata
├── .codex-plugin/        # Codex plugin metadata
├── .github/workflows/    # CI: pytest matrix + CLI smoke tests
├── skills/               # 31 skills: SKILL.md instructions, 9 with standalone Python CLIs
├── tests/test_skills.py  # End-to-end CLI tests + repo-wide frontmatter validation
├── LICENSE
└── README.md
```

## License

Licensed under the [MIT License](LICENSE).
