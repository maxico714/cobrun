# BUILD CHECKLIST — cobrun

Status: v0.1.0 built and verified 2026-10-26 (Windows 10 26200, Python 3.12.10).
Gate 8 (PyPI publish) stays open: G3 is not approved.

## Gate 0 — Rounding and oracle spike

- [x] Rounding edge cases defined before coding and frozen in `docs/COBOL_SUBSET.md` and the fixtures:
      `.5` away from zero (`2.25 → 2.3`, `2.35 → 2.4`), negative halves (`-2.25 → -2.3`), truncation
      without `ROUNDED` (`2.24 → 2.2`), high-order truncation (`1234 → 234` in `9(3)`), `ON SIZE ERROR`,
      negative into unsigned, 18-digit precision, signed division, no negative zero.
- [x] CCVS85 checked live: the historical NIST URL 301-redirects to `https://www.nist.gov/itl` and serves
      HTML, not a ZIP. `fetch-ccvs` therefore fails closed; conformance runs on user-supplied directories.
      No CCVS85 files exist in the repo (test-enforced). Verdict logged in `docs/EVIDENCE.md`.

## Gate 1 — L0 static

- [x] `ruff check .` — clean (E, F, I, B, UP, S, C4, SIM, RUF; S310 scoped to the fixed-URL fetcher).
- [x] `ruff format --check .` — 31 files formatted.
- [x] `mypy` — strict, 10 source modules, no issues.
- [x] `pytest --collect-only` — 145 tests collected.

## Gate 2 — L1 units

- [x] Lexer: 19 tests (free/fixed format, comments, indicator column, continuation rejection, quotes,
      PICTURE tokenisation, caps, line numbers).
- [x] PICTURE/storage: 12 tests (numeric/alphanumeric forms, rejects, padding, sign, scale, groups,
      duplicate names, 88 collection).
- [x] Parser: 23 tests (divisions, hierarchy, arithmetic forms, COMPUTE ROUNDED placement, IF/ELSE,
      PERFORM variants, THRU, DISPLAY/ACCEPT/STRING/UNSTRING/INSPECT, rejection of CALL/EVALUATE-era
      clauses, caps).
- [x] Interpreter: 24 tests (fixtures, step limit, division by zero, unknown names, size errors, signed
      values, group moves, 88 ranges, ACCEPT exhaustion, counters, THRU, INSPECT, decimal precision).
- [x] Mutation sanity (each killed, then restored):
      `ROUND_HALF_UP` → `ROUND_HALF_EVEN` ⇒ rounding fixture and test fail;
      overflow comparison inverted ⇒ 3 tests fail;
      `SUBTRACT` becomes `ADD` ⇒ arithmetic fixture test fails.

## Gate 3 — L2 integration (fixtures)

- [x] hello, arithmetic, rounding, perform, conditions, string-ops run to their expected output
      (`fixtures/manifest.json`, `tests/integration/test_fixtures.py`).
- [x] Differential mode: `cobrun diff hello.cbl --port hello_port.py` → `match`; a wrong port reports
      `line 1: original 'HELLO WORLD' vs port 'hello world'` and exits 1.
- [x] Step limit: `cobrun run loop.cbl --step-limit 25` → `E_STEPLIMIT`, exit 1, no hang.
- [x] CLI: 20 tests covering run/parse/dry-run/doctor/diff/conformance/fetch and every exit code.

## Gate 4 — Conformance (L3)

- [x] Conformance runner tested with temporary `.cbl`/`.out` directories: pass, fail, unsupported, and
      missing-directory cases; per-section summary.
- [x] `fetch-ccvs` tested with monkeypatched responses: valid ZIP accepted; HTML payload rejected and
      deleted; corrupt ZIP rejected; network error reported.
- [x] Never-bundle audit: `tests/security/test_provenance.py` asserts no archives, no COBOL outside
      `fixtures/programs/`, no NIST/CCVS file names.
- [x] No NIST pass rate is claimed anywhere in the docs.

## Gate 5 — L5 adversarial

- [x] `PERFORM … TIMES` with a huge count and `VARYING … BY 0` terminate via the step limit.
- [x] 500-digit numeric literal rejected; 200-deep IF nesting rejected; 20k-line source rejected;
      oversized CLI source rejected; invalid UTF-8 rejected by the reader.
- [x] Overflow with and without `ON SIZE ERROR`; negative into unsigned; division by zero in DIVIDE and
      COMPUTE; unknown paragraph/data name/condition name; `GO TO` out of a PERFORM; empty ACCEPT.

## Gate 6 — Honesty and provenance

- [x] THIRD_PARTY_NOTICES states CCVS85 is fetched at runtime, never bundled, and records the redirect
      status; README and CONFORMANCE repeat it.
- [x] ROUNDED = ROUND_HALF_UP documented, fixture-tested and mutation-checked.
- [x] Pitch is the differential/assertion angle, not "another COBOL tool"; limits (numeric DISPLAY, no
      CALL/file I/O) are in the README.
- [x] No TODO/FIXME in `src/`.
- [x] Secrets scan: `detect-secrets 1.5.0` over all project files → 0 findings.

## Gate 7 — L4 clean environment

- [x] Fresh copy (no caches, dist or egg-info) → `python -m venv` → `pip install .` → `pytest` →
      **145 passed**.
- [x] README quickstart in that venv: `cobrun run`, `cobrun diff`, `cobrun doctor`.

## Gate 8 — Naming and packaging (G3-gated; not executed)

- [x] PyPI name `cobrun` returns **404** (available). GitHub has unrelated same-name projects; installs
      go through PyPI.
- [x] `python -m build` → wheel and sdist; `twine check` PASSED.
- [ ] Publish to PyPI — **blocked on the G3 approval**.

## Definition of done (v0.1)

Gates 0–7 green with the evidence above; Gate 8 prepared but not executed.
