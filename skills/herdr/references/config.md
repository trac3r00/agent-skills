# Herdr configuration reference

File: `~/.config/herdr/config.toml` (override with `HERDR_CONFIG_PATH`).
Print the annotated default: `herdr --default-config`. Validate: `herdr config check`.
Apply to a running server: `herdr server reload-config`. Clear custom keybindings (with a
backup): `herdr config reset-keys`. Some UI settings only take effect on next launch.

Sibling files in the config directory: `session.json`, `release-notes.json`,
`.plugins.lock`, `herdr-server.log`, `herdr-client.log`, `herdr.sock`,
`herdr-client.sock`. Runtime state lives in `~/.local/state/herdr/`
(`agent-detection/status.toml`, `agent-detection/remote/*.toml`, `client-shell/*.json`).

## Top level

| Key | Default | Meaning |
|-----|---------|---------|
| `onboarding` | unset (shows onboarding) | Show first-run notification setup; set `false` after choosing |

## `[theme]`

`name` - one of `catppuccin`, `terminal`, `tokyo-night`, `dracula`, `nord`, `gruvbox`,
`one-dark`, `solarized`, `kanagawa`, `rose-pine`, `vesper`.
`auto_switch` - follow host light/dark appearance; `dark_name` / `light_name` pick the
themes (e.g. `catppuccin` / `catppuccin-latte`).
`[theme.custom]` overrides color tokens (`sidebar_bg`, `active_row_bg`, `selection_bg`,
`panel_bg`, `accent`, `red`, `green`, ...) accepting hex, named colors, `rgb(r,g,b)`, or
`reset`. `[theme.custom.light]` / `[theme.custom.dark]` layer appearance-specific overrides.

## `[terminal]`

| Key | Default | Meaning |
|-----|---------|---------|
| `default_shell` | `""` | Executable for new interactive panes; empty = `$SHELL`, then `/bin/sh` |
| `shell_mode` | `auto` | `auto` / `login` / `non_login`; `auto` uses login shells on macOS |
| `new_cwd` | `follow` | CWD policy for new panes/tabs/workspaces: `follow`, `home`, `current`, or a fixed path such as `~/Projects` |
| `kitty_graphics` | `true` | Render pane images in Kitty-graphics-compatible outer terminals |

## `[update]`

| Key | Default | Meaning |
|-----|---------|---------|
| `channel` | `stable` (Windows preview builds: `preview`) | Channel used by background checks and `herdr update` |
| `version_check` | `true` | Check herdr.dev for new versions in the background |
| `manifest_check` | `true` | Check herdr.dev for remote agent-detection manifests |

`herdr channel show` / `herdr channel set <stable|preview>` read and write the channel.

## `[keys]`

`prefix` defaults to `ctrl+b` (examples: `"f12"`, `"esc"`, `"-"`). Bindings use explicit
syntax: `prefix+n` requires the prefix, while `ctrl+alt+n` is a direct terminal-mode chord.
Accepted syntax: plain keys, `ctrl/shift/alt/cmd/super` modifiers, special keys
(`enter`, `tab`, `esc`, `left/right/up/down`), and named punctuation (`minus`, `comma`,
`ampersand`, `plus`, `backtick`). Most reliable direct bindings are `ctrl+letter`, function
keys, and explicit modified chords.

Prefix-mode actions (each settable, empty string unsets; several are unset by default):

`help` (`prefix+?`), `settings` (`prefix+s`), `detach` (`prefix+q`), `reload_config`
(`prefix+shift+r`), `open_notification_target` (`prefix+o`), `workspace_picker`
(`prefix+w`), `goto` (`prefix+g`), `new_workspace` (`prefix+shift+n`), `new_worktree`
(`prefix+shift+g`), `open_worktree` (`""`), `remove_worktree` (`""`, opens a
confirmation), `rename_workspace` (`prefix+shift+w`), `close_workspace`
(`prefix+shift+d`), `previous_workspace` (`""`), `next_workspace` (`""`),
`previous_agent` (`""`), `next_agent` (`""`), `focus_agent` (`""`, indexed e.g.
`prefix+alt+1..9`), `remote_image_paste` (`ctrl+v`, only in `herdr --remote`),
`new_tab` (`prefix+c`), `rename_tab` (`prefix+shift+t`), `previous_tab` (`prefix+p`),
`next_tab` (`prefix+n`), `move_tab_previous` (`""`), `move_tab_next` (`""`),
`switch_tab` (`prefix+1..9`), `switch_workspace` (`""`, indexed), `close_tab`
(`prefix+shift+x`), `rename_pane` (`prefix+shift+p`), `edit_scrollback` (`prefix+e`),
`focus_pane_left/down/up/right` (`prefix+h/j/k/l`), `cycle_pane_next` (`prefix+tab`),
`cycle_pane_previous` (`prefix+shift+tab`), `last_pane` (`""`), `split_vertical`
(`prefix+v`), `split_horizontal` (`prefix+minus`), `close_pane` (`prefix+x`), `zoom`
(`prefix+z`, legacy alias `fullscreen`), `resize_mode` (`prefix+r`),
`resize_pane_left/down/up/right` (`""`, direct resize without resize mode),
`toggle_sidebar` (`prefix+b`).

Navigate-mode locals (win while navigate mode is open; must not include prefix, esc,
enter, tab, or 1..9): `navigate_workspace_up/down` (`up`/`down`),
`navigate_pane_left/down/up/right` (`h`/`j`/`k`/`l`; arrows always move in that direction).

Custom commands:

```toml
[[keys.command]]
key = "prefix+alt+g"
type = "popup"          # shell (detached) | pane (temporary pane) | popup (session modal)
command = "lazygit"
width = "80%"           # cells or NN%
height = "80%"
```

Legacy `[keys.indexed]` (`tabs`, `workspaces`, `agents`) still parses but prefer
`switch_tab`, `switch_workspace`, and `focus_agent`.

## `[server]`

`headless_cols` (default 120), `headless_rows` (default 40) - virtual terminal size when no
client is attached; attached clients use their own size.

## `[worktrees]`

`directory` (default `~/.herdr/worktrees`) - where Herdr creates worktree checkouts.

## `[ui]`

Sidebar: `sidebar_width` (26, auto-scaled default), `sidebar_min_width` (18),
`sidebar_max_width` (36), `sidebar_start_collapsed` (false; next launch),
`sidebar_collapsed_mode` (`compact` keeps the narrow status rail, `hidden` uses zero
width).
Layout: `mobile_width_threshold` (64) - at or below this width Herdr uses the mobile
single-column layout; `pane_borders` (`auto`; `always` also frames a lone pane while
`pane_outer_borders` is on; legacy booleans parse as `true`=`auto`, `false`=`off`),
`pane_outer_borders` (true - set false for tmux-style internal splitters only),
`pane_scrollbars` (true), `pane_gaps` (true),
`show_agent_labels_on_pane_borders` (false), `hide_tab_bar_when_single_tab` (false),
`tab_bar_position` (`top` or `bottom`), `tab_bar_right` (ordered status entries of type
`zoom`, `hostname`, `datetime`, `text`, `command`; resolved on the server),
`tab_bar_right_separator` (`" "`).
Input/appearance: `mouse_capture` (true - false lets the terminal handle normal clicks such
as Cmd-click URLs; pane apps can still request mouse), `copy_on_select` (true),
`host_cursor` (`auto`; `native`, `drawn`), `right_click_passthrough_modifier` (`""`; Shift
intentionally unsupported), `redraw_on_focus_gained` (true), `mouse_scroll_lines` (3),
`confirm_close` (true), `prompt_new_tab_name` (true), `prompt_new_workspace_name` (false),
`window_title` (`"{hostname}: {workspace}"`; tokens `{hostname}`, `{workspace}`, `{tab}`,
`{pane}`, `{terminal_title}`, `{{`/`}}` for literals; `""` leaves the outer title alone),
`agent_panel_sort` (`spaces`|`priority`; `workspaces` is an alias for `spaces`),
`status_indicators` (`dots` or `symbols`), `accent` (hex, named, `rgb()`).

Agent rows - built-ins `state_icon`, `state_text`, `machine`, `workspace`, `tab`, `pane`,
`agent`, `terminal_title`, `terminal_title_stripped`; custom values come from pane metadata
`$name` tokens, and a token may carry `{ token = "...", fg = "#89b4fa", bold = true }`:

```toml
[ui.sidebar.agents]
row_gap = 0
rows = [["state_icon", "machine", "workspace", "tab"], ["agent"]]
[ui.sidebar.agents.rows_by_agent]
claude = [["state_icon", "machine", "workspace", "tab"], ["terminal_title_stripped"], ["agent"]]
```

Space rows - built-ins `state_icon`, `state_text`, `workspace`, `branch`, `git_status` plus
custom `$name` tokens; inline token styles accept `#RGB`/`#RRGGBB`, `bold`, `dim`:

```toml
[ui.sidebar.spaces]
row_gap = 0
rows = [["state_icon", "workspace"], ["branch", "git_status"]]
```

Toasts - `[ui.toast] delivery` = `off` | `herdr` (in-app) | `terminal` (ask the outer
terminal) | `system` (OS notification service), `delay_seconds` (1);
`[ui.toast.herdr] position = "bottom-right"`;
`[ui.toast.clipboard] enabled = true`, `position = "bottom-center"`.

Sound - `[ui.sound] enabled` (true), `path` (one mp3 for all notifications), `done_path`,
`request_path` (relative paths resolve from the config directory);
`[ui.sound.agents]` per-agent `default|on|off` (droid is muted by default).

## `[session]`

`resume_agents_on_restore` (true) - resume supported AI-agent panes into their native
conversation sessions after a server restart; requires official integrations that report
session refs.

## `[remote]`

`manage_ssh_config` (true) - when true Herdr runs `herdr --remote` ssh through a generated
config that includes `~/.ssh/config` first and adds `ServerAliveInterval`/`ServerAliveCountMax`
fallbacks (so your own keepalive values still win), plus a private per-attach OpenSSH
control socket to reuse the first authenticated connection. Setting false runs plain ssh
against your config unchanged - it does not force keepalive or multiplexing off, it only
stops Herdr from adding its own.

## `[experimental]`

| Key | Default | Meaning |
|-----|---------|---------|
| `allow_nested` | false | Allow launching herdr from inside a herdr-managed pane |
| `pane_history` | false | Save recent pane screen history across full server restarts |
| `switch_ascii_input_source_in_prefix` | false | While prefix mode is active, temporarily switch the host input source to an ASCII-capable mode (macOS layout / Windows Korean IME), then restore. macOS + Windows, best-effort |
| `reveal_hidden_cursor_for_cjk_ime` | false | Expose the focused pane's cursor so macOS input methods track the candidate window when TUIs paint their own cursor (Claude Code, pi, codex). Trade-off: an extra visible cursor for apps that hide it without painting a replacement |
| `cjk_ime_agents` | `[]` | Allow-list of agent names for the reveal (empty = any focused pane; an all-invalid list disables it) |
| `cjk_ime_cursor_shape` | `steady_block` | `block`, `steady_block`, `underline`, `steady_underline`, `bar`, `steady_bar` |

Accepted `cjk_ime_agents` values: `pi`, `claude`, `codex`, `gemini`, `cursor`, `devin`,
`cline`, `opencode`, `copilot`, `kimi`, `kiro`, `droid`, `amp`, `grok`, `hermes`, `kilo`,
`qodercli`, `qoder`, `qwen`, `qwen-code`, `letta`, `letta-code`, `maki`.

## `[advanced]`

`scrollback_limit_bytes` (10000000) - maximum scrollback retained per pane terminal,
matching Ghostty's default scrollback-limit behavior.

## Config workflow

```bash
herdr --default-config > /tmp/herdr-default.toml   # annotated template
cp ~/.config/herdr/config.toml ~/.config/herdr/config.toml.bak
# ... edit ...
herdr config check                                  # "config: ok" or diagnostics
herdr server reload-config                          # apply without restarting panes
```

`config check` exits 0 on a valid file; invalid TOML or unknown keys surface as
diagnostics. Changes to keybindings, sidebar collapse state, and similar UI settings may
only apply on the next launch - the default config comments mark those cases.
