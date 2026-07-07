# agent-skills

Three production-tested [Agent Skills](https://agentskills.io) for people running **real, long-lived AI agents** — the kind that accrete context, assert things without evidence, and talk across surfaces that don't share a brain. All three ship as small, dependency-light Python tools you can run standalone, drop into CI, or load as a skill in Claude Code, Codex, OpenCode, and any agent that follows the open [Agent Skills standard](https://agentskills.io/specification).

Most skill directories are full of prompt wrappers. These are **runnable tools that return an exit code** — they hold a line, not just a vibe.

| Skill | What it does | Why it's rare |
|-------|--------------|---------------|
| [`context-budget`](skills/context-budget) | Audits an agent's per-turn context window like a cost center — ranks what actually eats tokens (system prompt, skills, memory, tool schemas, gate code) and **fails CI when the agent gets fatter**. | Everyone talks about "context engineering"; almost nobody gives you a ruler with a budget you can enforce. |
| [`claim-audit`](skills/claim-audit) | A linter for AI answers: separates **grounded / hedged / bare** factual claims and surfaces the unverified hard assertions most likely to be hallucinations. Gates a reply before it ships. | Fact-checkers are heavy and online; this is an offline, instant triage of *which* claims to verify. |
| [`open-loops`](skills/open-loops) | Extracts the **unresolved commitments, deferrals, decisions, and open questions** from a thread into a JSON ledger — so a cron job or fresh session picks them up instead of dropping them. | The conversation surface and the scheduled surface never share memory; this is the missing handoff between them. |

## Quick start

```bash
git clone https://github.com/trac3r00/agent-skills
cd agent-skills

# 1) Where do my agent's tokens actually go?
python skills/context-budget/scripts/context_budget.py \
    ~/.agent/system_prompt.md ~/.agent/skills ~/.agent/memory \
    --budget 40000 --top 15

# 2) Which claims in this answer are unsupported?
echo "The capital of Australia is Sydney. See https://example.com for details." \
  | python skills/claim-audit/scripts/claim_audit.py -

# 3) What did the thread leave open for a later job to pick up?
printf '[me] charge the car tonight\n[bot] set the charge later\n' \
  | python skills/open-loops/scripts/open_loops.py -
```

`context-budget` uses `tiktoken` when available and falls back to a calibrated
`chars/4` estimate otherwise, so it never hard-fails on a fresh box. `claim-audit`
and `open-loops` are pure standard library — zero dependencies.

## Use them in CI

Both tools return a non-zero exit code when a threshold is crossed, so they wire
straight into a pre-commit hook or GitHub Actions:

```yaml
# .github/workflows/agent-guards.yml
- name: Context budget
  run: python skills/context-budget/scripts/context_budget.py PATHS --budget 40000
- name: Claim audit on golden answers
  run: python skills/claim-audit/scripts/claim_audit.py answers/*.txt --fail-over 0.4
- name: Open-loop handoff hygiene
  run: python skills/open-loops/scripts/open_loops.py thread.jsonl --max-open 8
```

"The agent got fatter" and "the answer is mostly unsupported assertions" now fail
the build instead of silently costing money or shipping hallucinations.

## Install straight into Claude Code or Codex

This repo ships as a **plugin marketplace** for both agents — one line, no manual copying:

```bash
# Claude Code
claude plugin marketplace add trac3r00/agent-skills
claude plugin install agent-guards@agent-guards

# Codex
codex plugin marketplace add trac3r00/agent-skills
codex plugin add agent-guards@agent-guards
```

All three skills (`context-budget`, `claim-audit`, `open-loops`) load together as
the `agent-guards` plugin. In Claude Code the plugin reports its own always-on
token cost (~460 tokens) via `claude plugin details agent-guards` — the same
context-budget discipline the skills enforce, applied to themselves.

## Or load as a plain Agent Skill

Each skill folder is also a standalone Agent Skill (`SKILL.md` + `scripts/`). Point
your agent's skills directory at `skills/`, or copy a folder into `~/.claude/skills/`,
`~/.codex/skills/`, or your Hermes `skills/` dir.

## Design notes

Both tools came out of running a production autonomous agent whose gate layer
grew to **214,588 tokens across 83 files** — a single quality gate eating 10.7% of
the window on every request. `context-budget` is the instrument that made that
visible; `claim-audit` is the reflex that keeps its answers honest. The heuristics
are deliberately simple and transparent — you can read the whole thing in one sitting
and trust what it flags.

## License

MIT — see [LICENSE](LICENSE).
