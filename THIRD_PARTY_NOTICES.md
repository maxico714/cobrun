# Third-party notices

## Runtime

`cobrun` has **no runtime dependencies**. The package imports only the Python standard library
(`argparse`, `dataclasses`, `decimal`, `io`, `json`, `pathlib`, `re`, `shlex`, `subprocess`, `sys`,
`typing`, `urllib`, `zipfile`). A test enforces this.

## Development

| Package | Version range | Licence | Purpose |
|---|---|---|---|
| `pytest` | >= 8.3 | MIT | Test runner |
| `ruff` | >= 0.9 | MIT | Linter and formatter |
| `mypy` | >= 1.14 | MIT | Static type checking |
| `build` | >= 1.2 | MIT | Wheel and sdist builds |
| `twine` | >= 6.1 | Apache-2.0 | Package metadata checks |

## NIST CCVS85 — fetched at runtime, never bundled

The NIST COBOL85 Conformance Test Suite (CCVS85) is a public-domain test suite published by NIST. This
repository contains **zero** CCVS85 files: `cobrun fetch-ccvs` downloads it at the user's request and
`cobrun conformance` runs `.cbl` / `.out` pairs from a directory the user supplies. A test asserts that
no COBOL source outside `fixtures/programs/` exists and that no archive is committed.

Fetch URL used by default: <https://www.itl.nist.gov/div897/ctg/software/ccvs85.zip>. **Status on
2026-10-26:** that URL redirects to `https://www.nist.gov/itl` and returns an HTML page rather than a ZIP,
so `fetch-ccvs` fails closed with an explicit message instead of saving garbage. Finding the current
canonical location is tracked in `docs/EVIDENCE.md`; until then, conformance runs against a local
directory prepared by the user.

## Explicitly not used

- No GnuCOBOL, Micro Focus, IBM or PythonBol code, tests or fixtures were copied. The fixtures in
  `fixtures/programs/` were written for this project.

## Comparing against a port

`cobrun diff` runs a command **you** supply (by default the current Python interpreter on a `.py` file)
with a fixed argument list, no shell, and a timeout. Nothing from that command is bundled or
redistributed.
