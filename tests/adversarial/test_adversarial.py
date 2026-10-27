from __future__ import annotations

import json
from pathlib import Path

import pytest

from cobrun.errors import RunError, StepLimitError
from cobrun.interpreter import Interpreter, run_source
from cobrun.parser import parse_program

REPO = Path(__file__).resolve().parents[2]


def test_perform_times_huge_hits_step_limit() -> None:
    with pytest.raises(StepLimitError):
        run_source(
            """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(3).
PROCEDURE DIVISION.
MAIN.
    PERFORM BUMP 999999 TIMES.
    STOP RUN.
BUMP.
    ADD 1 TO A.
""",
            step_limit=500,
        )


def test_varying_by_zero_hits_step_limit() -> None:
    with pytest.raises(StepLimitError):
        run_source(
            """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 I PIC 9(3).
PROCEDURE DIVISION.
MAIN.
    PERFORM VARYING I FROM 1 BY 0 UNTIL I > 5
        DISPLAY I
    END-PERFORM.
    STOP RUN.
""",
            step_limit=200,
        )


def test_huge_numeric_literal_is_rejected() -> None:
    from cobrun.errors import ParseError

    with pytest.raises(ParseError):
        parse_program(
            """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(3).
PROCEDURE DIVISION.
MAIN.
    MOVE """
            + "9" * 500
            + """ TO A.
    STOP RUN.
"""
        )


def test_missing_division_and_garbage() -> None:
    from cobrun.errors import ParseError

    for source in ["", "IDENTIFICATION DIVISION.\n", "PROCEDURE DIVISION.\nMAIN.\nSTOP RUN.\n"]:
        with pytest.raises(ParseError):
            parse_program(source)


def test_deep_if_nesting_is_bounded() -> None:
    from cobrun.errors import ParseError

    body = "IF A = 1\n" * 200 + "MOVE 1 TO A\n" + "END-IF\n" * 200 + ".\n"
    source = (
        """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(3).
PROCEDURE DIVISION.
MAIN.
"""
        + body
        + "STOP RUN.\n"
    )
    with pytest.raises(ParseError):
        parse_program(source)


def test_overflow_without_handler_truncates_repeatedly() -> None:
    output: list[str] = []
    interpreter = Interpreter(
        parse_program(
            """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(2) VALUE 99.
PROCEDURE DIVISION.
MAIN.
    ADD 1 TO A.
    DISPLAY A.
    ADD 1 TO A.
    DISPLAY A.
    STOP RUN.
"""
        ),
        output=output.append,
    )
    interpreter.run()
    assert output == ["0", "1"]


def test_division_by_zero_via_divide_statement() -> None:
    with pytest.raises(RunError):
        run_source("""IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC 9(2) VALUE 1.
01 B PIC 9(2) VALUE 0.
PROCEDURE DIVISION.
MAIN.
    DIVIDE A BY B GIVING A.
    STOP RUN.
""")


def test_go_to_out_of_perform_is_reported() -> None:
    with pytest.raises(RunError):
        run_source("""IDENTIFICATION DIVISION.
PROGRAM-ID. P.
PROCEDURE DIVISION.
MAIN.
    PERFORM INNER.
    STOP RUN.
INNER.
    GO TO ELSEWHERE.
ELSEWHERE.
    DISPLAY "X".
""")


def test_unknown_condition_name() -> None:
    with pytest.raises(RunError):
        run_source("""IDENTIFICATION DIVISION.
PROGRAM-ID. P.
PROCEDURE DIVISION.
MAIN.
    IF NOT-A-CONDITION
        DISPLAY "X"
    END-IF.
    STOP RUN.
""")


def test_unstring_with_more_targets_than_pieces() -> None:
    output: list[str] = []
    interpreter = Interpreter(
        parse_program(
            """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC X(3) VALUE "AAA".
01 B PIC X(3) VALUE "BBB".
PROCEDURE DIVISION.
MAIN.
    UNSTRING "ONE" DELIMITED BY "," INTO A B.
    DISPLAY A "|" B.
    STOP RUN.
"""
        ),
        output=output.append,
    )
    interpreter.run()
    assert output == ["ONE|BBB"]


def test_hostile_string_replace_with_empty_pattern() -> None:
    output: list[str] = []
    interpreter = Interpreter(
        parse_program(
            """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 A PIC X(4) VALUE "ABAB".
PROCEDURE DIVISION.
MAIN.
    INSPECT A REPLACING ALL "" BY "X".
    DISPLAY A.
    STOP RUN.
"""
        ),
        output=output.append,
    )
    interpreter.run()
    assert output == ["ABAB"]


def test_json_round_trip_of_run_report(tmp_path: Path) -> None:
    report = {"program": "P", "statements_executed": 1, "decimal_ops": 0, "rounding_ops": 0, "stopped": True}
    path = tmp_path / "report.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    assert json.loads(path.read_text(encoding="utf-8"))["program"] == "P"
