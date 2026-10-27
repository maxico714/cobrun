from __future__ import annotations

import pytest

from cobrun.errors import ParseError
from cobrun.lexer import MAX_TOKENS, read_source, tokenize


def words(text: str) -> list[str]:
    return [token.value for token in tokenize(text) if token.kind == "WORD"]


def kinds(text: str) -> list[tuple[str, str]]:
    return [(token.kind, token.value) for token in tokenize(text) if token.kind != "EOF"]


def test_free_format_words_are_uppercased() -> None:
    assert words("move ws-count to total.") == ["MOVE", "WS-COUNT", "TO", "TOTAL"]


def test_period_is_its_own_token() -> None:
    assert kinds("STOP RUN.") == [("WORD", "STOP"), ("WORD", "RUN"), ("PERIOD", ".")]


def test_number_followed_by_period() -> None:
    assert kinds("VALUE 0.") == [("WORD", "VALUE"), ("NUMBER", "0"), ("PERIOD", ".")]


def test_decimal_literal() -> None:
    assert kinds("MOVE 2.25 TO X.") == [
        ("WORD", "MOVE"),
        ("NUMBER", "2.25"),
        ("WORD", "TO"),
        ("WORD", "X"),
        ("PERIOD", "."),
    ]


def test_signed_literal_is_operator_plus_number() -> None:
    assert kinds("MOVE -2.5 TO X.") == [
        ("WORD", "MOVE"),
        ("OP", "-"),
        ("NUMBER", "2.5"),
        ("WORD", "TO"),
        ("WORD", "X"),
        ("PERIOD", "."),
    ]


def test_comparison_operators() -> None:
    assert kinds("= < > <= >=") == [("OP", "="), ("OP", "<"), ("OP", ">"), ("OP", "<="), ("OP", ">=")]


def test_string_literals_with_doubled_quotes() -> None:
    assert kinds("DISPLAY 'it''s'.") == [
        ("WORD", "DISPLAY"),
        ("STRING", "it's"),
        ("PERIOD", "."),
    ]
    assert kinds('DISPLAY "a""b".')[1] == ("STRING", 'a"b')


def test_picture_clause_tokens_are_reassembled_by_the_parser() -> None:
    assert kinds("PIC 9(3)V99.") == [
        ("WORD", "PIC"),
        ("NUMBER", "9"),
        ("LPAREN", "("),
        ("NUMBER", "3"),
        ("RPAREN", ")"),
        ("WORD", "V99"),
        ("PERIOD", "."),
    ]


def test_inline_comment_is_skipped() -> None:
    assert words("DISPLAY 'X'. *> a note") == ["DISPLAY"]


def test_comment_line_star_chevron() -> None:
    source = "*> whole line comment\nDISPLAY 'X'."
    assert words(source) == ["DISPLAY"]


def test_fixed_format_strips_sequence_and_indicator() -> None:
    source = "000100 IDENTIFICATION DIVISION.\n000200*COMMENT LINE\n000300     DISPLAY 'X'.\n"
    assert words(source) == ["IDENTIFICATION", "DIVISION", "DISPLAY"]


def test_fixed_format_continuation_is_rejected() -> None:
    source = "000100 DISPLAY 'ABCDEF'\n000200-    'GHI'.\n"
    with pytest.raises(ParseError) as caught:
        tokenize(source)
    assert "continuation" in caught.value.message


def test_free_format_keeps_hyphenated_names() -> None:
    assert "WS-TOTAL" in words("MOVE WS-TOTAL TO OUT.")


def test_unterminated_string() -> None:
    with pytest.raises(ParseError) as caught:
        tokenize("DISPLAY 'oops.")
    assert "unterminated" in caught.value.message
    assert caught.value.line == 1


def test_unexpected_character() -> None:
    with pytest.raises(ParseError) as caught:
        tokenize("MOVE $ TO X.")
    assert "unexpected character" in caught.value.message


def test_token_cap() -> None:
    with pytest.raises(ParseError):
        tokenize("A " * (MAX_TOKENS + 5))


def test_read_source_caps_lines() -> None:
    with pytest.raises(ParseError):
        read_source("\n" * 20_001)


def test_token_length_cap() -> None:
    with pytest.raises(ParseError) as caught:
        tokenize("A" * 5_000 + ".")
    assert "token longer" in caught.value.message


def test_token_line_numbers() -> None:
    tokens = tokenize("DISPLAY 'A'.\nDISPLAY 'B'.")
    assert tokens[0].line == 1
    assert tokens[3].line == 2
