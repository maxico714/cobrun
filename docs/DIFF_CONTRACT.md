# DIFF CONTRACT — how `cobrun diff` decides "identical"

The product claim is assertion-grade differential testing: run the original COBOL under `cobrun`, run the
port under its own runtime, and compare. This document is the comparison contract, so a green diff means
exactly what it says.

## What runs

```
cobrun diff original.cbl --port "python port.py" [--input in.dat] [--json]
```

1. `original.cbl` is parsed and executed by `cobrun` with the same stdin bytes.
2. The port command is executed with `subprocess.run(argv, input=stdin, capture_output=True, timeout=60,
   shell=False)`. A bare `.py` path is run with the current interpreter (`sys.executable`). The port must
   exit with status 0; anything else is reported as an oracle error, not a mismatch.
3. Both standard outputs are compared; the port's stderr is ignored unless the port fails.

## Normalisation (applied to both sides)

1. Decode as UTF-8 (the interpreter only emits text).
2. Convert `\r\n` and `\r` to `\n`.
3. Strip trailing whitespace from every line (`line.rstrip()`). This removes COBOL's fixed-width padding.
4. Drop trailing empty lines.
5. Everything else — case, leading spaces, internal blank lines, punctuation — must match exactly.

The first differing line is reported (`line N: original '…' vs port '…'`), or a line-count difference when
one side is a prefix of the other.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | outputs match after normalisation |
| 1 | outputs differ (a real mismatch) |
| 4 | could not run the original or the port |

## What a match does and does not prove

- It proves the port reproduces this input's observable output, under this contract, on this machine.
- It does **not** prove file output, database effects, timing, or behaviour on inputs you did not run.
  Run a corpus of realistic inputs, including boundary records, before treating the port as equivalent.
- It does not compare the port's internals; rounding and truncation differences show up only if they
  reach the output.

## Why the contract normalises trailing spaces

COBOL DISPLAY of a padded alphanumeric field emits the padding (`WS-NAME PIC X(10)` prints `ADA` followed
by seven spaces). Almost every port prints the trimmed text. Treating trailing spaces as insignificant
keeps the signal on real differences (values, order, text) instead of padding artefacts. If you need byte
comparison including padding, compare the raw outputs yourself; `--json` includes both normalised texts.

## The interpreter's own DISPLAY format

`cobrun` prints numeric fields as their value (no leading zeros, no implied decimal point): `007` prints
`7`, `25.00` prints `25`. This differs from a mainframe's digit image. The contract is symmetric — the
port must reproduce `cobrun`'s format — which is why `docs/COBOL_SUBSET.md` lists it as the single largest
deviation. For byte-accurate mainframe comparison, use the mainframe itself as the oracle and keep the
normalisation rules above.
