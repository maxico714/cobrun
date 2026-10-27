# TECHNICAL — cobrun

Status: v0.1.0 built and verified on Windows 10 (26200) with Python 3.12.10; 2026-10-26.
Stack: Python 3.10+ standard library only (`decimal`, `subprocess`, `urllib`); no native extensions.

## Architecture

```
COBOL source ──► lexer.py (fixed/free format) ──► parser.py ──► statements.py (AST)
                                                     │
                                              data.py (PICTURE, storage, 88 levels)
                                                     ▼
                                              interpreter.py (decimal engine, control flow)
                                                     │
                        ┌────────────────────────────┼────────────────────────────┐
                        ▼                            ▼                            ▼
                   cli.py run                  diff.py                     ccvs.py conformance
                                        (original vs port)          (.cbl/.out directories, fetch)
```

| Module | Responsibility |
|---|---|
| `lexer.py` | fixed/free source reader, comments, indicator column, tokenizer, caps |
| `parser.py` | recursive descent: divisions, data entries, statements, conditions, expressions |
| `data.py` | PICTURE parsing/rendering, field tree, storage, condition names |
| `interpreter.py` | statement execution, decimal arithmetic, rounding, size errors, step limit |
| `diff.py` | run original and port, normalise and compare output |
| `ccvs.py` | fetch-at-runtime and `.cbl`/`.out` conformance runner |
| `cli.py` | `run`, `parse`, `dry-run`, `diff`, `fetch-ccvs`, `conformance`, `doctor` |

## Execution model

- A `Storage` built from the DATA DIVISION owns numeric (`Decimal`) and alphanumeric values.
- Numeric storage is a PICTURE-scaled decimal: assignment rounds (`ROUND_HALF_UP`) or truncates, and
  checks integer capacity for `ON SIZE ERROR`.
- Execution walks paragraphs in order; `GO TO` returns a target paragraph index, `PERFORM` executes a
  paragraph span or an inline body with `TIMES`/`UNTIL`/`VARYING`, and the step limit counts every
  statement executed, including inside loops.
- `STOP RUN` ends the program; the CLI exits 0.
- Every executed statement increments a counter; arithmetic and rounding increment their own counters for
  the run report.

## Numeric semantics

- `decimal.Decimal` throughout; the default context precision (28 significant digits) applies to division.
- `ROUNDED` = `ROUND_HALF_UP` (away from zero at the half). Without `ROUNDED`, truncation toward zero.
- Size error conditions: integer digits exceed the PICTURE's integer capacity, or a negative value is
  stored into an unsigned field. With a handler, the handler runs and the target is unchanged; without
  one, high-order digits are dropped.
- Division by zero raises `E_RUNTIME` (not a size error).

## Error model

| Code | Class | Raised for |
|---|---|---|
| `E_PARSE` | `ParseError` | unsupported construct, malformed source, caps exceeded (with line) |
| `E_RUNTIME` | `RunError` | unknown data name/paragraph/condition, division by zero, invalid storage use |
| `E_STEPLIMIT` | `StepLimitError` | statements executed exceed the limit |
| `E_CONFIG` | `ConfigError` | unreadable/oversized CLI files, bad port command |
| `E_ORACLE` | `OracleError` | port failed or timed out, CCVS85 download unusable |
| `E_CONFORMANCE` | `ConformanceError` | conformance directory missing or without `.cbl`/`.out` pairs |

## Limits

20 000 source lines, 200 000 tokens, 4 096 characters per token, 100 nesting levels, 100 digits per
numeric literal, 5 000 fields, 5 MiB source files, 100 000 statements (default step limit), 60 s per port
run, 200 MB CCVS85 download cap.

## Threat model (STRIDE-lite)

- **COBOL source is untrusted.** No `eval`, no shell, no OS calls from COBOL; `CALL` is absent. The parser
  has hard caps on lines, tokens, token length, nesting and literal digits.
- **Runaway programs.** Every executed statement counts against the step limit, so `GO TO` cycles and
  `PERFORM BY 0` terminate with `E_STEPLIMIT` instead of hanging.
- **Differential mode** runs the user-supplied port with an explicit argv list, `shell=False`, a timeout,
  captured output. A non-zero exit or timeout is an oracle error, never a silent mismatch.
- **CCVS85** is never bundled; `fetch-ccvs` verifies the payload starts with a ZIP signature and is a
  readable archive before writing, and deletes invalid downloads.
- **Supply chain:** zero runtime dependencies; a test parses every import and asserts stdlib-only.
- **Privacy:** no telemetry; the only network call is the explicit `fetch-ccvs` command.

## Testing strategy

| Level | Evidence |
|---|---|
| L0 | `ruff check`, `ruff format --check`, strict `mypy` |
| L1 | 145 tests across lexer (19), picture (12), parser (23), interpreter (24), diff (12), conformance (10), CLI (20), fixtures (6), adversarial (12), provenance (7) |
| L2 | Six fixture programs (hello, arithmetic, rounding, perform, conditions, string-ops) against expected output |
| L3 | Differential mode on hello and arithmetic (match) and a wrong port (mismatch with line); conformance runner pass/fail/unsupported |
| L4 | Fresh copy → venv → `pip install .` → full test run (recorded in `BUILD_CHECKLIST.md`) |
| L5 | Step limit, `BY 0`, huge literals, deep nesting, overflow, negative-into-unsigned, unknown names, empty input |

Mutation checks (each killed its intended test, then restored): half-even rounding, inverted overflow
check, subtraction turned into addition.

## Packaging

Pure-Python wheel (`py3-none-any`) and sdist via `python -m build`; `twine check` clean. PyPI returns 404
for `cobrun` (2026-10-26). Publishing is G3-gated and not executed.

## Deviations from the scaffold

| Scaffold | Built | Why |
|---|---|---|
| `PROCEDURE DIVISION` in a separate `procedure.py` | inside `parser.py` + `statements.py` | keeps parsing in one place; execution lives in the interpreter |
| `CALL` basic | rejected with a clear error | half-working within-interpreter CALL semantics are worse than none |
| CCVS85 fetch expected to work | fails closed (URL redirects) | verified at Gate 0; honesty over a fabricated pass rate |
| Configurable global scale | PICTURE-driven scale and the interpreter's decimal context | matches how COBOL code actually declares scale |
| `diff` compares stdout + files | stdout only | file I/O is not in the v0.1 subset; documented in DIFF_CONTRACT |
