# Conformance runs — layout and honesty

`cobrun conformance --ccvs <dir>` executes every `.cbl` file that has a sibling `.out` file and reports a
pass rate per section. It does not download anything; you supply the directory.

## Directory layout

```
<dir>/
  CM101-hello.cbl      # program source (free or fixed format)
  CM101-hello.out      # expected standard output
  CM102-arith.cbl
  CM102-arith.out
  SM201-call.cbl       # unsupported construct -> reported, not silently skipped
  SM201-call.out
```

- Pairs are found by matching the stem (`CM101-hello.cbl` ↔ `CM101-hello.out`); a `.cbl` without an
  `.out` is ignored, and a directory with no pairs is an error (`E_CONFORMANCE`).
- The **section** is the part of the stem before the first `-` or `_` (`CM101`), which is how NIST CCVS85
  names its tests.
- Expected output is compared with the same normalisation as `cobrun diff` (UTF-8, line endings, trailing
  spaces, trailing blank lines), documented in `DIFF_CONTRACT.md`.
- A case that fails with a parse error mentioning an unsupported construct is reported as
  **unsupported**; other runtime failures are **fail**.

Exit code: `0` when nothing failed (unsupported cases are counted and shown, not hidden), `3` when at
least one case failed.

## NIST CCVS85 status (2026-10-26)

The historical download URL
`https://www.itl.nist.gov/div897/ctg/software/ccvs85.zip` redirects to `https://www.nist.gov/itl` and
returns HTML, not a ZIP. `cobrun fetch-ccvs` therefore fails closed with a clear message and never writes
a partial file. No CCVS85 material is stored in this repository; a test enforces that.

Until the canonical location is re-established (`docs/EVIDENCE.md` tracks it), conformance runs use
hand-written `.cbl`/`.out` pairs. The pass rate of such a suite says how well the interpreter matches
**those** expectations — not how conformant it is with NIST.
