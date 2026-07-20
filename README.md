# Agent Guards

Dependency-light Python tools for auditing AI-agent context, output, handoffs, recurring costs, gate overlap, and capability usage.

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

## Overview

Agent Guards is a collection of six runnable [Agent Skills](https://agentskills.io). Each skill combines an instruction file (`SKILL.md`) with a standalone Python CLI that can produce human-readable or JSON output. The tools run locally, accept files or standard input, and can return a non-zero status when a configured threshold is exceeded.

The repository can be used directly from a clone or installed as the `agent-guards` plugin for Claude Code or Codex.

## Features

| Skill | Purpose | Optional gate |
| --- | --- | --- |
| [`context-budget`](skills/context-budget/) | Ranks text files by estimated token usage and reports total context size. | `--budget` |
| [`claim-audit`](skills/claim-audit/) | Classifies statements as grounded, hedged, bare, or opinion/meta to identify claims that need verification. It is a linter, not a fact-checker. | `--fail-over` |
| [`open-loops`](skills/open-loops/) | Extracts unresolved commitments, deferrals, decisions, and questions from plain-text or JSON transcripts. | `--max-open` |
| [`subscription-audit`](skills/subscription-audit/) | Detects repeated charges in exported bank or card CSV files and estimates monthly and yearly recurring spend. | `--budget` |
| [`gate-graph`](skills/gate-graph/) | Compares Python modules by AST-derived fingerprints and reports overlap and modules with no detected imports. | `--max-gates`, `--max-overlap` |
| [`skill-decay`](skills/skill-decay/) | Compares a declared skill inventory with usage logs and classifies capabilities as live, stale, or never used. | `--max-decay`, `--fail-on-never` |

All tools support JSON output. They operate offline and do not require credentials or network access.

## Architecture

```text
Claude Code / Codex / compatible Agent Skills host
                        |
               plugin manifests
                        |
                skills/<name>/
                |             |
             SKILL.md      scripts/*.py
                                |
                 files or stdin input
                                |
            text or JSON output + exit status
```

The plugin manifests in `.claude-plugin/` and `.codex-plugin/` expose the directories under `skills/`. Each script is also directly executable with Python and does not depend on an agent host.

## Installation

### Run from a clone

Python 3.10 or later is required.

```bash
git clone https://github.com/Trac3r00/agent-skills.git
cd agent-skills
```

Five tools use only the Python standard library. `context-budget` also runs without third-party packages, but uses the `cl100k_base` tokenizer when `tiktoken` is installed and otherwise falls back to an approximate character-based count.

```bash
python3 -m pip install tiktoken  # optional, for tokenizer-based context counts
```

### Install as a plugin

Claude Code:

```bash
claude plugin marketplace add Trac3r00/agent-skills
claude plugin install agent-guards@agent-guards
```

Codex:

```bash
codex plugin marketplace add Trac3r00/agent-skills
codex plugin add agent-guards@agent-guards
```

The plugin installs all six skills together. To use individual skills without the plugin, copy the relevant directory from `skills/` into the skills directory supported by your agent host.

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

No CI workflow is currently included in this repository.

## Project structure

```text
.
├── .claude-plugin/       # Claude Code marketplace and plugin metadata
├── .codex-plugin/        # Codex plugin metadata
├── skills/               # Skill instructions and standalone Python CLIs
├── tests/test_skills.py  # End-to-end CLI tests
├── LICENSE
└── README.md
```

## License

Licensed under the [MIT License](LICENSE).
