# PRODUCT — cobrun

Status: v0.1.0 built, tested and verified (2026-10-26). MIT, alpha.

## Problem

Enterprises still run millions of lines of COBOL (mainframe batch jobs, midrange transaction systems, distributed processing). Porting to modern languages (Java, Python, Go) is high-risk: a single semantic divergence — rounding (`ROUNDED` = `ROUND_HALF_UP` vs Python's default `ROUND_HALF_EVEN`), decimal arithmetic precision, string handling (`INSPECT`, `UNSTRING`), or `PERFORM` VARYING bounds — can silently corrupt financial calculations. Existing Python options are translators (PythonBol-Translator) that lose fidelity, or abandoned projects. Teams need **assertion-grade fidelity**: run the original COBOL under test, run the port, diff outputs, trust the port only when they match.

## Target users (personas)

1. **Mainframe modernization engineer (primary):** porting COBOL batch jobs to Java/Python. Job: prove the port produces identical outputs on the same inputs before cutting over.
2. **Financial systems auditor (secondary):** needs evidence that a port didn't change rounding/precision behavior. Job: NIST CCVS85 conformance run + differential report.
3. **COBOL educator / student (tertiary):** runs small COBOL programs without a mainframe. Job: pure-Python interpreter, no install friction.

## Jobs-to-be-done

- "Run this COBOL-85 batch program in Python and get identical output to the mainframe."
- "Prove our Java port rounds the same way as the original COBOL."
- "Run NIST CCVS85 conformance against our interpreter; show pass rate."

## Value proposition (one sentence)

Pure-Python COBOL-85 core-subset interpreter with assertion-grade fidelity — run the original, run the port, diff outputs, trust the port only when they match.

## Non-goals (explicit)

- Not a full COBOL compiler (core subset only; no full IBM/Micro Focus extensions in v1).
- Not a porting tool (interpreter runs original source; porting is human + differential proof).
- Not a mainframe emulator (no JCL, no CICS, no DB2 — batch/transaction COBOL core only).
- Not bundling NIST CCVS85 (fetched at runtime only — provenance risk).

## MVP scope (MoSCoW)

**Must (v0.1) — delivered:**
- Divisions: IDENTIFICATION, ENVIRONMENT (accepted and skipped), DATA (`WORKING-STORAGE`, levels 01–49/77/88,
  `USAGE DISPLAY`, PICTURE `9`/`S`/`V`/`X` with repeats), PROCEDURE (paragraphs and sentences).
- Statements: `MOVE`, `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE`, `COMPUTE`, `IF/ELSE` with 88 condition names,
  `PERFORM` (paragraph, `THRU`, `TIMES`, `UNTIL`, `VARYING`, inline), `GO TO`, `STOP RUN`, `DISPLAY`,
  `ACCEPT`, `STRING`, `UNSTRING`, `INSPECT` TALLYING/REPLACING, `CONTINUE`.
- Arithmetic: `ROUNDED` = **ROUND_HALF_UP** everywhere, `ON SIZE ERROR`, decimal `Decimal`, PICTURE-driven scale.
- NIST CCVS85 **fetched at runtime only**: `fetch-ccvs` implemented and fail-closed (the historical URL now
  redirects), `conformance` runs user-supplied `.cbl`/`.out` pairs with per-section pass rates.
- Differential mode: `cobrun diff original.cbl --port port.py --input in.dat` comparing normalised stdout.
- `doctor` self-check; `dry-run` (parse only); step limit for runaway programs.
- Deferred: `CALL` (rejected), file I/O, `EVALUATE`, `COPY`, packed decimal, `COMP-3`, editing characters.

**Should (v0.5):**
- Broader PICTURE clauses (signed, packed-decimal simulation, editing).
- `SEARCH` / `SEARCH ALL`; `EVALUATE`; `SECTION` / `paragraph` PERFORM.
- Record I/O (sequential, VSAM-ish basic); `SORT` / `MERGE` basic.
- COPY / REPLACING (COPY census: 53 / 1 / 0 — round-4 M2).

**Could (v1.0):**
- IBM extension coverage (documented gaps); Micro Focus compatibility mode.
- CICS/DB2 stubs (not full — stubs for differential on batch portions).
- Web REPL / playground.

**Won't (this run):** full mainframe emulator; JCL; bundling NIST; every COBOL extension.

## Success criteria (measurable)

| Criterion | Measure | Command/proof |
|---|---|---|
| L1 units | Lexer/parser/evaluator unit tests (≥40 statements) | 145 tests pass |
| L2 integration | Hand-written COBOL fixtures run correctly | six programs, expected outputs match |
| L3 e2e | Differential mode works; conformance runner reports pass/fail/unsupported | `cobrun diff` on hello/arithmetic; conformance tests |
| L4 clean env | Fresh copy + `pip install .` + tests green | recorded in `BUILD_CHECKLIST.md` |
| L5 adversarial | Rounding edges, `ON SIZE ERROR`, step limit, `BY 0`, huge literals, deep nesting | `tests/adversarial/` |
| Never-bundle | Zero NIST CCVS85 files; only own fixtures | `tests/security/test_provenance.py` |
| Rounding honesty | ROUNDED = ROUND_HALF_UP documented, tested and mutation-checked | fixtures + mutation run |

## Honest comparison

- **PythonBol-Translator:** a translator (produces code you cannot check against the original); `cobrun` is an interpreter and differential runner.
- **Full mainframe emulators (IBM, Micro Focus):** commercial and heavyweight; `cobrun` is pure Python, lightweight and test-focused.
- **GnuCOBOL:** a C compiler for production; `cobrun` needs no native build and targets differential testing. GnuCOBOL is the better choice for production execution.
- **Hand-written regression scripts:** no COBOL semantics; `cobrun` runs the actual source.
- **CCVS85:** the reference suite; it is not bundled, and its historical download URL currently redirects, so no NIST pass rate is claimed.

## Naming & license

- Name `cobrun` — PyPI returned 404 on 2026-10-26 (available). Unrelated GitHub projects share the name; installation goes through PyPI, so that is not a blocker.
- License: MIT (core); NIST CCVS85 fetched separately (public domain, but provenance risk — never bundle).

## Risk register (top)

| Risk | Sev | Mitigation |
|---|---|---|
| COBOL semantics complexity explodes | High | Core subset only; assertion-grade differentiator; CCVS85 oracle |
| Rounding divergence corrupts financials | High | ROUNDED = ROUND_HALF_UP ADR day one; differential tests |
| NIST provenance risk | High | never bundle; fetch-at-runtime only; a test asserts no CCVS85 files |
| CCVS85 URL unavailable | Med | accepted: `fetch-ccvs` fails closed; conformance runs on user-supplied directories; no pass-rate claim |
| Numeric DISPLAY differs from a mainframe | Med | documented as the largest deviation; the diff contract is symmetric |
