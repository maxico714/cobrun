from __future__ import annotations

from decimal import Decimal

import pytest

from cobrun.data import Field, Picture, Storage, format_decimal, parse_picture
from cobrun.errors import ParseError, RunError


def test_numeric_pictures() -> None:
    assert parse_picture("9(3)") == Picture("numeric", 3, 3, 0, False)
    assert parse_picture("999") == Picture("numeric", 3, 3, 0, False)
    assert parse_picture("S9(5)V9(2)") == Picture("numeric", 8, 7, 2, True)
    assert parse_picture("9V99") == Picture("numeric", 3, 3, 2, False)
    assert parse_picture("v99") == Picture("numeric", 2, 2, 2, False)


def test_alphanumeric_pictures() -> None:
    assert parse_picture("X(10)") == Picture("alnum", 10)
    assert parse_picture("X") == Picture("alnum", 1)


def test_picture_rejects_unsupported_clauses() -> None:
    for text in ["9(3)V9(2) COMP-3", "ZZZ", "$9,999", "9(0)", "9(3", "X9", "SX(3)", "", "S(V9"]:
        with pytest.raises(ParseError):
            parse_picture(text)


def test_picture_rejects_huge_lengths() -> None:
    with pytest.raises(ParseError):
        parse_picture("X(40000)")


def test_numeric_rendering_pads_and_keeps_the_sign() -> None:
    assert parse_picture("9(3)").render(Decimal(42)) == "042"
    assert parse_picture("S9(2)").render(Decimal(-5)) == "-05"
    assert parse_picture("9V99").render(Decimal("1.5")) == "150"


def test_numeric_rendering_truncates_fraction() -> None:
    assert parse_picture("9V9").render(Decimal("1.29")) == "12"


def test_numeric_rendering_beyond_default_decimal_precision() -> None:
    assert parse_picture("9(30)").render(Decimal("123456789012345678901234567890")) == (
        "123456789012345678901234567890"
    )
    assert parse_picture("9V9(28)").render(Decimal("1.5")) == "1" + "5" + "0" * 27
    assert len(parse_picture("9V9(5000)").render(Decimal("1.5"))) == 5001


def test_scale_value_quantizes_without_rounding() -> None:
    assert format_decimal(Decimal("2.50")) == "2.5"
    assert format_decimal(Decimal("0.00")) == "0"
    assert format_decimal(Decimal("-0.25")) == "-0.25"


def test_storage_initial_values() -> None:
    roots = [
        Field("WS-N", 1, parse_picture("9(3)"), Decimal(7)),
        Field("WS-X", 1, parse_picture("X(4)"), "AB"),
        Field("WS-EMPTY", 1, parse_picture("9(2)"), None),
        Field("WS-TEXT", 1, parse_picture("X(2)"), None),
    ]
    storage = Storage(roots)
    assert storage.read("WS-N") == Decimal(7)
    assert storage.text("WS-N") == "007"
    assert storage.text("WS-X") == "AB  "
    assert storage.read("WS-EMPTY") == Decimal(0)
    assert storage.read("WS-TEXT") == ""


def test_storage_duplicate_names_rejected() -> None:
    roots = [Field("A", 1, parse_picture("9")), Field("A", 1, parse_picture("9"))]
    with pytest.raises(ParseError) as caught:
        Storage(roots)
    assert "duplicate" in caught.value.message


def test_group_rendering_concatenates_children() -> None:
    child_a = Field("A", 5, parse_picture("X(2)"), "AB")
    child_b = Field("B", 5, parse_picture("9(2)"), Decimal(3))
    group = Field("G", 1, None, None, [child_a, child_b])
    storage = Storage([group])
    assert storage.text("G") == "AB03"
    assert group.length == 4


def test_empty_group_renders_as_empty_text() -> None:
    group = Field("G", 1, None, None, [])
    storage = Storage([group])
    assert storage.read("G") == ""
    assert storage.display_value("G") == ""


def test_condition_names_are_collected() -> None:
    from cobrun.data import Condition

    parent = Field("SCORE", 1, parse_picture("9(3)"), Decimal(85))
    parent.conditions.append(Condition("PASSED", [(Decimal(50), Decimal(100))]))
    storage = Storage([parent])
    field, condition = storage.condition_value("PASSED")
    assert field.name == "SCORE"
    assert condition.values == [(Decimal(50), Decimal(100))]


def test_unknown_field_raises() -> None:
    storage = Storage([])
    with pytest.raises(RunError):
        storage.field("MISSING")
    with pytest.raises(RunError):
        storage.condition_value("MISSING")
