# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | yes |

## Reporting a vulnerability

Use GitHub's private "Report a vulnerability" form on the repository's Security tab. Do not open a public
issue for anything that could execute code, escape the interpreter's sandboxed semantics, exhaust memory,
or make `cobrun` write outside the paths you asked for.

Include the version (`cobrun --version`), the Python version, the platform, the COBOL source, and a minimal
reproduction. You can expect an acknowledgement within seven days and a remediation plan or a reasoned
decision within thirty days.

## Threat model in brief

- **COBOL source is data, not code.** There is no `eval`, no `exec`, no import machinery and no OS calls.
  `CALL` is not implemented; unknown statements are rejected.
- **Bounded resources.** Source lines (20k), tokens (200k), token length (4 KiB), nesting (100), numeric
  literal digits (100), fields (5k), source file size (5 MiB) and executed statements (100k by default)
  all have hard caps.
- **Runaway programs terminate.** Every statement counts against the step limit, so `GO TO` cycles and
  `PERFORM … BY 0` end with `E_STEPLIMIT` rather than hanging.
- **External processes.** `cobrun diff` runs the port you supply with an explicit argv list,
  `shell=False`, a 60-second timeout and captured output. A non-zero exit is reported, never ignored.
- **Downloads.** `fetch-ccvs` is the only network call. It uses a fixed HTTPS URL, a timeout, a size cap,
  and writes only after the payload passes ZIP signature and archive checks; invalid downloads are deleted.
- **No telemetry.** Nothing is sent anywhere unless you run `fetch-ccvs`.

## Out of scope

- The correctness of a port you run with `diff`; that is exactly what the tool measures.
- Mainframe-specific storage formats (overpunch, packed decimal) that the v0.1 subset does not emulate.
