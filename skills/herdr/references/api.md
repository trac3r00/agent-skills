# Herdr socket API (protocol 22)

Herdr's server speaks newline-delimited JSON over a Unix socket. Every CLI verb is a thin
wrapper around one method, so anything the CLI can do is scriptable directly, and the
schema exposes capabilities the 0.9.1 CLI does not surface as subcommands (plugins, event
streaming, layout capture/restore, graphics, selections).

- Session socket: `~/.config/herdr/herdr.sock` (per named session: its own
  `session_dir` + `socket_path`, listed by `herdr session list --json`)
- Client socket: `~/.config/herdr/herdr-client.sock`
- Client PID record: `~/.local/state/herdr/client-shell/local-<hash>.json`
- Windows endpoint form used by integrations: `\\.\pipe\<socketPath>`
- Protocol: `22`; bundled schema `schema_version` 1; schemas: `request`,
  `success_response`, `error_response`, `event`, `subscription_event`
- Print the schema: `herdr api schema --json` (or `--output PATH`)
- Live state: `herdr api snapshot`

## Framing and envelopes

One JSON object per line. Requests carry an `id` you choose; every response echoes it.

```json
{"id":"cli:pane:get","method":"pane.get","params":{"pane_id":"w1:p1"}}
{"id":"cli:pane:get","result":{"type":"pane_info","pane":{"pane_id":"w1:p1","agent_status":"idle"}}}
{"id":"cli:pane:get","error":{"code":"pane_not_found","message":"pane w99:p9 not found"}}
```

Observed request ids follow `<surface>:<group>:<verb>` (`cli:agent:list`,
`cli:workspace:list`, `cli:api:snapshot`). Use your own stable ids; they are opaque.

| Schema | Required | Shape |
|--------|----------|-------|
| `request` | `id`, `method`, `params` | `{"id":string,"method":string,"params":object}`; `method` is a `const` per variant, `params` resolves to a per-method `*Params` definition |
| `success_response` | `id`, `result` | result body varies by method and usually repeats a `type` discriminator |
| `error_response` | `id`, `error{code,message}` | `{"id":string,"error":{"code":string,"message":string}}` |
| `event` | `id`, event payload | server-pushed session events, `EventData` is a tagged union |
| `subscription_event` | `event`, `data` | pushed by `events.subscribe`: `pane.output_matched`, `pane.agent_status_changed`, `pane.scroll_changed` |

`ping` (`params: {}`) is the health check; `herdr status --json` reports the server's
`capabilities` (`live_handoff`, `detached_server_daemon`, `surface_interest`,
`health_check`) and `endpoint_protocol_generation`.

## Methods (103)

`agent.*`
`agent.list`, `agent.get`, `agent.focus`, `agent.read`, `agent.send_keys`, `agent.prompt`,
`agent.rename`, `agent.start`, `agent.wait`, `agent.explain`,
`agent.view.set`, `agent.view.clear`

`pane.*`
`pane.list`, `pane.get`, `pane.current`, `pane.layout`, `pane.edges`, `pane.neighbor`,
`pane.focus`, `pane.focus_direction`, `pane.resize`, `pane.zoom`, `pane.read`, `pane.rename`,
`pane.process_info`, `pane.input.set`, `pane.split`, `pane.swap`, `pane.move`, `pane.close`,
`pane.send_text`, `pane.send_keys`, `pane.send_input`, `pane.wait_for_output`,
`pane.scroll`, `pane.selection.read`, `pane.copy_search`, `pane.copy_motion`,
`pane.edit_scrollback`, `pane.link.activate`, `pane.link.resolve`,
`pane.graphics.set`, `pane.graphics.info`, `pane.graphics.clear`,
`pane.report_agent`, `pane.report_agent_session`, `pane.report_metadata`,
`pane.release_agent`, `pane.clear_agent_authority`

`workspace.*` / `tab.*` / `worktree.*`
`workspace.list`, `workspace.create`, `workspace.get`, `workspace.focus`,
`workspace.rename`, `workspace.move`, `workspace.move_block`, `workspace.close`,
`workspace.report_metadata`;
`tab.list`, `tab.create`, `tab.get`, `tab.focus`, `tab.rename`, `tab.move`, `tab.close`;
`worktree.list`, `worktree.create`, `worktree.open`, `worktree.remove`

`layout.*`
`layout.export` (`pane_id`/`tab_id` -> `LayoutNode` tree), `layout.apply`
(`root`, optional `workspace_id`/`tab_id`/`tab_label`, `focus`),
`layout.set_split_ratio`

`events.*` / `command.*` / `session.*`
`events.subscribe` (`subscriptions[]`), `events.wait` (`match_event`, `timeout_ms`);
`command.invoke` (run a client-shell command by opaque `command_id`, with optional
`pane_id`/`tab_id`/`workspace_id`/`selection`);
`session.snapshot` (same document as `herdr api snapshot`)

`server.*` / `client*`
`server.stop`, `server.live_handoff`, `server.reload_config`, `server.agent_manifests`,
`server.reload_agent_manifests`;
`client.window_title.set`, `client.window_title.clear`, `client_shell.surface.set`
(whether the requesting client shell receives and controls pane presentation)

`integration.*` / `notification.*` / `popup.*`
`integration.list`, `integration.install`, `integration.uninstall`;
`notification.show` (`title`, optional `body`/`position`/`sound`);
`popup.close`

`plugin.*`
`plugin.list`, `plugin.link` (`path`, optional `source`, `enabled`), `plugin.unlink`,
`plugin.enable`, `plugin.disable`, `plugin.action.list`, `plugin.action.invoke`,
`plugin.pane.open` (entrypoint, placement/direction, `cwd`, `env`, `focus`, popup
`width`/`height` as cells or `NN%`), `plugin.pane.focus`, `plugin.pane.close`,
`plugin.log.list`

`misc`
`ping`, `product_announcement.dismiss`, `release_notes.dismiss`

Group totals: agent 12, pane 37, workspace 9, tab 7, worktree 4, layout 3, events 2,
command 1, session 1, server 5, client 3, integration 3, notification 1, popup 1,
plugin 11, misc 3 = **103**.

Notable params: `AgentStartParams.timeout_ms` must be > 3000 and <= 300000.
`WorkspaceCloseParams.close_group` also closes linked worktree workspaces.
`PaneReportMetadataParams` accepts at most 16 tokens (name pattern `[A-Za-z0-9_-]{1,32}`)
plus `ttl_ms`; `PaneWaitForOutputParams` takes literal or pattern matching plus a snapshot
source and line cap.

## Events (26)

`layout_updated`, `pane_agent_detected`, `pane_agent_status_changed`, `pane_closed`,
`pane_created`, `pane_exited`, `pane_focused`, `pane_moved`, `pane_output_changed`,
`pane_updated`, `tab_closed`, `tab_created`, `tab_focused`, `tab_moved`, `tab_renamed`,
`workspace_closed`, `workspace_created`, `workspace_focused`,
`workspace_metadata_updated`, `workspace_moved`, `workspace_renamed`,
`workspace_reordered`, `workspace_updated`, `worktree_created`, `worktree_opened`,
`worktree_removed`

`events.wait` takes an `EventMatch` restricted to 19 of these: `workspace_created`,
`workspace_updated`, `workspace_closed`, `workspace_renamed`, `workspace_moved`,
`workspace_focused`, `tab_created`, `tab_closed`, `tab_renamed`, `tab_moved`,
`tab_focused`, `pane_created`, `pane_closed`, `pane_focused`, `pane_moved`,
`pane_output_changed`, `pane_exited`, `pane_agent_detected`, `pane_agent_status_changed`
(each optionally narrowed by `workspace_id`, `pane_id`, `tab_id`, `label`).

## Subscriptions (27)

`events.subscribe` takes `subscriptions: [{"type": "<name>", ...}]`:

`workspace.created`, `workspace.updated`, `workspace.metadata_updated`,
`workspace.renamed`, `workspace.moved`, `workspace.reordered`, `workspace.closed`,
`workspace.focused`, `worktree.created`, `worktree.opened`, `worktree.removed`,
`tab.created`, `tab.closed`, `tab.focused`, `tab.renamed`, `tab.moved`,
`pane.created`, `pane.closed`, `pane.updated`, `pane.focused`, `pane.moved`,
`pane.exited`, `pane.agent_detected`, `pane.output_matched`,
`pane.agent_status_changed`, `pane.scroll_changed`, `layout.updated`

Pushed subscription envelopes carry `event` (kind) plus `data`:

- `pane.agent_status_changed` -> `pane_id`, `workspace_id`, `agent_status`, optional
  `agent`, `display_agent`, `title`, `state_labels`
- `pane.output_matched` -> `pane_id`, `matched_line`, `read` (a full `PaneReadResult`:
  `workspace_id`, `tab_id`, `source`, `format`, `text`, `revision`, `truncated`)
- `pane.scroll_changed` -> `pane_id`, `workspace_id`, `scroll`

`AgentStatus` enum used everywhere: `idle`, `working`, `blocked`, `done`, `unknown`.
`ReadSource`: `visible`, `recent`, `recent-unwrapped`, `detection`. `ReadFormat`:
`text`, `ansi`.

## Snapshot document

`herdr api snapshot` / `session.snapshot` returns:

```
{
  "protocol": 22, "version": "0.9.1",
  "focused_workspace_id": "w1H", "focused_tab_id": "w1H:t1", "focused_pane_id": "w1H:p1",
  "workspaces": [{"workspace_id","label","number","active_tab_id","tab_count","pane_count","agent_status","focused"}],
  "tabs":       [{"tab_id","workspace_id","label","number","pane_count","agent_status","focused"}],
  "panes":      [{"pane_id","workspace_id","tab_id","terminal_id","revision","agent","agent_status",
                  "cwd","foreground_cwd","title","terminal_title","terminal_title_stripped",
                  "display_agent","focused","scroll":{"max_offset_from_bottom","offset_from_bottom","viewport_rows"}}],
  "agents":     [ ...panes with an agent, same fields plus "state_change_seq" ],
  "layouts":    [{"workspace_id","tab_id","focused_pane_id","zoomed","area","panes"[{"rect"}],"splits"}]
}
```

`agent.list` / `pane.list` return the same record shape; `AgentInfo` in the success schema
also documents `name`, `interactive_ready`, `launch_pending`, `screen_detection_skipped`,
`state_labels`, `tokens`, and `agent_session{source,agent,kind:id|path,value}`.

## Errors

Error responses are `{"id": ..., "error": {"code": ..., "message": ...}}`; the CLI prints
them on stderr and exits 1. Observed live:

| Code | Meaning |
|------|---------|
| `pane_not_found` | Unknown pane id (`pane w99:p9 not found`) |
| `agent_not_found` | Unknown agent name/pane target (`agent target nosuchagent not found`) |
| `not_git_worktree` | Worktree action outside a Git work tree |
| `agent_blocked` | `agent prompt` refused because the agent is at an approval/question dialog |
| `agent_prompt_stalled` | No `working`/`blocked` activity observed within 5000 ms of an accepted prompt |
| `agent_not_ready` | `agent start` returned while the agent was blocked during startup (name stays usable) |
| `timeout` | Caller timeout expired before a matching state |

CLI syntax errors exit 2. A connection or forwarding failure does not prove a mutation was
not applied - inspect remote state before retrying.

## Environment injected into panes

| Variable | Value |
|----------|-------|
| `HERDR_ENV` | `1` inside a Herdr-managed pane |
| `HERDR_PANE_ID` | caller pane, e.g. `w1J:p1` |
| `HERDR_WORKSPACE_ID` | caller workspace, e.g. `w1J` |
| `HERDR_TAB_ID` | caller tab, e.g. `w1J:t1` |
| `HERDR_SOCKET_PATH` | socket the pane should talk to |
| `HERDR_BIN_PATH` | absolute path to the `herdr` binary |
| `HERDR_CONFIG_PATH` | (set by you) overrides the config file location |

`HERDR_INTEGRATION_ID` / `HERDR_INTEGRATION_VERSION` appear as comments in files written
by `herdr integration install`.

## Remote (machine) forwarding

`herdr --machine <label-or-id> <command>` forwards API commands over SSH to a saved
profile's remote session. Constraints verified against the vendor skill and CLI help:

- selector is an enabled saved profile ID or a unique case-sensitive label - never an
  arbitrary SSH hostname;
- incompatible with `--session` and `--remote`;
- requires both installations to support forwarding, and the remote server to already be
  running and API-compatible - forwarding never installs, starts, or restarts a server and
  never falls back to Local;
- local configuration, session management, installation commands, and interactive
  attachment are not forwarded;
- remote worktree paths must be absolute, `~`, or `~/...`; plugin link paths must be
  absolute;
- ids are per-server: `w1:p1` can exist on two machines, and local inherited ids or
  `--current` do not identify remote panes.
