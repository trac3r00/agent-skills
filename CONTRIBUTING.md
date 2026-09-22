# Contributing

## Local checks

Run the complete repository checks before opening a pull request:

```sh
python3 skills/skill-picker/scripts/generate_catalogue.py --check
pytest tests/
```

Skills need complete frontmatter, focused instructions, and deterministic
tests for executable behavior. Do not add credentials, personal data, or
generated catalogue edits by hand; regenerate `catalogue.json` with the
checked-in generator.

## Pull requests

Keep changes scoped, explain user-visible behavior, and document validation.
New skills must be self-contained and must not depend on an unpinned external
repository except through an explicit, documented submodule or install step.
