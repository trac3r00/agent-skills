---
name: session-finder
description: Detects and administers currently RUNNING AI agent sessions on this machine — Claude Code, Codex, OMO/Senpi, gjc, Hermes, OpenCode, aider, Cursor, Gemini CLI — at the process level. Status summary with client grouping and uptime, watch mode, and safe kill (SIGTERM only, validated to refuse non-agent PIDs). Complements session-handoff (which reads completed session logs) — this watches live processes.
when_to_use: "How many agents are running right now?", "which client is that runaway process?", "kill the stuck Claude session", or admin/monitoring workflows over multiple agent clients. NOT a session log reader (session-handoff) or a process manager for non-agent processes.
version: 1.0.0
license: MIT
metadata:
  agentskills:
    tags: [sessions, processes, monitoring, admin, multi-agent]
---

# Session Finder

Which AI agents are running right now, and what do you do about them.

## Commands

```bash
python3 scripts/session_finder.py              # one-shot scan
python3 scripts/session_finder.py --json       # machine-readable
python3 scripts/session_finder.py --watch 10   # re-scan every 10s
python3 scripts/session_finder.py --kill 85819 # SIGTERM (validated)
python3 scripts/session_finder.py --match "my-custom-agent"
```

## Detection

Process-level via `ps`: matches command lines against known agent patterns
(claude, codex, omo/senpi, gajae-code, hermes, opencode, aider, cursor,
gemini). Excludes itself, greps, and the agent-skills test harness. Groups
by client with per-process PID, parent PID, uptime, and command.

## Safe kill

`--kill PID` validates the PID against a fresh detection scan before sending
SIGTERM — it refuses any process that does not match an agent pattern, so
you cannot accidentally kill a system process. SIGTERM only (no SIGKILL);
a hung agent that ignores SIGTERM is your call to handle manually.

## Pairs with

`session-handoff` (read the logs of sessions you found here),
`usage-audit` (token accounting for those same clients),
`session-rules` (corrections from those sessions).
