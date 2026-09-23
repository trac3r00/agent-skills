# Clients and panes

> Engine 0 - the default - is the Pro engine in
> [pro-engine.md](pro-engine.md): ChatGPT Pro through the guarded pinned
> transport. The engines below are opt-in alternatives for when the user asks for
> a specific client or the Pro route is unavailable.


This skill ships no reviewer of its own. It drives a client you already have,
inside the terminal surface you already use. Verified on macOS, 2026-09-22,
Herdr 0.9.1.

## Engine 1: pane client (default inside Herdr)

Use when `HERDR_ENV=1`. The reviewer gets its own pane, its own working
directory, and full tool access; the user can watch or steer it.

```sh
# 1. Sibling pane in the current tab, same cwd, without stealing focus.
herdr pane split --current --direction right --cwd "$PWD" --no-focus
#    -> read the new id from .result.pane.pane_id

# 2. Launch the client. `omo` is the OmO client; see the table for others.
herdr pane run <pane-id> "omo"

# 3. Wait until the client's own UI is ready before typing.
herdr pane wait-output <pane-id> --regex "/ commands|Skills\\]" --timeout 60000 --raw

# 4. Send the brief, then submit it.
herdr pane send-text <pane-id> "<brief>"
herdr pane send-keys <pane-id> enter
```

Harvest, then keep the pane open:

```sh
herdr pane wait-output <pane-id> --match "<report-path>" --timeout 1800000 --raw
herdr pane read <pane-id> --source recent-unwrapped --lines 200
```

Rules learned from real runs:

- **Never treat a console echo as the answer.** The brief you send contains the
  report path and any marker text, so `wait-output --match` can match your own
  prompt. The artifact file is the authority: have the reviewer write
  `<cwd>/.pro-review/<slug>.md` and wait for that file (OmO can watch it with
  the monitor tool), then read it.
- `send-text` alone does not submit; send `enter` after it.
- Prefer `--no-focus`, and never close or repurpose a pane you did not create.
- Split down in a tall narrow pane, right in a wide one.
- If the client shows an approval or warning dialog, read the pane and resolve it
  per this skill's "Ask the client" section; ask the user only for what only a
  human can do.

### Client commands

| Client | Launch in pane | Herdr lifecycle | Headless one-shot |
| --- | --- | --- | --- |
| OmO | `omo` | not integrated in this install | `omo --print "<brief>"` |
| Pi (upstream) | `pi` | yes | `pi -p "<brief>"` |
| Claude Code | `claude` | yes | `claude -p "<brief>"` |
| OpenAI Codex | `codex` | yes | `codex exec "<brief>"` |
| OpenCode | `opencode` | yes | `opencode run "<brief>"` |
| Others | same as binary | check `herdr integration status` | check `<client> --help` |

Herdr's agent API is the better coordination channel **when the client is
integrated** (`herdr integration status` shows `current`):

```sh
herdr agent start reviewer --kind codex --pane <pane-id>
herdr agent prompt reviewer "<brief>" --wait --timeout 1800000
herdr agent read reviewer --source recent-unwrapped --lines 200
herdr agent get reviewer
```

`agent prompt --wait` waits for observed working activity and then a settled
state, so it avoids the echo problem entirely. Verify the integration before
relying on it: a pane-launched OmO client is **not** listed by
`herdr agent list` on this machine, so use pane commands plus the artifact
protocol for OmO.

## Engine 2: headless client (no pane)

Use outside Herdr, in scripts, or when plain stdout capture is enough. Run it
through OmO's background monitor rather than a blocking foreground wait.

```sh
omo --print --model "openai-codex/gpt-6-astra:max" "<brief>"   # OmO
codex exec "<brief>"                                           # Codex CLI
claude -p "<brief>"                                            # Claude Code
```

Keep the same discipline: name the exact scope paths, require `path:line`
citations, and add the client's no-session flag when the run should not be
stored. Do not claim a model tier the client did not report.

## Engine 3: in-session subagent

Use when Herdr is unavailable and a one-shot client is not appropriate. Spawn
OmO's own reviewer through the task tool with the same brief and scope, then
verify its findings like any other reviewer's. Prefer `omo-senpi-code-reviewer`
for a code diff and the gate reviewer for a completed change set.

## Scope and model controls

- Naming a tier: pass it explicitly, e.g.
  `omo --model "openai-codex/gpt-6-astra:xhigh"`, `codex -m gpt-5.6-sol`,
  `claude --model opus`. Otherwise the client's configured default applies.
- Record the model the client itself reports (status line, `--mode json`, or its
  own model picker). A UI label is selection evidence, not independent proof of
  backend identity; say which one you have.
- Never silently substitute a different client, model, or tier to make a run look
  successful. Report the substitution instead.
- Long reviews prefer a pane because the client keeps its own context and session;
  if it stalls, read the pane and continue that same session.
