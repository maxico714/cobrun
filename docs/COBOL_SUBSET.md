# COBOL subset — v0.1 (normative)

This is the contract for `cobrun` v0.1. Anything not listed is rejected with `E_PARSE` rather than
guessed. The interpreter follows COBOL-85 semantics for the constructs it supports, with the deviations
listed at the end.

## Source format

- **Free format** (default for this project's fixtures): code from column 1; `*>` starts a comment.
- **Fixed format** (auto-detected when columns 1–6 hold sequence numbers or column 7 holds `*`, `/`, `-`
  or `D`): columns 1–6 ignored, column 7 is the indicator (`*`/`/` comment, `D` debug line, `-`
  continuation — continuations are rejected with a clear error), code in columns 8–72.
- Words are case-insensitive and uppercased; hyphens are part of a word (`WS-COUNT`).
- Literals: numeric (`123`, `2.25`), alphanumeric with `'…'` or `"…"` and doubled quotes for an embedded
  quote.
- Comments: `*>` anywhere in free format; `*` or `/` in column 7 in fixed format.

## Divisions

| Division | Support |
|---|---|
| IDENTIFICATION | required; `PROGRAM-ID.` required |
| ENVIRONMENT | accepted and skipped (no FILE-CONTROL semantics) |
| DATA | `WORKING-STORAGE SECTION`; `FILE`, `LINKAGE`, `LOCAL-STORAGE` and `SCREEN` sections are rejected |
| PROCEDURE | required; paragraphs and sentences |

`DATA DIVISION.` may be omitted entirely (leniency for small programs; COBOL-85 requires it).

## DATA DIVISION entries

```
01 name PIC 9(3) VALUE 42.
01 group.
   05 child PIC X(5).
01 flag PIC X VALUE "Y".
   88 IS-YES VALUE "Y".
```

- Levels `01`–`49`, `77`, `88`. Level 88 entries attach to the preceding field.
- `PIC`/`PICTURE`: `9`, `S`, `V`, `X`, and `(n)` repeats. Examples: `9(3)`, `999`, `S9(5)V9(2)`,
  `9V99`, `X(10)`.
- `USAGE DISPLAY` is accepted explicitly. `COMP`, `COMP-3`, `OCCURS`, `JUSTIFIED`, `BLANK WHEN ZERO`,
  `SYNCHRONIZED` and editing characters (`Z`, `$`, `*`, `,`) are rejected in v0.1.
- `VALUE` accepts numeric and alphanumeric literals and the figuration constants below.
- 88 entries accept `VALUE literal` and `VALUE low THRU high`.

### Figurative constants

`ZERO/ZEROS/ZEROES` → `0`; `SPACE/SPACES` → `" "`; `HIGH-VALUE(S)` → `\xff`; `LOW-VALUE(S)` → `\x00`;
`QUOTE/QUOTES` → `"`.

## Storage and DISPLAY format

- Numeric fields hold a `Decimal`; the stored character form is zero-padded digits with an implied
  decimal point and a leading `-` for signed fields. No overpunch is emulated.
- Alphanumeric fields hold text, left-justified and space-padded to the PICTURE length on read.
- Groups are the concatenation of their elementary children.
- **DISPLAY of a numeric field prints the value, not the stored digits** (`007` with value 7 prints `7`,
  `25.00` prints `25`, `-2.5` keeps its sign). Real COBOL would print the digit image. This is the single
  largest deviation; it is deliberate so that differential output is readable, and it is applied
  identically to the original and the port (`docs/DIFF_CONTRACT.md`).

## PROCEDURE DIVISION statements

| Statement | Supported forms |
|---|---|
| `MOVE` | `MOVE operand TO name [name …]`; numeric → numeric (truncate/round?), numeric → alphanumeric (display form), alphanumeric → numeric (parse), any → group (distributed left to right) |
| `ADD` | `ADD a [b …] TO target [target …]`, `ADD a [b …] GIVING target`, `ROUNDED`, `ON SIZE ERROR` |
| `SUBTRACT` | `SUBTRACT a [b …] FROM target [target …]`, `ROUNDED`, `ON SIZE ERROR` |
| `MULTIPLY` | `MULTIPLY a BY b [GIVING target]`, `ROUNDED`, `ON SIZE ERROR` |
| `DIVIDE` | `DIVIDE a BY b [GIVING target]`, `DIVIDE a INTO b [GIVING target]`, `ROUNDED`, `ON SIZE ERROR` |
| `COMPUTE` | `COMPUTE target [ROUNDED] = expression [ROUNDED]`, `ON SIZE ERROR`; `+ - * /`, `**` is not supported |
| `IF` | `IF condition [statements] [ELSE statements] [END-IF]`; conditions with `=`, `<`, `>`, `<=`, `>=`, condition names (88), `AND`, `OR`, `NOT`, parentheses |
| `PERFORM` | paragraph, `THRU`, `n TIMES`, `UNTIL`, `VARYING … FROM … BY … UNTIL`, inline `… END-PERFORM` |
| `GO TO` | `GO TO paragraph` (single target) |
| `STOP RUN` | stops the program with exit code 0 |
| `DISPLAY` | literals, data names (groups included), multiple operands; `UPON` is rejected |
| `ACCEPT` | one data name, reads the next input line |
| `STRING` | operands `DELIMITED BY SIZE` into one target |
| `UNSTRING` | source `DELIMITED BY [ALL] literal` into one or more targets |
| `INSPECT` | `TALLYING target FOR ALL literal`, `REPLACING ALL literal BY literal` |
| `CONTINUE` | no operation |

`CALL`, `EVALUATE`, `SEARCH`, `SORT`, `MERGE`, file I/O, `COPY`, `ALTER`, sections and `DEPENDING ON`
are **not** supported in v0.1 and are rejected.

## Arithmetic and rounding

- Internal arithmetic uses `decimal.Decimal` with the interpreter's default context precision (28
  digits); storage truncates or rounds to the target PICTURE.
- **`ROUNDED` uses `ROUND_HALF_UP`**, i.e. halves away from zero (`2.25 → 2.3`, `-2.25 → -2.3`). This is
  COBOL's rule and the opposite of Python's default bank rounding. Every rounding operation increments the
  `rounding_ops` counter in the run report.
- Without `ROUNDED`, the result is truncated toward zero at the target scale.
- **`ON SIZE ERROR`** fires when the integer part does not fit the target PICTURE or when a negative value
  is stored into an unsigned field. It runs the imperative statement and leaves the target unchanged. With
  no handler, high-order digits are dropped (classic COBOL truncation, no exception).
- Division by zero is a runtime error (`E_RUNTIME`), not `ON SIZE ERROR`.

## Conditions and 88 levels

- A relation compares two operands; numeric fields compare numerically, alphanumeric fields compare as
  text with trailing spaces removed.
- An 88 condition name is true when the parent field matches one of its values or falls inside a
  `THRU` range (inclusive).
- `AND` binds tighter than `OR`; `NOT` binds tighter than both. COBOL abbreviated combined relations
  (`IF A = 1 OR 2`) are not supported; write both comparisons.

## Control flow and limits

- Execution starts at the paragraph named `MAIN` if present, otherwise at the first paragraph/statement.
- `GO TO` changes the current paragraph. A `GO TO` inside a `PERFORMed` paragraph is reported as an error
  rather than silently unwinding the PERFORM.
- `PERFORM paragraph THRU end` executes the paragraph span in source order.
- A step limit (default 100 000 statements) turns runaway `GO TO`/`PERFORM` loops into `E_STEPLIMIT`.
  `PERFORM n TIMES` with a huge or fractional count is truncated and bounded by the step limit.
- Parser caps: 20 000 source lines, 200 000 tokens, 4 096 characters per token, 100 nesting levels, 100
  digits per numeric literal, 5 000 fields, 5 MiB source file.

## Deviations from COBOL-85 (deliberate, documented)

1. Numeric `DISPLAY` prints the value, not the stored digit image (see above).
2. Signed DISPLAY fields use a leading `-`; no zone overpunch.
3. `DATA DIVISION` may be omitted.
4. Multiple `GO TO` targets, `ALTER`, sections, `EVALUATE`, `CALL` and file I/O are absent rather than
   approximated.
5. Numeric literals and arithmetic are decimal, not COBOL's implementation-defined binary/decimal mix.
6. `STRING` without `POINTER` always writes from the start of the target (COBOL does the same for the
   first STRING; a `POINTER` phrase is parsed and ignored).
