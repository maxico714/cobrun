from __future__ import annotations

from decimal import Decimal

import pytest

from cobrun.errors import ParseError
from cobrun.parser import parse_program
from cobrun.statements import (
    Accept,
    Arithmetic,
    Compute,
    ConditionName,
    Display,
    GoTo,
    If,
    InspectReplacing,
    InspectTallying,
    Move,
    Perform,
    Relation,
    StopRun,
    StringStatement,
    Unstring,
)

HEADER = """IDENTIFICATION DIVISION.
PROGRAM-ID. TESTPROG.
DATA DIVISION.
WORKING-STORAGE SECTION.
01 WS-A PIC 9(3) VALUE 0.
01 WS-B PIC 9(3) VALUE 0.
01 WS-TEXT PIC X(10).
PROCEDURE DIVISION.
MAIN.
"""


def program(body: str, data: str = "") -> object:
    source = HEADER.replace("01 WS-A PIC 9(3) VALUE 0.\n01 WS-B PIC 9(3) VALUE 0.\n01 WS-TEXT PIC X(10).\n", data)
    if data:
        source = (
            """IDENTIFICATION DIVISION.
PROGRAM-ID. TESTPROG.
DATA DIVISION.
WORKING-STORAGE SECTION.
"""
            + data
            + """
PROCEDURE DIVISION.
MAIN.
"""
        )
    return parse_program(source + body)


def main_statements(body: str, data: str = "") -> list[object]:
    parsed = program(body, data)
    assert parsed.paragraphs
    return list(parsed.paragraphs[0].statements)


def test_program_id_and_paragraphs() -> None:
    body = "    DISPLAY 'X'.\n" + "SECOND.\n    STOP RUN.\n"
    parsed = program(body)
    assert parsed.program_id == "TESTPROG"
    assert [paragraph.name for paragraph in parsed.paragraphs] == ["MAIN", "SECOND"]


def test_data_hierarchy_and_88_levels() -> None:
    data = """01 WS-GROUP.
   05 WS-INNER PIC 9(2) VALUE 1.
      88 WS-SMALL VALUE 0 THRU 5.
"""
    parsed = program("    STOP RUN.\n", data)
    group = parsed.data_roots[0]
    assert group.name == "WS-GROUP"
    assert group.children[0].name == "WS-INNER"
    assert group.children[0].conditions[0].name == "WS-SMALL"


def test_move_multiple_targets() -> None:
    statements = main_statements("    MOVE WS-A TO WS-B WS-TEXT.\n    STOP RUN.\n")
    move = statements[0]
    assert isinstance(move, Move)
    assert move.targets == ("WS-B", "WS-TEXT")


def test_arithmetic_forms() -> None:
    statements = main_statements(
        "    ADD WS-A WS-B GIVING WS-TEXT.\n"
        "    SUBTRACT WS-B FROM WS-A.\n"
        "    MULTIPLY WS-A BY WS-B.\n"
        "    DIVIDE WS-A BY WS-B.\n"
        "    DIVIDE WS-A INTO WS-B.\n"
        "    STOP RUN.\n"
    )
    add = statements[0]
    assert isinstance(add, Arithmetic) and add.statement == "ADD" and add.giving
    subtract = statements[1]
    assert isinstance(subtract, Arithmetic) and subtract.targets == ("WS-A",)
    multiply = statements[2]
    assert isinstance(multiply, Arithmetic) and multiply.targets == ("WS-B",)
    divide_by = statements[3]
    assert isinstance(divide_by, Arithmetic) and divide_by.operands[1].name == "WS-B"
    divide_into = statements[4]
    assert isinstance(divide_into, Arithmetic) and divide_into.operands[0].name == "WS-B"


def test_compute_with_rounded_before_and_after() -> None:
    statements = main_statements(
        "    COMPUTE WS-A ROUNDED = WS-B / 3.\n    COMPUTE WS-A = WS-B / 3 ROUNDED.\n    STOP RUN.\n"
    )
    first = statements[0]
    second = statements[1]
    assert isinstance(first, Compute) and first.rounded
    assert isinstance(second, Compute) and second.rounded


def test_compute_expression_precedence() -> None:
    statements = main_statements("    COMPUTE WS-A = 1 + 2 * 3.\n    STOP RUN.\n")
    compute = statements[0]
    assert isinstance(compute, Compute)
    assert compute.expression.operator == "+"
    assert compute.expression.right.operator == "*"


def test_if_else_end_if() -> None:
    statements = main_statements(
        "    IF WS-A = 1\n        MOVE 1 TO WS-B\n    ELSE\n        MOVE 2 TO WS-B\n    END-IF.\n    STOP RUN.\n"
    )
    statement = statements[0]
    assert isinstance(statement, If)
    assert isinstance(statement.condition, Relation)
    assert len(statement.then_body) == 1 and len(statement.else_body) == 1


def test_condition_names_and_logic() -> None:
    data = """01 WS-A PIC 9(3) VALUE 1.
    88 SMALL VALUE 0 THRU 9.
"""
    statements = main_statements(
        "    IF SMALL AND NOT SMALL\n        DISPLAY 'X'\n    END-IF.\n    STOP RUN.\n",
        data,
    )
    statement = statements[0]
    assert isinstance(statement, If)
    assert statement.condition.operator == "AND"
    assert isinstance(statement.condition.left, ConditionName)


def test_perform_variants() -> None:
    body = """    PERFORM PARA-ONE.
    PERFORM PARA-ONE 3 TIMES.
    PERFORM PARA-ONE UNTIL WS-A > 5.
    PERFORM PARA-ONE VARYING WS-A FROM 1 BY 1 UNTIL WS-A > 3.
    PERFORM 2 TIMES
        DISPLAY 'X'
    END-PERFORM.
    PERFORM UNTIL WS-A = 0
        SUBTRACT 1 FROM WS-A
    END-PERFORM.
    STOP RUN.
PARA-ONE.
    ADD 1 TO WS-A.
"""
    statements = main_statements(body)
    first = statements[0]
    assert isinstance(first, Perform) and first.paragraph == "PARA-ONE"
    second = statements[1]
    assert isinstance(second, Perform) and second.times is not None
    third = statements[2]
    assert isinstance(third, Perform) and third.until is not None
    fourth = statements[3]
    assert isinstance(fourth, Perform) and fourth.varying is not None
    inline = statements[4]
    assert isinstance(inline, Perform) and inline.paragraph is None and inline.times is not None


def test_perform_thru() -> None:
    body = """    PERFORM A THRU B.
    STOP RUN.
A.
    DISPLAY 'A'.
B.
    DISPLAY 'B'.
"""
    statements = main_statements(body)
    first = statements[0]
    assert isinstance(first, Perform) and first.thru == "B"


def test_go_to_and_stop_run() -> None:
    statements = main_statements("    GO TO MAIN.\n    STOP RUN.\n")
    assert isinstance(statements[0], GoTo) and statements[0].targets == ("MAIN",)
    assert isinstance(statements[1], StopRun)


def test_display_accept_string_unstring_inspect() -> None:
    statements = main_statements(
        "    DISPLAY 'A' WS-A.\n"
        "    ACCEPT WS-TEXT.\n"
        "    STRING WS-TEXT DELIMITED BY SIZE '!' DELIMITED BY SIZE INTO WS-TEXT.\n"
        "    UNSTRING WS-TEXT DELIMITED BY ',' INTO WS-TEXT.\n"
        "    INSPECT WS-TEXT TALLYING WS-A FOR ALL 'A'.\n"
        "    INSPECT WS-TEXT REPLACING ALL 'A' BY 'B'.\n"
        "    STOP RUN.\n"
    )
    assert isinstance(statements[0], Display) and len(statements[0].items) == 2
    assert isinstance(statements[1], Accept)
    assert isinstance(statements[2], StringStatement) and len(statements[2].parts) == 2
    assert isinstance(statements[3], Unstring) and statements[3].delimiter is not None
    assert isinstance(statements[4], InspectTallying)
    assert isinstance(statements[5], InspectReplacing)


def test_missing_divisions() -> None:
    with pytest.raises(ParseError):
        parse_program("DISPLAY 'X'.")
    with pytest.raises(ParseError):
        parse_program("IDENTIFICATION DIVISION.\nPROCEDURE DIVISION.\nMAIN.\nSTOP RUN.\n")


def test_missing_program_id() -> None:
    source = "IDENTIFICATION DIVISION.\nDATA DIVISION.\nPROCEDURE DIVISION.\nMAIN.\nSTOP RUN.\n"
    with pytest.raises(ParseError) as caught:
        parse_program(source)
    assert "PROGRAM-ID" in caught.value.message


def test_call_is_rejected() -> None:
    with pytest.raises(ParseError) as caught:
        main_statements("    CALL 'OTHER'.\n    STOP RUN.\n")
    assert "CALL" in caught.value.message


def test_unsupported_data_clauses() -> None:
    for clause in ["USAGE COMP-3", "OCCURS 3 TIMES", "JUSTIFIED RIGHT", "BLANK WHEN ZERO"]:
        data = f"01 WS-A PIC 9(3) {clause}.\n"
        with pytest.raises(ParseError):
            program("    STOP RUN.\n", data)


def test_unterminated_data_entry() -> None:
    data = "01 WS-A PIC 9(3)\n"
    with pytest.raises(ParseError):
        program("    STOP RUN.\n", data)


def test_unknown_statement() -> None:
    with pytest.raises(ParseError) as caught:
        main_statements("    FROBNICATE 5.\n    STOP RUN.\n")
    assert "unsupported statement" in caught.value.message


def test_else_without_if() -> None:
    with pytest.raises(ParseError):
        main_statements("    ELSE.\n    STOP RUN.\n")


def test_deep_if_nesting_is_bounded() -> None:
    body = "    IF WS-A = 1\n" * 150 + "        MOVE 1 TO WS-B\n" + "    END-IF\n" * 150 + "    .\n"
    with pytest.raises(ParseError) as caught:
        main_statements(body)
    assert "nest" in caught.value.message


def test_deep_parentheses_are_bounded() -> None:
    with pytest.raises(ParseError):
        main_statements("    COMPUTE WS-A = " + "(" * 150 + "1" + ")" * 150 + ".\n    STOP RUN.\n")


def test_numeric_literal_digit_cap() -> None:
    with pytest.raises(ParseError) as caught:
        main_statements("    MOVE " + "9" * 120 + " TO WS-A.\n    STOP RUN.\n")
    assert "digits" in caught.value.message


def test_division_by_zero_is_a_runtime_error_not_parse_error() -> None:
    statements = main_statements("    COMPUTE WS-A = 1 / 0.\n    STOP RUN.\n")
    compute = statements[0]
    assert isinstance(compute, Compute)
    assert compute.expression.right.value == Decimal(0)
