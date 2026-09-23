---
name: pro-review
description: "Explicit second-opinion code review: scope the change set, hand a sized, hazard-filtered brief to ChatGPT Pro (default, through a pinned guarded browser transport) or to a real agent client (OmO, Claude, Codex) in its own Herdr pane, then machine-check the returned report and verify every finding locally. Use only when invoked as /pro-review, $pro-review, or /skill:pro-review."
version: 1.0.0
license: MIT
metadata:
  agentskills:
    tags: [review, code-review, chatgpt-pro, second-opinion, herdr, agents, verification]
disable-model-invocation: true
---

# OmO Pro Review

Use this workflow when explicitly invoked as `/pro-review`, `$pro-review`, or
`/skill:pro-review`. It obtains an independent review from a real agent client
that inspects the project itself, machine-checks the returned report, and
verifies every claim locally before reporting. It adds no model, provider, or
auth configuration, and it is not a substitute for tests.

The `/pro-review` prompt alias tells the host agent to read this file; native
`$pro-review` and `/skill:pro-review` invocations expand the skill directly.

## 1. Scope the question

State the review question in one sentence. Use the user's target and its absolute
paths or globs. Without a target, review the current working changes plus their
callers and tests. If neither exists, ask what should be reviewed. Never hand a
reviewer the home directory, an entire workspace, or unrelated personal data as
a guessed target.

Inspect the implementation yourself first so you can brief the reviewer
accurately and judge its answers later. Scope to the complete relevant set:
full function bodies, callers, types, tests, and configuration. A diff alone is
rarely enough. For a contained feature name its whole module; for larger work
trace dependencies and boundaries instead of widening to the whole repository.

## 2. Plan the handoff

`PRO_REVIEW_DIR` below is this skill's own directory (for example
`~/.agents/skills/pro-review`, or wherever your client installed it). The scripts
need Node.js 24 or newer and nothing else.

Let the handoff engine do the mechanical scoping, sizing, hazard exclusion, and
pass splitting, then read its summary before sending anything:

```sh
node "$PRO_REVIEW_DIR"/scripts/handoff.mjs plan \
  --repo "$PWD" --changes \
  --question "<the one-sentence question>" \
  --out "$PWD/.pro-review/<slug>"     # the default engine is ChatGPT Pro
```

It writes `manifest.json` plus one `brief-pass<N>.md` per pass and prints a
scoped summary: files with roles and token estimates, every exclusion with its
reason, the git digest (including deleted paths), the report path, and one nonce
marker per pass. The path policy is a bounded filter on path shape (secrets,
tokens, cookies, sessions, logs, generated and excluded directories, earlier
handoffs); it does not detect credentials pasted inside ordinary source files.
The output directory must be new or empty; `--force` replaces only an earlier
handoff's own manifest and briefs, and refuses once that handoff has a report. Check that the
scope matches your intent, that nothing essential was excluded, and that the
passes fit the reviewer's context. Use `--budget <tokens>` to force a split of a
scope that is too large for one pass.

For explicit paths instead of the change set, replace `--changes` with repeated
`--target <path|glob>`; the engine still applies the hazard rules.

## 3. Send it to ChatGPT Pro

Default engine: the **Pro engine** reaches the web-only ChatGPT Pro tier through the
pinned, guarded transport. Read [The Pro engine](references/pro-engine.md) before the
first live run of a session.

```sh
node "$PRO_REVIEW_DIR"/scripts/pro-engine.mjs run \
  --manifest "<manifest dir>/manifest.json"        # add --pass N for later passes
```

Run that through the background command monitor with a deadline covering the
20-minute response allowance; a Pro answer usually takes 10-15 minutes.

### Other engines (opt-in)

Planning with `--client <name>` selects a client engine instead of Pro. When the user asks for a different reviewer, or Pro is unavailable, pick one of these instead:

- **Pane client** (default inside Herdr): the reviewer runs in its own visible
  pane with its full tool surface - best for long reviews, and you can watch or
  steer it.
- **Headless client**: the same client in one-shot print mode - best outside
  Herdr or for scripted runs.
- **In-session subagent**: OmO's own reviewer agent through the task tool - use it
  when Herdr is unavailable.

Send `brief-pass<N>.md` verbatim; it already carries the question, scope roles,
digest, focus hints, exclusions, constraints, the report path, and the nonce.
Compose a custom brief only when the template genuinely does not fit, and then
follow [Review brief](references/review-brief.md) and keep the output contract.

An explicit review invocation authorizes sending the scoped brief to the chosen
engine. Installing the skill, or merely reading this file, does not request a
live review. Stay inside the user's existing credentials: never add API keys, copy
another client's auth, or switch a client's account. Keep the pane visible; never
close a pane you did not create, and do not steal focus unless asked.

## 4. Harvest the artifact, never the echo

Wait for the report file the brief named - watch that path, or wait on the
client's own settled state when Herdr tracks it. A marker echoed back from your
own prompt is not an answer, and a fixed sleep is not a wait. Then run:

```sh
node "$PRO_REVIEW_DIR"/scripts/handoff.mjs verify \
  --report "<report path>" --manifest "<manifest path>" --format terminal
```

Exit 0 renders the summary (verdict, severity counts, findings with locations,
checks, limits); exit 2 names exactly what the report is missing.

`verify` checks that a cooperating reviewer's report is complete and well-formed
under a deliberately strict grammar (exact headings, one findings table, no raw
HTML, fences only at column 0) and fails closed on anything outside it. It is
not a defense against a reviewer that hides its own findings - such a reviewer
could simply omit them - so always read the report artifact itself (step 5). Reject the
report and ask for a corrected one instead of summarising an incomplete answer.
If a client stalls, sits on an approval dialog, or loses its transport, recover
the same pane or session rather than submitting a duplicate. Ask the user only
for what a human must do: a login, an account choice, an approval prompt, or a
decision to abandon the run.

## 5. Verify and report

Read the report artifact. Reproduce each proposed finding in the current code
and run focused checks where needed. Separate confirmed defects, plausible
risks, and unsupported claims; agreement between reviewers is not proof.

Return findings first, ordered by severity, with `path:line`, the failing
condition, impact, and a minimal correction. State when there are no confirmed
findings. Include unresolved questions, the reviewed scope, the checks actually
run, the reviewer and engine used, the pane or output path, and the model
identity the client itself reported. The filled report template lives at
[Report template](references/report-template.md); `verify --format json` emits
the machine-readable form for scripted consumers.

Review-only requests end with the assessment; do not implement, commit, publish,
or contact people unless the user separately asks for that work. For an existing
authorized fix task, use verified findings within that task's scope.

See [Design and evidence](references/sources.md) for what was verified on this
machine and the difference between a client's self-reported model and independent
attestation.
