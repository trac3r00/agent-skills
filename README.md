# agent-skills

Runnable [Agent Skills](https://agentskills.io) for people running **real, long-lived AI agents** — and for people who just want their own recurring costs audited. The agent skills tackle the messes agents make: they accrete context, assert things without evidence, and talk across surfaces that don't share a brain. The everyday skills tackle the messes *humans* let slide — like a subscription stack nobody re-reads. All ship as small, dependency-light Python tools you can run standalone, drop into CI, or load as a skill in Claude Code, Codex, OpenCode, and any agent that follows the open [Agent Skills standard](https://agentskills.io/specification).

Most skill directories are full of prompt wrappers. These are **runnable tools that return an exit code** — they hold a line, not just a vibe.

| Skill | What it does | Why it's rare |
|-------|--------------|---------------|
| [`context-budget`](skills/context-budget) | Audits an agent's per-turn context window like a cost center — ranks what actually eats tokens (system prompt, skills, memory, tool schemas, gate code) and **fails CI when the agent gets fatter**. | Everyone talks about "context engineering"; almost nobody gives you a ruler with a budget you can enforce. |
| [`claim-audit`](skills/claim-audit) | A linter for AI answers: separates **grounded / hedged / bare** factual claims and surfaces the unverified hard assertions most likely to be hallucinations. Gates a reply before it ships. | Fact-checkers are heavy and online; this is an offline, instant triage of *which* claims to verify. |
| [`open-loops`](skills/open-loops) | Extracts the **unresolved commitments, deferrals, decisions, and open questions** from a thread into a JSON ledger — so a cron job or fresh session picks them up instead of dropping them. | The conversation surface and the scheduled surface never share memory; this is the missing handoff between them. |
| [`subscription-audit`](skills/subscription-audit) | Finds the **recurring charges hiding in a bank/card CSV** — clusters repeat payments by merchant and cadence, reports the true monthly and yearly cost, and flags the **forgotten** ones (stale, or a free trial that started charging) worth cancelling. | Every "find my subscriptions" product wants a bank login; this reads a CSV you already have, fully offline, and returns an exit code you can put on a monthly cron. |
| [`gate-graph`](skills/gate-graph) | Builds an AST overlap matrix for validator/middleware gate modules, flags duplicate checks and dead gates, and fails CI when overlap or count thresholds are exceeded. | Gate layers grow quietly; this keeps validator stacks from becoming bloated without a measurable signal. |
| [`skill-decay`](skills/skill-decay) | Cross-references a declared skill/tool inventory (SKILL.md files or a name list) against **real usage logs** and classifies each capability as **never / stale / live** — so you prune the dead weight taxing every prompt with receipts, not vibes. Fails CI when decay candidates exceed a budget. | `context-budget` tells you how heavy a capability is; this tells you whether anyone actually uses it. A file that is both is the first to cut. |

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

# 4) Which subscriptions am I paying for on repeat?
python skills/subscription-audit/scripts/subscription_audit.py statement.csv --budget 80

# 5) Which validator gates are duplicate, orphaned, or over threshold?
python skills/gate-graph/scripts/gate_graph.py ./skills --max-gates 49 --max-overlap 0.5 --json
```

`context-budget` uses `tiktoken` when available and falls back to a calibrated
`chars/4` estimate otherwise, so it never hard-fails on a fresh box. `claim-audit`,
`open-loops`, and `gate-graph` are pure standard library — zero dependencies.

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
- name: Gate overlap hygiene
  run: python skills/gate-graph/scripts/gate_graph.py ./skills --max-gates 49 --max-overlap 0.5
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

All five skills (`context-budget`, `claim-audit`, `open-loops`, `subscription-audit`, `gate-graph`)
load together as the `agent-guards` plugin. In Claude Code the plugin reports its own
always-on token cost via `claude plugin details agent-guards` — the same
context-budget discipline the skills enforce, applied to themselves.

## Or load as a plain Agent Skill

Each skill folder is also a standalone Agent Skill (`SKILL.md` + `scripts/`). Point
your agent's skills directory at `skills/`, or copy a folder into `~/.claude/skills/`,
`~/.codex/skills/`, or your Hermes `skills/` dir.

## Design notes

`context-budget`, `claim-audit`, and `gate-graph` came out of running a production autonomous agent whose gate layer
grew to **214,588 tokens across 83 files** — a single quality gate eating 10.7% of
the window on every request. `context-budget` is the instrument that made that
visible; `claim-audit` is the reflex that keeps its answers honest; `gate-graph` is
the maintenance lens for duplicate and orphaned guards. The heuristics are deliberately
simple and transparent — you can read the whole thing in one sitting and trust what it flags.

## License

MIT — see [LICENSE](LICENSE).
