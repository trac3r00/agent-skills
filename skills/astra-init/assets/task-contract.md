# Task contract

Use only the fields that materially affect the task. Unknown is a valid value.
Derive this contract from the user's request and existing authority; do not use
it to add approvals, permissions, work, or success criteria the user did not set.

- Outcome and observable stop condition:
- In-scope files, components, and effects:
- Non-goals and protected user work:
- Already-authorized actions:
- Actions requiring approval; revoked or superseded approvals:
- Active model evidence; host and dependency versions:
- Acceptance checks and who or what independently verifies them:
- Budget, time limits, and permitted external calls:
- Missing evidence, conflicts, or blockers:

## Completion evidence

For each acceptance criterion, record its status and attributable evidence:
the actual command or tool action, working directory, exit/result status,
observed behavior, source state including relevant uncommitted changes,
environment/dependency identity, and run identity.

Use statuses such as verified, failed, unknown, conflict, unverified,
environment-blocked, and approval-blocked. Treat skipped checks as unverified.
Invalidate the affected evidence after changes to its inputs.

A self-authored completion record is a report, not a protected host receipt.
Do not mark success solely because this form is complete.
