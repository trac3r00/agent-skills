# Herdr CLI reference

Complete flag-level reference for `herdr 0.9.1` (protocol 22). The installed binary is the
authority: `herdr --help`, `herdr <group> --help`, `herdr <group> <sub> --help`.
Anything with `[OPTIONS]` also accepts the global selectors below.

## Global flags

| Flag | Meaning |
|------|---------|
| `--session <name>` | Use or create a named persistent session (own server, socket, directory) |
| `--machine <label-or-id>` | Run an API command against a saved SSH machine profile |
| `--remote <ssh-target>` | Attach through SSH to a remote Herdr server |
| `--remote-keybindings <local\|server>` | Keybinding source for `--remote app attach` (default `local`) |
| `--handoff` | Opt into live handoff for `update` or remote attach |
| `--default-config` | Print the annotated default configuration and exit |
| `--skill` | Print the bundled agent skill and exit |
| `--version`, `-V` | Print version |
| `--help`, `-h` | Help for the current level |

`--machine` must not be combined with `--session` or `--remote`.

Top-level commands: `herdr` (launch/attach TUI), `herdr status [server|client] [--json]`,
`herdr update [--handoff]`, `herdr completion <shell>`, `herdr channel <show|set>`,
`herdr config <check|reset-keys>`, `herdr server [...]`, `herdr api <snapshot|schema>`,
`herdr workspace [...]`, `herdr worktree [...]`, `herdr tab [...]`,
`herdr notification show`, `herdr agent [...]`, `herdr pane [...]`, `herdr session [...]`,
`herdr machine [...]`, `herdr integration [...]`.

Exit codes: `0` ok; `1` server/API error (JSON error object on stderr); `2` CLI syntax error.

## workspace

| Subcommand | Usage |
|------------|-------|
| `list` | `herdr workspace list` - all workspaces with `workspace_id`, `label`, `number`, `active_tab_id`, `tab_count`, `pane_count`, `agent_status`, `focused` |
| `create` | `herdr workspace create [--cwd PATH] [--label TEXT] [--env KEY=VALUE]... [--focus\|--no-focus]` -> `.result.workspace`, `.result.tab`, `.result.root_pane` |
| `get` | `herdr workspace get <workspace_id>` |
| `focus` | `herdr workspace focus <workspace_id>` |
| `rename` | `herdr workspace rename <workspace_id> <LABEL>...` |
| `report-metadata` | `herdr workspace report-metadata --source <ID> <WORKSPACE_ID> [--token NAME=VALUE]... [--clear-token NAME]... [--seq N] [--ttl-ms N]` |
| `close` | `herdr workspace close <workspace_id>` (socket param `close_group` also closes linked worktree workspaces) |

`--env KEY=VALUE` sets an environment variable for the launched process. `report-metadata`
is display-only: it feeds sidebar tokens such as `$name` and never changes real state.

## tab

| Subcommand | Usage |
|------------|-------|
| `list` | `herdr tab list [--workspace WORKSPACE_ID]` |
| `create` | `herdr tab create [--workspace WORKSPACE_ID] [--cwd PATH] [--label TEXT] [--env KEY=VALUE]... [--focus\|--no-focus]` -> `.result.tab`, `.result.root_pane` |
| `get` | `herdr tab get <tab_id>` |
| `focus` | `herdr tab focus <tab_id>` |
| `rename` | `herdr tab rename <TAB_ID> <LABEL>...` |
| `close` | `herdr tab close <tab_id>` |

## pane

Target selectors used throughout: positional `<PANE_ID>` / `<pane_id>`, or `--pane <ID>`,
or `--current` (your own pane, from `HERDR_PANE_ID`).

| Subcommand | Usage and notes |
|------------|-----------------|
| `list` | `herdr pane list [--workspace WORKSPACE_ID]` - includes `scroll` info (`max_offset_from_bottom`, `offset_from_bottom`, `viewport_rows`) |
| `current` | `herdr pane current [--pane ID] [--current]` |
| `get` | `herdr pane get <pane_id>` |
| `layout` | `herdr pane layout [--pane ID] [--current]` -> `area`, `panes[].rect`, `splits[]`, `focused_pane_id`, `zoomed` |
| `process-info` | `herdr pane process-info [--pane ID] [--current]` - foreground process group and argv |
| `neighbor` | `herdr pane neighbor --direction <left\|right\|up\|down> [--pane ID] [--current]` |
| `edges` | `herdr pane edges [--pane ID] [--current]` - which sides are outer edges |
| `focus` | `herdr pane focus --direction <left\|right\|up\|down> [--pane ID] [--current]` |
| `resize` | `herdr pane resize --direction <left\|right\|up\|down> [--amount FLOAT] [--pane ID] [--current]` |
| `zoom` | `herdr pane zoom [PANE_ID] [--pane ID] [--current] [--toggle\|--on\|--off]` |
| `read` | `herdr pane read <PANE_ID> [--source visible\|recent\|recent-unwrapped\|detection] [--lines N] [--format text\|ansi] [--ansi] [--raw]` |
| `rename` | `herdr pane rename <PANE_ID> [LABEL]... [--clear]` |
| `input` | `herdr pane input --right-click <herdr\|pane> [PANE_ID] [--pane ID] [--current]` |
| `split` | `herdr pane split [PANE_ID] [--pane ID] [--current] [--direction right\|down] [--ratio FLOAT] [--cwd PATH] [--env KEY=VALUE]... [--right-click herdr\|pane] [--focus\|--no-focus]` -> `.result.pane` |
| `swap` | `herdr pane swap [--direction left\|right\|up\|down] [--pane ID] [--current] [--source-pane ID] [--target-pane ID]` |
| `move` | `herdr pane move <PANE_ID> [--tab TAB_ID] [--split right\|down] [--target-pane ID] [--ratio FLOAT] [--new-tab] [--workspace ID] [--new-workspace] [--label TEXT] [--tab-label TEXT] [--focus\|--no-focus]` |
| `close` | `herdr pane close <pane_id>` |
| `send-text` | `herdr pane send-text <PANE_ID> <TEXT>` - literal text, no Enter |
| `send-keys` | `herdr pane send-keys <PANE_ID> <KEY>...` - `esc` is canonical (`escape` accepted) |
| `wait-output` | `herdr pane wait-output (--match TEXT \| --regex PATTERN) <PANE_ID> [--source visible\|recent\|recent-unwrapped] [--lines N] [--timeout MS] [--raw]` |
| `run` | `herdr pane run <PANE_ID> <COMMAND>...` - sends command text **and** Enter atomically |
| `report-agent` | `herdr pane report-agent --source ID --agent LABEL --state <idle\|working\|blocked\|unknown> <PANE_ID> [--message TEXT] [--seq N] [--agent-session-id ID] [--agent-session-path PATH]` |
| `report-agent-session` | `herdr pane report-agent-session --source ID --agent LABEL <PANE_ID> [--seq N] [--agent-session-id ID] [--agent-session-path PATH] [--session-start-source SOURCE]` |
| `release-agent` | `herdr pane release-agent --source ID --agent LABEL <PANE_ID> [--seq N]` - drop lifecycle authority |
| `report-metadata` | `herdr pane report-metadata --source ID <PANE_ID> [--agent LABEL] [--applies-to-source ID] [--title TEXT \| --clear-title] [--display-agent TEXT \| --clear-display-agent] [--state-label STATUS=TEXT \| --clear-state-labels] [--token NAME=VALUE \| --clear-token NAME] [--seq N] [--ttl-ms N]` |

Read sources: `visible` = current viewport; `recent` = recent rendered rows (default);
`recent-unwrapped` = same with soft wraps joined; `detection` = plain-text bottom-buffer
snapshot used by agent detection. `--raw` keeps ANSI even when matching/formatting.

`*agent*` reporting commands are what Herdr's own client integrations call; use them when
building a new integration, not for ordinary control.

## agent

Targets are a unique live agent name or the pane ID hosting it.

| Subcommand | Usage and notes |
|------------|-----------------|
| `list` | `herdr agent list` -> `agents[]` with `pane_id`, `agent`, `agent_status`, `cwd`, `focused`, `title`, `terminal_title`, `state_change_seq` |
| `get` | `herdr agent get <target>` |
| `read` | `herdr agent read <TARGET> [--source visible\|recent\|recent-unwrapped\|detection] [--lines N] [--format text\|ansi] [--ansi]` |
| `send-keys` | `herdr agent send-keys <TARGET> <KEY>...` |
| `prompt` | `herdr agent prompt <TARGET> <TEXT> [--wait] [--until <idle\|working\|blocked\|done\|unknown>]... [--timeout <MS>]` |
| `rename` | `herdr agent rename <TARGET> <NAME> \| --clear` |
| `focus` | `herdr agent focus <target>` |
| `wait` | `herdr agent wait <TARGET> [--until <STATUS>]... [--timeout <MS>]` |
| `attach` | `herdr agent attach <TARGET> [--takeover]` |
| `start` | `herdr agent start <NAME> --kind <KIND> --pane <ID> [--timeout <MS>] [-- <AGENT_ARG>...]` |
| `explain` | `herdr agent explain [TARGET] [--file PATH --agent LABEL] [--json] [--format text\|json] [-v\|--verbose]` |

`agent start` kinds: `pi`, `claude`, `codex`, `gemini`, `cursor`, `devin`, `agy`, `cline`,
`omp`, `mastracode`, `opencode`, `copilot`, `kimi`, `kiro`, `droid`, `amp`, `grok`,
`hermes`, `kilo`, `qodercli`, `qwen`, `letta`, `maki`, `muse`. Startup timeout default
30000 ms, max 300000 ms (values must exceed 3000). Success means the expected agent was
detected in the same terminal and is ready for input.

`agent prompt` semantics: already-blocked agent -> `agent_blocked` with no input written;
accepted prompt from a non-working state must show `working`/`blocked` within 5000 ms or
`agent_prompt_stalled`; caller `--timeout` expiring first -> `timeout`; default match set
for `--wait` (and `agent wait` without `--until`) is `idle`, `done`, `blocked`. It tracks
lifecycle state, not an individual turn.

## worktree

| Subcommand | Usage |
|------------|-------|
| `list` | `herdr worktree list [--workspace ID] [--cwd PATH] [--trust-repository]` |
| `create` | `herdr worktree create [--workspace ID] [--cwd PATH] [--branch NAME] [--base REF] [--path PATH] [--label TEXT] [--focus\|--no-focus] [--trust-repository]` |
| `open` | `herdr worktree open [--workspace ID] [--cwd PATH] [--path PATH] [--branch NAME] [--label TEXT] [--focus\|--no-focus] [--trust-repository]` |
| `remove` | `herdr worktree remove [--workspace ID] [--force] [--trust-repository]` |

Requires a workspace inside a Git work tree (`not_git_worktree` otherwise). On remote
machines, worktree paths must be absolute, `~`, or `~/...`.

## session

| Subcommand | Usage |
|------------|-------|
| `list` | `herdr session list [--json]` -> `sessions[]` with `name`, `running`, `default`, `session_dir`, `socket_path` |
| `attach` | `herdr session attach <NAME>` (interactive) |
| `stop` | `herdr session stop [--json] <NAME>` |
| `delete` | `herdr session delete [--json] <NAME>` - stopped sessions only |

Create/use a session non-interactively with the global `--session <name>`.

## machine

| Subcommand | Usage |
|------------|-------|
| `list` | `herdr machine list [--json]` - saved connection profiles, not a pane inventory |
| `add` | `herdr machine add --label <LABEL> <SSH_TARGET> [--remote-session NAME]` |
| `rename` | `herdr machine rename --label <LABEL> <PROFILE_ID>` |
| `remove` | `herdr machine remove <PROFILE_ID>` - disconnects the client, does not stop remote sessions |
| `enable` | `herdr machine enable <PROFILE_ID>` |
| `disable` | `herdr machine disable <PROFILE_ID>` |

## integration

| Subcommand | Usage |
|------------|-------|
| `install` | `herdr integration install <TARGET>` (overwrites managed integration files) |
| `uninstall` | `herdr integration uninstall <TARGET>` |
| `status` | `herdr integration status [--outdated-only]` |

Targets: `pi`, `omp`, `claude`, `codex`, `copilot`, `devin`, `droid`, `kimi`, `opencode`,
`kilo`, `hermes`, `qodercli`, `qwen`, `cursor`, `mastracode`, `antigravity-cli`, `grok`,
`letta`.

## notification

`herdr notification show <TITLE> [--body TEXT] [--position <top-left|top-right|bottom-left|bottom-right>] [--sound <none|done|request>]`

## config

| Subcommand | Usage |
|------------|-------|
| `check` | `herdr config check` - validate `config.toml`, print diagnostics |
| `reset-keys` | `herdr config reset-keys` - back up `config.toml` and remove custom keybindings |

## channel

`herdr channel show` | `herdr channel set <stable|preview>`.

## server

| Subcommand | Usage |
|------------|-------|
| (bare) | `herdr server` - run as a headless server |
| `stop` | `herdr server stop` - stop the running server via the API socket |
| `reload-config` | `herdr server reload-config` - reload `config.toml` in the running server |
| `agent-manifests` | `herdr server agent-manifests [--json]` - active detection manifests, versions, sources |
| `update-agent-manifests` | `herdr server update-agent-manifests [--json]` - fetch and reload remote manifests |
| `reload-agent-manifests` | `herdr server reload-agent-manifests` - reload local overrides |

## api

| Subcommand | Usage |
|------------|-------|
| `snapshot` | `herdr api snapshot` - live session snapshot (`agents`, `panes`, `tabs`, `workspaces`, `layouts`, `focused_*`, `protocol`, `version`) |
| `schema` | `herdr api schema [--json] [--output PATH]` - bundled API schema |

## status

`herdr status [--json] [server|client]`. Reports client/server versions, protocol numbers,
capabilities, socket path, and `restart_needed` / `server_binary_stale` flags.

## Examples

```bash
# discover
herdr status --json
herdr workspace list
herdr tab list --workspace "$HERDR_WORKSPACE_ID"
herdr agent list
herdr pane current --current
herdr api snapshot

# layout + command
herdr pane split --current --direction right --cwd "$PWD" --no-focus
herdr pane run w1:p2 "npm test"
herdr pane wait-output w1:p2 --match "Tests:" --timeout 300000
herdr pane read w1:p2 --source recent-unwrapped --lines 200

# agent work
herdr agent start reviewer --kind claude --pane w1:p2
herdr agent prompt reviewer "Summarize the failing tests; no fixes yet." --wait --timeout 180000
herdr agent wait reviewer --until blocked --timeout 60000
herdr agent read reviewer --source recent-unwrapped --lines 80
herdr agent send-keys reviewer esc

# cleanup you created
herdr pane close w1:p2

# remote
herdr machine list --json
herdr --machine buildbox agent list

# diagnostics
herdr config check
herdr agent explain w1:p1 -v
herdr server agent-manifests --json
```
