# Herdr agent integrations

An integration is the piece that lets Herdr *see* a coding agent. Without it, a pane is
just a terminal: Herdr cannot classify `idle`/`working`/`blocked`/`done`, cannot show the
agent's conversation title in the sidebar, and cannot resume that agent's native session
after a server restart.

Installed integrations are the only supported source of that signal. They work by calling
Herdr's own API from inside the client:

- `pane.report_agent` - lifecycle state (`idle`, `working`, `blocked`, `unknown`) with
  `source`, `agent`, `seq`, optional `message`
- `pane.report_agent_session` - session identity/ref (`agent_session_id`,
  `agent_session_path`, `session_start_source`) used for titles and resume
- `pane.release_agent` - drop lifecycle authority when the agent exits or is replaced
- `pane.report_metadata` - display-only title/labels/tokens

Each integration script starts by checking it is actually inside a Herdr pane
(`HERDR_ENV=1`, `HERDR_PANE_ID`, `HERDR_SOCKET_PATH`) and exits silently otherwise, so
running the same client outside Herdr is unaffected.

## Managing integrations

```bash
herdr integration status                     # every target: path, version, current/outdated
herdr integration status --outdated-only     # only what needs reinstalling
herdr integration install <target>           # install or upgrade
herdr integration uninstall <target>
```

- Installing **overwrites** the managed file; installed files carry
  `HERDR_INTEGRATION_ID` / `HERDR_INTEGRATION_VERSION` markers and a header telling you to
  add custom hooks *beside* the file, never inside it.
- After `herdr update`, run `herdr integration status --outdated-only` and reinstall what
  it lists; client and server features can otherwise skew.
- Targets (18): `pi`, `omp`, `claude`, `codex`, `copilot`, `devin`, `droid`, `kimi`,
  `opencode`, `kilo`, `hermes`, `qodercli`, `qwen`, `cursor`, `mastracode`,
  `antigravity-cli`, `grok`, `letta` (experimental).

## What each target wires up

Paths below were observed on this workstation with `herdr integration status`
(herdr 0.9.1, 2026-09-22). Version numbers are the integration's own, not Herdr's.

| Target | Installed path | Observed version |
|--------|----------------|------------------|
| `pi` | `~/.pi/agent/extensions/herdr-agent-state.ts` | v9, current |
| `omp` | `~/.omp/agent/extensions/herdr-omp-agent-state.ts` | not installed |
| `claude` | `~/.claude/hooks/herdr-agent-state.sh` | v10, current |
| `codex` | `~/.codex/herdr-agent-state.sh` | v8, current |
| `copilot` | `~/.copilot/hooks/herdr-agent-state.sh` | not installed |
| `devin` | `~/.config/devin/herdr-agent-state.sh` | not installed |
| `droid` | `~/.factory/hooks/herdr-agent-state.sh` | not installed |
| `kimi` | `~/.kimi-code/hooks/herdr-agent-state.sh` | v7, current |
| `opencode` | `~/.config/opencode/plugins/herdr-agent-state.js` plus `~/.config/opencode/herdr-tui-session.js` and `~/.config/opencode/herdr-opencode/tui.js` | v12, current |
| `kilo` | `~/.config/kilo/plugin/herdr-agent-state.js` | not installed |
| `hermes` | `~/.hermes/plugins/herdr-agent-state/` (`__init__.py` + `plugin.yaml`) | v5, current |
| `qodercli` | `~/.qoder/hooks/herdr-agent-state.sh` | not installed |
| `qwen` | `~/.qwen/hooks/herdr-agent-session.sh` | not installed |
| `cursor` | `~/.cursor/herdr-agent-state.sh` | not installed |
| `mastracode` | `~/.mastracode/hooks/herdr-agent-state.sh` | not installed |
| `antigravity-cli` | `~/.gemini/config/hooks/herdr-agent-state.sh` | not installed |
| `grok` | `~/.grok/hooks/herdr-agent-state.sh` (+ `~/.grok/hooks/herdr.json` registering it on `SessionStart`) | v2, current |
| `letta` | `~/.letta/hooks/herdr-agent-session.sh` (experimental) | not installed |

Two shapes are in play: hook-based clients (Claude Code, Codex, Kimi, Grok, Cursor,
Copilot, Devin, Droid, Qoder, Qwen, Mastracode, Antigravity, Letta) get a script plus a
session-start hook registration; extension/plugin-based clients (pi, omp, OpenCode, Kilo,
Hermes) get an extension module the client loads itself. The hook script reads the client's
hook payload from stdin, ignores subagent sessions, and reports only real session starts.

## Agents you can start vs agents Herdr can detect

`herdr agent start --kind` accepts **24 kinds**: `pi`, `claude`, `codex`, `gemini`,
`cursor`, `devin`, `agy`, `cline`, `omp`, `mastracode`, `opencode`, `copilot`, `kimi`,
`kiro`, `droid`, `amp`, `grok`, `hermes`, `kilo`, `qodercli`, `qwen`, `letta`, `maki`,
`muse`. Integration targets are a smaller set (18) - Herdr can *launch* more agents than it
can *classify* through an integration. Starting a kind without an installed integration
still works; lifecycle state just falls back to screen-based detection, which is less
reliable and can report `unknown`.

## Detection manifests

Classification rules ship as versioned manifests and update independently of the binary:

```bash
herdr server agent-manifests --json           # active version + source per agent
herdr server update-agent-manifests --json    # fetch remote updates, then reload
herdr server reload-agent-manifests           # reload local overrides only
```

Manifest sources resolve from `~/.local/state/herdr/agent-detection/remote/<agent>.toml`;
per-agent overrides live under `~/.local/state/herdr/agent-detection/status.toml` and can
shadow the remote version (`local_override_shadowing_remote`). `[update] manifest_check` in
`config.toml` controls background checking.

When detection disagrees with reality, ask Herdr why rather than guessing:

```bash
herdr agent explain <target> -v
herdr agent explain --file screen.txt --agent claude -v   # classify a captured screen
```

## Verifying an install end to end

```bash
herdr integration status                                   # 1. path + version, expect "current"
herdr server reload-config                                 # 2. only if config changed
# 3. inside the client, inside a Herdr pane: start a new session
herdr agent list                                           # 4. the client appears with a name and status
herdr agent explain <target> -v                            # 5. classification reasoning
herdr agent read <target> --source detection --lines 40    # 6. what Herdr saw on screen
```

Expected: `agent` = the client's kind label, `agent_status` moving `idle` -> `working` ->
`idle`/`done` as you interact, `title` reflecting the client's conversation, and
`agent_session` populated for clients that report session refs
(`session.resume_agents_on_restore` then covers restarts).

For the client-facing half - prompts, waits, blocked dialogs, key injection - see the
recipes in `../SKILL.md`; `agent explain` and `agent read --source detection` are the two
tools that make a misclassification debuggable instead of mysterious.
