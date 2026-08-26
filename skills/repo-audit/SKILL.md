---
name: repo-audit
description: Structural health check for a git repository — LICENSE, README, tests, CI config, .gitignore, large tracked files, and stale merged branches (idle beyond a configurable window). Offline, stdlib + git CLI, deterministic. Use when inheriting a repo, before open-sourcing, or as a periodic hygiene gate across many repos.
when_to_use: "Is this repo maintained?", onboarding onto an unfamiliar codebase, or a fleet-wide hygiene check. NOT a code-quality tool (it checks structure, not code) and not a vulnerability scanner.
version: 1.0.0
license: MIT
metadata:
  agentskills:
    tags: [git, repository, hygiene, ci-gate, maintenance]
---

# Repo Audit

"Is this thing maintained?" in one deterministic pass.

## Commands

```bash
python3 scripts/repo_audit.py .                 # this repo
python3 scripts/repo_audit.py ~/src --json      # any repo
python3 scripts/repo_audit.py . --stale-days 60
python3 scripts/repo_audit.py . --fail-on license,tests
for d in ~/src/*/; do python3 scripts/repo_audit.py "$d" --json; done
```

## Checks

| Check | Fail when |
|---|---|
| `license` | no LICENSE file |
| `readme` | no README |
| `tests` | no test files detected |
| `ci` | no CI config (GitHub Actions, GitLab CI, CircleCI) |
| `gitignore` | missing (untracked junk risk) |
| `large_files` | tracked files over 5MB (warn) |
| `stale_branches` | merged branches idle > `--stale-days` (warn) |

`--fail-on a,b` requires specific checks — the rest become advisory.

## Pairs with

`git-master` (act on the stale branches this finds),
`skill-audit` (the same structural-hygiene idea, for agent skills),
`diff-review` (the per-change gate; this is the per-repo gate).
