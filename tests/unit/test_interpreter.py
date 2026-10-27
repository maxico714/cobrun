from __future__ import annotations

from decimal import Decimal
from io import StringIO
from pathlib import Path

import pytest

from cobrun.errors import RunError, StepLimitError
from cobrun.interpreter import Interpreter, run_source
from cobrun.parser import parse_program

PROGRAMS = Path(__file__).resolve().parents[2] / "fixtures" / "programs"
EXPECTED = Path(__file__).resolve().parents[2] / "fixtures" / "expected"


def run_fixture(name: str, accept: list[str] | None = None) -> str:
    output = StringIO()
    run_source(
        (PROGRAMS / f"{name}.cbl").read_text(encoding="utf-8"),
        output=output,
        accept=accept,
    )
    return output.getvalue()


def test_hello_output() -> None:
    assert run_fixture("hello") == (EXPECTED / "hello.out").read_text(encoding="utf-8")


def test_arithmetic_output() -> None:
    assert run_fixture("arithmetic") == (EXPECTED / "arithmetic.out").read_text(encoding="utf-8")


def test_rounding_output() -> None:
    assert run_fixture("rounding") == (EXPECTED / "rounding.out").read_text(encoding="utf-8")


def test_perform_output() -> None:
    assert run_fixture("perform") == (EXPECTED / "perform.out").read_text(encoding="utf-8")


def test_conditions_output() -> None:
    assert run_fixture("conditions") == (EXPECTED / "conditions.out").read_text(encoding="utf-8")


def test_string_ops_output() -> None:
    assert run_fixture("string-ops", accept=["ZZ"]) == (EXPECTED / "string-ops.out").read_text(encoding="utf-8")


def test_step_limit_stops_a_go_to_loop() -> None:
    program = parse_program((PROGRAMS / "loop.cbl").read_text(encoding="utf-8"))
    interpreter = Interpreter(program, step_limit=50)
    with pytest.raises(StepLimitError) as caught:
        interpreter.run()
    assert "50 statements" in caught.value.message


def test_division_by_zero_is_a_runtime_error() -> None:
    with pytest.raises(RunError) as caught:
        run_source("""IDENTIFICATION DIVISION.
PROGRAM-ID. DIV.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(2) VALUE 1.
PROCEDURE DIVISION.
MAIN.
    COMPUTE A = A / 0.
    STOP RUN.
""")
    assert "division by zero" in caught.value.message


def test_unknown_paragraph() -> None:
    with pytest.raises(RunError) as caught:
        run_source("""IDENTIFICATION DIVISION.
PROGRAM-ID. P.
PROCEDURE DIVISION.
MAIN.
    PERFORM MISSING.
    STOP RUN.
""")
    assert "unknown paragraph" in caught.value.message


def test_unknown_data_name() -> None:
    with pytest.raises(RunError) as caught:
        run_source("""IDENTIFICATION DIVISION.
PROGRAM-ID. P.
PROCEDURE DIVISION.
MAIN.
    MOVE 1 TO MISSING.
    STOP RUN.
""")
    assert "unknown data name" in caught.value.message


def test_size_error_without_handler_truncates_high_order_digits() -> None:
    output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(3).
PROCEDURE DIVISION.
MAIN.
    MOVE 1234 TO A.
    DISPLAY A.
    STOP RUN.
""",
        output=output,
    )
    assert output.getvalue() == "234\n"


def test_size_error_handler_runs_and_leaves_target_unchanged() -> None:
    output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(3) VALUE 7.
PROCEDURE DIVISION.
MAIN.
    ADD 999 999 GIVING A ON SIZE ERROR DISPLAY "OVERFLOW".
    DISPLAY A.
    STOP RUN.
""",
        output=output,
    )
    assert output.getvalue() == "OVERFLOW\n7\n"


def test_negative_value_into_unsigned_field_is_a_size_error() -> None:
    output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(3) VALUE 5.
PROCEDURE DIVISION.
MAIN.
    COMPUTE A = 0 - 1 ON SIZE ERROR DISPLAY "NEG".
    DISPLAY A.
    STOP RUN.
""",
        output=output,
    )
    assert output.getvalue() == "NEG\n5\n"


def test_signed_field_accepts_negative_values() -> None:
    output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC S9(3)V99.
PROCEDURE DIVISION.
MAIN.
    COMPUTE A = 10 / -4.
    DISPLAY A.
    STOP RUN.
""",
        output=output,
    )
    assert output.getvalue() == "-2.5\n"


def test_move_numeric_to_alphanumeric_uses_display_form() -> None:
    output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 N PIC 9(3)V9 VALUE 12.5.
01 T PIC X(8).
PROCEDURE DIVISION.
MAIN.
    MOVE N TO T.
    DISPLAY T.
    STOP RUN.
""",
        output=output,
    )
    assert output.getvalue() == "12.5\n"


def test_move_to_group_distributes_text() -> None:
    output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 G.
   05 G1 PIC X(2).
   05 G2 PIC X(3).
PROCEDURE DIVISION.
MAIN.
    MOVE "ABCDE" TO G.
    DISPLAY G1 "|" G2.
    STOP RUN.
""",
        output=output,
    )
    assert output.getvalue() == "AB|CDE\n"


def test_88_range_and_value_conditions() -> None:
    output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(2) VALUE 7.
   88 LOW-RANGE VALUE 0 THRU 5.
   88 EXACT VALUE 7.
PROCEDURE DIVISION.
MAIN.
    IF LOW-RANGE
        DISPLAY "LOW"
    ELSE
        IF EXACT
            DISPLAY "EXACT"
        END-IF
    END-IF.
    STOP RUN.
""",
        output=output,
    )
    assert output.getvalue() == "EXACT\n"


def test_accept_without_input_yields_empty() -> None:
    output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 T PIC X(4) VALUE "XX".
PROCEDURE DIVISION.
MAIN.
    ACCEPT T.
    DISPLAY T.
    STOP RUN.
""",
        output=output,
    )
    assert output.getvalue() == "\n"


def test_report_counters() -> None:
    program = parse_program((PROGRAMS / "arithmetic.cbl").read_text(encoding="utf-8"))
    interpreter = Interpreter(program)
    interpreter.run()
    report = interpreter.report()
    assert report["program"] == "ARITH"
    assert report["statements_executed"] > 0
    assert report["decimal_ops"] > 0
    assert report["rounding_ops"] == 1
    assert report["stopped"] is True


def test_perform_thru_runs_the_span() -> None:
    output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(2) VALUE 0.
PROCEDURE DIVISION.
MAIN.
    PERFORM FIRST THRU SECOND.
    DISPLAY A.
    STOP RUN.
FIRST.
    ADD 1 TO A.
SECOND.
    ADD 10 TO A.
""",
        output=output,
    )
    assert output.getvalue() == "11\n"


def test_inspect_tallying_counts_occurrences() -> None:
    output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 T PIC X(6) VALUE "ABABAB".
01 C PIC 9(2) VALUE 0.
PROCEDURE DIVISION.
MAIN.
    INSPECT T TALLYING C FOR ALL "AB".
    DISPLAY C.
    STOP RUN.
""",
        output=output,
    )
    assert output.getvalue() == "3\n"


def test_decimal_precision_is_exact() -> None:
    interpreter_output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(1)V9(18).
PROCEDURE DIVISION.
MAIN.
    COMPUTE A = 1 / 3.
    DISPLAY A.
    STOP RUN.
""",
        output=interpreter_output,
    )
    assert interpreter_output.getvalue().startswith("0.333333333333333333")


def test_negative_zero_displays_without_sign() -> None:
    output = StringIO()
    run_source(
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC S9(2)V9.
PROCEDURE DIVISION.
MAIN.
    COMPUTE A = 0.
    DISPLAY A.
    STOP RUN.
""",
        output=output,
    )
    assert output.getvalue() == "0\n"


def test_storage_values_are_decimal() -> None:
    program = parse_program((PROGRAMS / "arithmetic.cbl").read_text(encoding="utf-8"))
    interpreter = Interpreter(program)
    interpreter.run()
    value = interpreter.storage.read("WS-SUM")
    assert isinstance(value, Decimal)
