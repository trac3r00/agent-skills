# The Pro engine (ChatGPT Pro)

This is the default engine: it reaches the **web-only ChatGPT Pro tier** that has
no API, using a pinned browser transport under our own guard and report
contract. It is the only engine that can honestly claim a Pro review.

## Pieces

| piece | role |
| --- | --- |
| `scripts/pro-engine.mjs` | builds (`plan`) or runs (`run`) one guarded invocation for a brief and a report path |
| `scripts/oracle-guard.mjs` | refuses unsafe authentication sources, validates the pinned transport, and fixes the Pro model + effort |
| pinned transport | `@steipete/oracle@0.21.1`, resolved from `PRO_REVIEW_ORACLE_CLI`, then the npx cache, then the global npm root; the skill never installs it |

Install it once with `npx -y @steipete/oracle@0.21.1 --version` (that populates the
npx cache), or point `PRO_REVIEW_ORACLE_CLI` at an absolute
`.../@steipete/oracle/dist/bin/oracle-cli.js`. Node.js 24 or newer is required.

The transport is pinned and version-checked: if the installed package is not
`0.21.1` at the expected path, the guard refuses before anything runs. Our own
code owns scope selection, the brief, the report contract, verification, and the
cookie/credential boundary - the package only drives the browser.

## What the guard refuses (exit 2, nothing sent)

- Cookie payloads or export files from the environment (`ORACLE_BROWSER_COOKIES_JSON`,
  `..._FILE`, including empty values), from `.env`, from a config file, or passed
  as CLI options.
- Automatic cookie exports found in the effective transport home.
- A transport home or browser profile that differs from the pinned paths.
- Cookie synchronisation, copied profiles, attached or remote browsers.
- Saved-session recovery whose metadata does not prove manual login with cookie
  sync disabled, or whose saved request carries cookie configuration.
- Any option outside the documented allowlist (including `restart` and follow-ups).

- A project `.env` that sets runtime or browser controls (`NODE_OPTIONS`,
  `LD_*`/`DYLD_*`, `PATH`, `CHROME_PATH`, `ORACLE_CLIENT_FACTORY`, remote-debug
  ports, and similar). Other project dotenv keys outside the transport's `ORACLE_`
  namespace are dropped, never promoted into the transport environment.

Refusal is a setup blocker: do not bypass the guard, delete cookies, or edit the
user authentication configuration to get past it.

## Upload integrity

`plan` records a SHA-256 for every scoped file. Before sending, `run` re-checks
each manifest entry (plain repository-relative path, canonical containment, the
shared path policy, regular file, unchanged hash) and uploads a private snapshot
of exactly those bytes as one text bundle (`===== FILE: <path> =====` per file, so
no repository filename reaches the transport's glob-expanding file interface),
removed after the run (also on a failed snapshot). The transport writes the reply
to a private file; `run` then publishes it to the report path with exclusive
create, so a pre-existing entry or link there is refused, never followed.
Project dotenv promotes only a short allowlist of `ORACLE_` tuning settings, and
prompt-mutating config (`promptSuffix`, `promptPrefix`, `systemPrompt`) is refused.
Every submission is pinned to a new chat (`--chatgpt-url https://chatgpt.com/`); a
configured `chatgptUrl`/`url` destination is refused, and the transport file-size
limit is set from the real bundle size. The
brief is bound the same way: it must be the regular file beside the manifest with
the hash the plan recorded, and `plan` output shows only its length and hash. A
file or brief that changed or became a link since planning is refused: re-plan
to approve the new content.

Transport discovery runs npm from your home directory and ignores candidates
inside the working project, so a reviewed repository's `.npmrc` cannot choose
the executable transport.

## Pinned selection

Every run is pinned to `--engine browser --model gpt-6-pro
--browser-model-strategy select --browser-thinking-time pro`, with manual login,
no cookie sync, archiving off, and one bundled text attachment. The guard builds
those flags itself, so a caller cannot weaken them.

## First login

The dedicated profile is `~/.oracle/browser-profile`. Add `--keep-browser`
(the engine flag; the guard forwards it as `--browser-keep-browser`) on the first live run so the window stays open for sign-in, then drop the flag.
A `needs_login` failure happens before submission, so retrying after sign-in is
correct; a failure after possible submission means recovering the saved session,
not resubmitting.

## Commands

```sh
# Build the exact invocation from a handoff manifest (no browser, no prompt):
node "$PRO_REVIEW_DIR"/scripts/pro-engine.mjs plan \
  --manifest "<manifest dir>/manifest.json" [--pass 1]

# Send it to ChatGPT Pro and save the reply as the report:
node "$PRO_REVIEW_DIR"/scripts/pro-engine.mjs run \
  --manifest "<manifest dir>/manifest.json" [--pass 1] [--keep-browser]

# Recovery, through the same guard (oracleCli is the path `plan` prints):
node "$PRO_REVIEW_DIR"/scripts/oracle-guard.mjs \
  --oracle-cli "<oracleCli from plan>" \
  --oracle-home "$HOME/.oracle" --profile-dir "$HOME/.oracle/browser-profile" \
  status --hours 72
```

The manifest supplies the brief, the report path, and every scoped file, which the
engine uploads as an attachment. A brief-only invocation is refused unless
`--prompt-only` says the review genuinely needs no files, and a manifest whose
engine mode is not `pro` is refused too. `--keep-browser` is forwarded for
first-time sign-in.

Run `run` through the background command monitor with a deadline that covers the
20-minute response allowance, and wait for the report file rather than for
console text. A Pro answer usually takes 10-15 minutes.

## Evidence

Verified on the author's machine (the suites are not shipped with the skill):

- Guard boundary suite: 28/28, including a clean preview that reaches the real
  pinned transport and preserves the Pro selection.
- Engine wiring suite: 5/5.
- The last live Pro review run (session `pro-review-lease-race-closure`) returned
  an APPROVE verdict on the runtime repair under review at the time.

## Limits

Selection evidence (the picker showed `Latest` + `Pro`) is not independent proof
of the backend that served an answer. The transport is a third-party package: an
upgrade can break it, which is why the version is pinned and checked.
