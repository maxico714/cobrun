# Contributing

The most useful contributions are conformance cases, clearer errors and missing core statements — each
with a test and, for arithmetic, a mutation check.

## Setup (under five minutes)

```console
$ git clone https://github.com/maxico714/cobrun
$ cd cobrun
$ python -m venv .venv
$ .venv/Scripts/activate        # Windows; source .venv/bin/activate elsewhere
$ pip install -e ".[dev]"
$ ruff check . && ruff format --check . && mypy && pytest
```

Requires Python 3.10+. No runtime dependencies; the dev extra adds pytest, ruff, mypy, build and twine.

## Guidelines

- **Every behaviour change needs a test that fails without it.** For arithmetic or rounding changes, add a
  mutation check to the pull request notes: break the rule, show the failing test, restore.
- **Rounding is load-bearing.** `ROUNDED` is `ROUND_HALF_UP`; do not change it without a version bump and a
  differential fixture that shows the old and new behaviour.
- **Keep the subset honest.** If you add a statement or clause, update `docs/COBOL_SUBSET.md`, the README
  and the changelog in the same pull request, and reject what is still unsupported with a clear message.
- **No new runtime dependencies.** The stdlib-only test in `tests/security/` parses every import.
- **Never add CCVS85 material.** Do not commit NIST files, archives or derived expectations; conformance
  runs on directories the user supplies.
- **Bounded input.** New syntax must respect the existing caps (lines, tokens, nesting, literal digits,
  fields, step limit) or add a new explicit one.

## Adding a fixture

1. Put the program in `fixtures/programs/<name>.cbl` and its expected output in
   `fixtures/expected/<name>.out`.
2. Register it in `fixtures/manifest.json` (add `accept` lines if the program uses `ACCEPT`).
3. Run `python -m pytest tests/integration/test_fixtures.py`.

## Adding a conformance case

Create `<dir>/<SECTION>-<name>.cbl` and `<SECTION>-<name>.out`; `cobrun conformance --ccvs <dir>` compares
them with the documented normalisation. The section prefix is reported in the summary.

## Commits and pull requests

Conventional Commits, one logical change per pull request, CI green. Describe the failure, the fix and the
command that proves it.
