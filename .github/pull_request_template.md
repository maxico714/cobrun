## What changed

<!-- One paragraph: the failure or gap and the fix. -->

## How it was verified

- [ ] `ruff check . && ruff format --check . && mypy && pytest` pass locally
- [ ] New or changed behaviour has a test that failed before the change
- [ ] For arithmetic/rounding changes: mutation check described below (break it, see the test fail, restore)
- [ ] `docs/COBOL_SUBSET.md` updated if the subset, semantics or limits changed

Commands and results:

```console
$ python -m pytest -q
```

## Checklist

- [ ] No new runtime dependencies (stdlib-only test still passes)
- [ ] No CCVS85 material committed
- [ ] New syntax respects the input/token/depth/step caps
- [ ] No TODO/FIXME left in `src/`
