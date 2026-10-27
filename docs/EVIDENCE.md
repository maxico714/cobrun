# EVIDENCE — cobrun

Research judgement (2026-10-12, round-4 verifier + skeptic, ADR-004, ledger row 49), followed by
build-time verification on **2026-10-26**. Claims are dated so older research is not presented as fresh
evidence.

## Gap class: A (nothing mature found)

- No mature open-source pure-Python COBOL-85 interpreter was found in the round-4 search.
- **PythonBol-Translator** is a translator, not an interpreter: it produces code you cannot check against
  the original. The assertion-grade differential angle is the differentiator.
- **GnuCOBOL** is a C compiler for production use; a different niche.
- **NIST CCVS85** is the reference conformance suite; it is fetched at runtime only.

## Build-time checks (2026-10-26)

| Check | Result |
|---|---|
| Name `cobrun` on PyPI | **404** — available (GitHub has unrelated projects with the same name; PyPI is what matters for install) |
| Historical CCVS85 URL (`itl.nist.gov/.../ccvs85.zip`) | **301 → https://www.nist.gov/itl**, returns HTML, not a ZIP |
| `cobrun fetch-ccvs` against that response | fails closed with `did not return a ZIP archive`, no partial file left behind |
| Destination of the redirect | a generic NIST landing page; the archive was not located in this pass |

Consequence: the conformance runner is implemented and tested against `.cbl`/`.out` directories, but no
NIST pass rate is claimed. `docs/CONFORMANCE.md` and the README say this explicitly. Finding the current
canonical archive is tracked as v1.0 work.

## Rounding spike (Gate 0)

Ten edge cases were defined before implementation and pinned in tests and fixtures:

| Input | Target | Result | Rule |
|---|---|---|---|
| 2.25 | `9(2)V9(1)`, ROUNDED | 2.3 | half away from zero |
| 2.35 | `9(2)V9(1)`, ROUNDED | 2.4 | half away from zero |
| 2.24 | `9(2)V9(1)`, no ROUNDED | 2.2 | truncate toward zero |
| −2.25 | `S9(2)V9(1)`, ROUNDED | −2.3 | half away from zero, sign preserved |
| 1 234 | `9(3)`, no handler | 234 | high-order truncation (COBOL size-error default) |
| 999 + 999 | `9(3)` with `ON SIZE ERROR` | unchanged, handler runs | size error |
| 0 − 1 | `9(3)` (unsigned) | unchanged, handler runs | negative into unsigned |
| 1 / 3 | `9(1)V9(18)` | 0.333333333333333333 | exact decimal, truncation at scale |
| 10 / −4 | `S9(3)V9(2)` | −2.5 | signed division |
| 0 | `S9(2)V9(1)` | 0 | no negative zero |

The implementation uses `ROUND_HALF_UP` on every rounding path and `ROUND_DOWN` truncation otherwise; a
mutation that swaps in `ROUND_HALF_EVEN` fails the rounding fixture, as recorded below.

## Verification evidence (2026-10-26)

| Check | Command | Result |
|---|---|---|
| Static | `ruff check .`, `ruff format --check .`, `mypy` | clean; strict mypy over 10 modules |
| Tests | `pytest` | **145 passed** |
| Fixtures | six programs vs expected output | all match (hello, arithmetic, rounding, perform, conditions, string-ops) |
| Differential | `cobrun diff` on hello and arithmetic | `match` (exit 0); a deliberately wrong port reports `line 1` (exit 1) |
| Mutation 1 | `ROUND_HALF_UP` → `ROUND_HALF_EVEN` | rounding fixture + interpreter test fail |
| Mutation 2 | overflow comparison inverted | arithmetic, size-error tests fail (3) |
| Mutation 3 | `SUBTRACT` becomes `ADD` | arithmetic fixture test fails |
| Step limit | `cobrun run loop.cbl --step-limit 25` | `E_STEPLIMIT`, exit 1, no hang |
| Packaging | `python -m build`, `twine check` | wheel `py3-none-any`, sdist, metadata clean |
| L4 | fresh copy → venv → `pip install .` → `pytest` | green (see `BUILD_CHECKLIST.md`) |
| Secrets | `detect-secrets` over the tree | see checklist record |

## Failure modes encountered while building

| Symptom | Cause | Fix |
|---|---|---|
| `COMPUTE X ROUNDED = …` rejected | ROUNDED was only accepted after the expression | accept it before or after `=` |
| `ADD 999 999 GIVING X` rejected | operand loop stopped at the first NUMBER | loop until a connector keyword, not until a non-IDENTIFIER |
| `MOVE -2.25 TO X` rejected | operands had no unary sign | `-`/`+` before a numeric literal in operand position |
| numeric rendering produced `002` for 1.5 in `9V99` | the implied decimal point was not scaled back | multiply by 10^scale before formatting |
| groups could not be moved or displayed | storage registered only elementary fields | register every node, keep values for elementary ones |
| conformance of a `CALL` program escaped as an uncaught parse error | `run_original` caught only `RunError` | catch every `CobolError` and classify unsupported constructs |

## Not verified

- A real NIST CCVS85 run (URL unavailable; no pass rate claimed).
- GnuCOBOL or a mainframe as a second oracle.
- File-output comparison (stdout only in v0.1), sections, `EVALUATE`, `COPY`, packed decimal.
- macOS/Linux locally (CI covers Ubuntu and Windows on Python 3.10/3.12/3.13).
- PyPI publication (G3 gate not approved).

## Score

60/105 (round-4 third pick, SURVIVE with conditions). Conditions — never bundle NIST, rounding ADR,
name check, assertion-grade differentiator — are met: no CCVS85 files exist (test enforced), rounding is
`ROUND_HALF_UP` with mutation coverage, PyPI returns 404 for the name, and differential mode is the
documented core with its own contract and fixtures.
