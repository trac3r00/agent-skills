# OmO Pro Review

<!-- Copy this file to the handoff report path and fill every section. -->
<!-- handoff.mjs verify machine-checks the section headings, the verdict, the findings table, and the final marker line: keep all of them intact. -->

## Verdict

APPROVE | REQUEST_CHANGES | INCONCLUSIVE

One sentence on what the verdict means for the change set.

## Scope

- reviewed: `path/a.ts`, `path/b.test.ts`
- not reviewed: `path/vendor/**` (out of scope)
- engine: client + model as reported by the client

What was inspected directly, and what was deliberately excluded.

## Findings

| severity | location | finding | impact | fix |
| --- | --- | --- | --- | --- |
| critical | `path/a.ts:42` | failing input/state and the causal chain | who is hurt and how | smallest correct change |
| high | `path/b.test.ts:17` | ... | ... | ... |

Order by severity, worst first. Every row has exactly five filled cells, a real
`path:line`, and a severity from `critical`, `high`, `medium`, `low`, `info`.
Escape a literal pipe inside a cell as `\|`. The findings table is one contiguous
block and the only table in the report. Never put example finding rows or section headings inside code blocks,
quotes, lists, comments, or indentation: the verifier is fail-closed and rejects
a report containing them rather than guessing which ones are real.
Write exactly `No confirmed findings.` when the review found none, then use
the remaining sections for risks and open questions.

## Checks run

- `command` -> observed result (or: not run, and why)
- Commands you did not run: say so. Never imply execution.

## Limits

- Context that was unavailable, and how it could change the verdict.
- Residual uncertainty a reader must weigh.

<!-- Each pass has its own nonce; a report carrying another pass's marker is rejected. The marker is the last line; only link-reference lines such as web citations may follow it. -->

PRO_REVIEW_DONE <this pass's nonce, from its brief>
