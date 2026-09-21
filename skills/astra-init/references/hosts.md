# Native host integration

## OmO / Senpi

The installed Senpi skill documentation identifies `~/.agents/skills/` as a
native user-level location. Invoke `/skill:astra-init` or a leading
`$astra-init`. The skill's `disable-model-invocation: true` hides it from the
implicit skill list while retaining explicit invocation.

Use the host's current session model, not `settings.json` defaults: a session
can override defaults or fall back to another model. Host identity must be
unambiguous before initializing or loading the project profile.
If a newly installed skill is not visible, start a fresh session.

Concrete identity sources in OmO: the running session's `PI_MODEL`,
`PI_PROVIDER`, and `PI_REASONING_LEVEL` environment variables, the `get_state`
RPC command, or the interactive status line. `settings.json` defaults are not
session evidence.

## Codex

Codex documents native discovery in `~/.agents/skills/`. Invoke `$astra-init`.
`agents/openai.yaml` sets `allow_implicit_invocation: false`; it controls
selection, not model access or tool permissions.

Do not assume every nested `AGENTS.md` is active. Use the installed host's
discovery rules and verify the effective instruction stack. This skill instead
writes `.agents/astra/working-agreement.md`, which is loaded explicitly.

## Other hosts and hard isolation

Check native skill discovery, explicit-only controls, and active-model metadata
before adapting this package. Do not infer OpenCode behavior from Codex or Senpi.
Prefer one portable profile plus documented native host controls, not duplicate
`AGENTS.md` files or a second loader.

Neither metadata nor prose prevents a user or another model from manually
reading a file. A strict Astra-only loading guarantee requires a host-owned
model-selection gate that is also enforced after fallback and resume. This
package does not install one or remove already-loaded text from a context.
Do not claim hard isolation from this instruction-only package.

## Transport, reasoning, and compaction

This initializer does not configure API transport. When such changes are
separately requested, verify current provider documentation and the effective
request: model identifier, returned metadata, supported reasoning levels,
function-calling API, permissions, and host version. Do not invent snapshots.

Before using reasoning `configuration_update` items, verify compatibility with
the host's actual automatic compaction, truncation, and `/responses/compact`
paths. Record effective effort separately from request-level metadata.
Preserve native compaction unless a separately authorized, tested change is needed.

For caching experiments, inspect real cache usage, boundaries, and write/read
costs. A new session or cache key alone does not establish a cold-cache run.
Installation requires no model calls or provider credentials. Invocation uses
the host's normal authenticated model session; this skill adds no separate API
client, credential setup, benchmark calls, or runtime modifications.
