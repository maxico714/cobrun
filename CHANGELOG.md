# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres to
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.1.0] — 2026-10-26

### Added

- COBOL source reader for free and fixed format (sequence area, indicator column, comments; continuation
  lines rejected explicitly) and a bounded tokenizer.
- Parser for IDENTIFICATION/ENVIRONMENT/DATA/PROCEDURE divisions, levels 01–49/77/88, `PIC` with
  `9`/`S`/`V`/`X` and repeats, and the documented statement set.
- Interpreter with exact `Decimal` arithmetic, `ROUNDED` = `ROUND_HALF_UP`, truncation, `ON SIZE ERROR`,
  88 condition names with `THRU` ranges, and a configurable step limit.
- Statements: `MOVE`, `ADD`, `SUBTRACT`, `MULTIPLY`, `DIVIDE`, `COMPUTE`, `IF/ELSE`, `PERFORM`
  (paragraph/`THRU`/`TIMES`/`UNTIL`/`VARYING`/inline), `GO TO`, `STOP RUN`, `DISPLAY`, `ACCEPT`, `STRING`,
  `UNSTRING`, `INSPECT` TALLYING/REPLACING, `CONTINUE`.
- Differential mode (`cobrun diff`) with a documented normalisation contract and a Python port fixture.
- Conformance runner for `.cbl`/`.out` directories with per-section pass/fail/unsupported reporting, and a
  fail-closed `fetch-ccvs` that never bundles NIST material.
- Six fixture programs, 145 tests (including adversarial and provenance checks), strict mypy, ruff and a
  SHA-pinned CI matrix.

### Notes

- Numeric `DISPLAY` prints the value, not the stored digit image; see `docs/COBOL_SUBSET.md`.
- The historical NIST CCVS85 URL redirects to a generic page, so `fetch-ccvs` fails closed and no NIST
  pass rate is claimed.
- Not published to PyPI yet.

[Unreleased]: https://github.com/maxico714/cobrun/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/maxico714/cobrun/releases/tag/v0.1.0
