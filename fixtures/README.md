# Fixtures

Everything here is written for this project; no NIST CCVS85 or third-party COBOL is included.

| Path | Purpose |
|---|---|
| `programs/*.cbl` | Six programs used by the tests and the README (hello, arithmetic, rounding, perform, conditions, string-ops) plus `loop.cbl` for the step-limit tests |
| `expected/*.out` | Expected standard output for each fixture, in the interpreter's documented DISPLAY format |
| `manifest.json` | Fixture registry consumed by `tests/integration/test_fixtures.py` (add `accept` lines for programs that read stdin) |
| `inputs/string-stdin.txt` | Input for the `ACCEPT` line in `string-ops.cbl` |
| `ports/*.py` | Hand-written "ports" for differential demos: `hello_port.py` and `arithmetic_port.py` match, `hello_bad.py` deliberately differs |
| `ports/string_port.py` | Port for the stdin example |

Run them all:

```console
$ cobrun run fixtures/programs/arithmetic.cbl
$ cobrun diff fixtures/programs/hello.cbl --port fixtures/ports/hello_port.py
$ cobrun diff fixtures/programs/hello.cbl --port fixtures/ports/hello_bad.py   # exits 1
```
