# Design and evidence

## What this skill is

OmO Pro Review is a native second-opinion workflow. It ships no reviewer of its
own: it scopes a change set, hands a complete brief to a real agent client that
you already trust, harvests the report artifact, machine-checks it, and then
verifies every finding locally before reporting.

Pieces:

- `SKILL.md` - the conductor workflow.
- `references/clients.md` - engines (pane client, headless client, in-session
  subagent), per-client commands, and the traps verified on this machine.
- `references/review-brief.md` - how to compose the brief.
- `references/report-template.md` - the report contract the client must fill.
- `scripts/handoff.mjs` - zero-dependency scope/brief/verify/status engine.

## Why it is built this way

- **Clients, not wrappers.** A real client brings its own tools, session, model
  routing, and credentials. Duplicating that in a wrapper would freeze a
  smaller copy of a client that already exists and ages faster than the client
  itself.
- **Artifacts, not transcripts.** Console markers can be satisfied by the echo
  of the prompt. The report file written by the client is the only trustworthy
  completion signal.
- **Threat model of `verify`.** Sixteen adversarial Pro rounds showed that an
  ad hoc Markdown reader can always be fooled into reading less than a renderer
  shows. `verify` therefore accepts only a narrow grammar and rejects everything
  outside it. It protects against incomplete or malformed reports from a
  cooperating reviewer; it does not (and cannot) stop a reviewer from hiding its
  own findings, which omission would achieve anyway.
- **Machine-checked contract.** The section list, verdict vocabulary, findings
  table, and nonce live in `handoff.mjs`; a report that does not satisfy them is
  rejected instead of being summarised as if it were complete.
- **Explicit scope.** Hazards are excluded by rule with a recorded reason
  (secret-shaped paths, binary content, oversized files, generated and log
  shaped files) so that nobody has to remember which paths must never leave the
  machine.
- **Selection evidence is not attestation.** A client status line shows what
  the client believes it selected. It is not proof of the backend that produced
  a given answer, and this skill never upgrades it in the summary.

## Verified on this machine (2026-09-22, Herdr 0.9.1, node v26.7.0)

- The pane flow was exercised against a real client: split, launch, brief,
  answer, and an artifact written to the exact requested path.
- A pane-launched OmO client is not listed by `herdr agent list` in this
  install, so OmO uses pane commands plus the artifact protocol; clients whose
  Herdr integration reports `current` can use `agent prompt --wait` instead.
- `herdr agent start <name> --kind pi` launched the first `pi` on that pane PATH
  (upstream Pi with its own config), not OmO. Verify the client a `--kind`
  launch produced before trusting it.
- `handoff.mjs` scope, exclusion, split, and verify behaviour is covered by the
  author's local skill-contract suite (not shipped with the skill).

## Boundaries

- No model, provider, or auth configuration is added or modified.
- The Pro engine drives a pinned third-party browser transport (see [pro-engine.md](pro-engine.md))
  because the Pro tier has no API; scope selection, the brief, the report contract,
  verification, and the credential boundary are ours.
- Review-only by default: findings and the smallest next step, nothing else,
  unless the user separately asks for implementation.
