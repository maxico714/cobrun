# ROADMAP — cobrun

Status: v0.1.0 built and verified (2026-10-26). SemVer; Keep a Changelog. **Never bundles NIST CCVS85.**
`ROUNDED` = `ROUND_HALF_UP`.

## v0.1 — Walking skeleton (done)

- [x] Gate 0: rounding semantics probed and frozen; CCVS85 URL checked — it redirects to a generic NIST
      page and no longer serves an archive, so `fetch-ccvs` fails closed and conformance runs on
      user-supplied directories. Recorded in `docs/EVIDENCE.md`.
- [x] Source reader (fixed and free format), tokenizer, parser for the documented subset.
- [x] PICTURE engine (`9`, `S`, `V`, `X`, repeats), levels 01–49/77/88, storage and group moves.
- [x] Arithmetic with exact decimals, `ROUNDED` = `ROUND_HALF_UP`, truncation and `ON SIZE ERROR`.
- [x] Statements: `MOVE`, `ADD`/`SUBTRACT`/`MULTIPLY`/`DIVIDE`/`COMPUTE`, `IF`/`ELSE`, `PERFORM`
      (paragraph/THRU/TIMES/UNTIL/VARYING/inline), `GO TO`, `STOP RUN`, `DISPLAY`, `ACCEPT`, `STRING`,
      `UNSTRING`, `INSPECT TALLYING/REPLACING`, `CONTINUE`.
- [x] Step limit, parser caps, fail-closed schema for data entries and statements.
- [x] Differential mode with a documented comparison contract and a Python port fixture.
- [x] Conformance runner for `.cbl`/`.out` directories with pass/fail/unsupported reporting.
- [x] 145 tests, mutation checks, strict mypy, ruff, CI matrix.

**Riskiest assumption, now retired:** that COBOL `ROUNDED` and decimal truncation could be matched with
`decimal.Decimal`. They can, with `ROUND_HALF_UP` on every rounding path and explicit high-order
truncation when no `ON SIZE ERROR` handler exists; tests pin `2.25 → 2.3`, `-2.25 → -2.3`, `2.24 → 2.2`
and `1234 → 234` into a `9(3)` field.

## v0.5 — Core value

- [ ] Broader PICTURE: signed overpunch storage, editing characters (`Z`, `$`, `*`, `,`), `COMP-3`
      packed-decimal simulation.
- [ ] `EVALUATE`, `SEARCH`/`SEARCH ALL`, sections, `PERFORM ... DEPENDING ON`.
- [ ] `COPY`/`REPLACING` with a copybook path allow-list (census 53/1/0 from the research).
- [ ] Sequential record I/O and a `SORT`/`MERGE` subset.
- [ ] File-output comparison in differential mode (currently stdout only).
- [ ] A second oracle (GnuCOBOL) for cross-checking; publish the divergence list.

## v1.0 — Production-ready

- [ ] IBM extension coverage with documented gaps; Micro Focus compatibility mode.
- [ ] Re-establish a verified CCVS85 source and publish a real pass rate per section.
- [ ] SBOM, signed releases, registry publish via trusted publishing (G3-gated).
- [ ] Verified on macOS/Linux and with larger programs (10k+ statements).

## Post-1.0 (parked)

Full mainframe emulator, JCL, CICS/DB2, web playground, every extension.

## Maintenance cadence

- New statements and PICTURE features are minor releases.
- Rounding, truncation or comparison changes are major releases; the differential fixtures gate every
  change.
