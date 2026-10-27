# cobrun

Pure-Python **COBOL-85 core-subset interpreter** with assertion-grade differential testing: run the
original COBOL, run the port, diff the output, and trust the port only when they match.

```console
$ pip install cobrun
$ cobrun run fixtures/programs/hello.cbl
HELLO WORLD

$ cobrun diff fixtures/programs/hello.cbl --port fixtures/ports/hello_port.py
match
```

No native extensions, no runtime dependencies, Python 3.10+. MIT.

**Status:** v0.1.0, alpha. The supported subset is frozen in [docs/COBOL_SUBSET.md](docs/COBOL_SUBSET.md).
145 tests; NIST CCVS85 is fetched at runtime only (see below) and **not bundled**.

## Why this tool

Porting COBOL to a modern language is risky because one semantic difference — `ROUNDED` against Python's
bank rounding, truncation, padding, `PERFORM VARYING` bounds — can silently corrupt money. Translators
produce code you cannot check. `cobrun` runs the original program so you can compare the original and the
port on the same inputs, and fail the build when they disagree.

| Option | Position |
|---|---|
| pythonbol-style translators | produce code, not evidence; this is an interpreter |
| GnuCOBOL and vendor compilers | production compilers, native builds; this is pure Python and test-focused |
| Mainframe emulators | heavyweight, commercial; this is a lightweight core subset |
| Hand-written regression scripts | no COBOL semantics; this runs the actual source |

## Install

```console
$ pip install cobrun          # once published; until then:
$ git clone https://github.com/maxico714/cobrun && cd cobrun
$ pip install .
```

Pure-Python wheel (`py3-none-any`), no compiler, no native build.

## Usage

### Run a program

```console
$ cobrun run fixtures/programs/string-ops.cbl --input fixtures/inputs/string-stdin.txt
ADA LOVELACE
3
BONONO
RED GREEN BLUE
ZZ
```

`--json` prints a run report (`statements_executed`, `decimal_ops`, `rounding_ops`, `stopped`).
`--step-limit` bounds runaway `GO TO`/`PERFORM` loops (default 100 000 statements).

### Differential mode

```console
$ cobrun diff fixtures/programs/arithmetic.cbl --port fixtures/ports/arithmetic_port.py --json
{"match": true, "difference": "", "original": "...", "port": "..."}
```

Exit codes: `0` match, `1` mismatch, `2` parse error, `3` conformance failure, `4` port/oracle failure,
`5` usage/config. The comparison rules are in [docs/DIFF_CONTRACT.md](docs/DIFF_CONTRACT.md): UTF-8,
normalised line endings, trailing spaces and trailing blank lines ignored, everything else exact.

### Parse only

```console
$ cobrun dry-run fixtures/programs/hello.cbl
parse ok: HELLO (1 paragraph(s))
$ cobrun parse fixtures/programs/hello.cbl --json
{"program": "HELLO", "paragraphs": ["MAIN"], "data_roots": 1}
```

### Conformance directories

```console
$ cobrun conformance --ccvs path/to/suite
pass        CM101-hello
fail        CM102-arith (expected '42', got '43')
unsupported SM201-call (CALL is not supported in v0.1)
1/3 passed, 1 failed, 1 unsupported
```

Layout and semantics: [docs/CONFORMANCE.md](docs/CONFORMANCE.md).

### CCVS85

`cobrun fetch-ccvs` downloads the NIST suite **at runtime**; the repository contains no CCVS85 files and a
test enforces that. As of 2026-10-26 the historical NIST URL redirects to a generic page and no longer
serves the archive, so the command fails closed with an explicit message rather than saving HTML. See
[docs/EVIDENCE.md](docs/EVIDENCE.md).

## What is supported

IDENTIFICATION / ENVIRONMENT / DATA / PROCEDURE divisions; `PIC` with `9`, `S`, `V`, `X` and repeats;
levels `01`–`49`, `77`, `88` with `THRU` ranges; `USAGE DISPLAY`; `MOVE`; `ADD`/`SUBTRACT`/`MULTIPLY`/
`DIVIDE`/`COMPUTE` with `ROUNDED` and `ON SIZE ERROR`; `IF`/`ELSE` with Kleene-free boolean conditions and
88 names; `PERFORM` (paragraph, `THRU`, `TIMES`, `UNTIL`, `VARYING`, inline); `GO TO`; `STOP RUN`;
`DISPLAY`; `ACCEPT`; `STRING`; `UNSTRING`; `INSPECT TALLYING/REPLACING`.

**`ROUNDED` is `ROUND_HALF_UP`** (`2.25 → 2.3`, `-2.25 → -2.3`), overriding Python's default bank
rounding. Everything else — `CALL`, `EVALUATE`, file I/O, `COPY`, `COMP-3` — is rejected explicitly in
v0.1. Full contract: [docs/COBOL_SUBSET.md](docs/COBOL_SUBSET.md).

## Honest limitations

- **Numeric `DISPLAY` prints the value, not the stored digit image** (`007` → `7`). This is the largest
  deviation from a mainframe and is deliberate; see the diff contract.
- **No file I/O, CALL, EVALUATE, COPY or packed decimal.** This is a batch-calculation subset, not a
  migration compiler.
- **CCVS85 could not be fetched** at build time (redirects). The conformance runner is tested with
  hand-written pairs; the pass rate is not a NIST claim.
- **One platform was verified directly** (Windows 10, Python 3.12); CI covers Ubuntu and Windows on 3.10,
  3.12 and 3.13.
- **`GO TO` out of a `PERFORMed` paragraph is an error**, not COBOL's unwind behaviour.
- Not published to PyPI yet; the name `cobrun` returned 404 there on 2026-10-26.

## Development

```console
$ pip install -e ".[dev]"
$ ruff check . && ruff format --check . && mypy && pytest
```

145 tests cover the source reader, PICTURE parsing, parser, interpreter, arithmetic and rounding, the
fixtures, differential mode, conformance, adversarial limits and provenance checks.

## Licence

MIT — [LICENSE](LICENSE), [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
