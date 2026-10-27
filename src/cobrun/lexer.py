"""COBOL source reader and tokenizer (fixed and free format).

Bounded: source lines, token count and token length are capped. Comments, sequence
numbers and the indicator column are handled here; continuation lines are rejected
explicitly rather than misparsed.
"""

from __future__ import annotations

from dataclasses import dataclass

from .errors import ParseError

MAX_SOURCE_LINES = 20_000
MAX_TOKENS = 200_000
MAX_TOKEN_CHARS = 4_096

PIC_CHARS = set("9XSVPA()")


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Token({self.kind}, {self.value!r}, line={self.line})"


def read_source(text: str) -> list[tuple[int, str]]:
    """Return (line number, code) pairs with comments and sequence areas removed."""
    if not isinstance(text, str):
        raise ParseError("source must be text")
    raw_lines = text.splitlines()
    if len(raw_lines) > MAX_SOURCE_LINES:
        raise ParseError(f"source has more than {MAX_SOURCE_LINES} lines")
    fixed = _looks_fixed(raw_lines)
    code_lines: list[tuple[int, str]] = []
    for number, raw in enumerate(raw_lines, start=1):
        line = raw.rstrip("\r\n")
        if fixed:
            if len(line) > 6 and line[6] in {"-"}:
                raise ParseError("continuation lines are not supported in v0.1", line=number)
            indicator = line[6] if len(line) > 6 else " "
            if indicator in {"*", "/"} or (indicator == "D"):
                continue
            code = line[7:72] if len(line) > 7 else ""
        else:
            stripped = line.strip()
            if stripped.startswith("*>"):
                continue
            code = line
        code_lines.append((number, code))
    return code_lines


def _looks_fixed(lines: list[str]) -> bool:
    for raw in lines:
        if len(raw) <= 6:
            continue
        prefix = raw[:6]
        if prefix.strip() and not prefix.strip().isdigit():
            return False
        if raw[6] in {"*", "/", "-", "D"}:
            return True
    return False


def tokenize(text: str) -> list[Token]:
    tokens: list[Token] = []
    for line_number, code in read_source(text):
        index = 0
        length = len(code)
        while index < length:
            char = code[index]
            if char in " \t":
                index += 1
                continue
            if char == "*" and index + 1 < length and code[index + 1] == ">":
                break
            if char == '"':
                value, index = _read_string(code, index, line_number, quote='"')
                _append(tokens, Token("STRING", value, line_number))
                continue
            if char == "'":
                value, index = _read_string(code, index, line_number, quote="'")
                _append(tokens, Token("STRING", value, line_number))
                continue
            if char.isdigit() or (char == "." and index + 1 < length and code[index + 1].isdigit()):
                start = index
                while index < length and (code[index].isdigit() or code[index] == "."):
                    index += 1
                literal = code[start:index].rstrip(".")
                trailing = index - start - len(literal)
                _append(tokens, Token("NUMBER", literal, line_number))
                for _ in range(trailing):
                    _append(tokens, Token("PERIOD", ".", line_number))
                continue
            if char.isalpha():
                start = index
                while index < length and (code[index].isalnum() or code[index] in "-_"):
                    index += 1
                word = code[start:index].upper()
                _append(tokens, Token("WORD", word, line_number))
                continue
            if char == ".":
                _append(tokens, Token("PERIOD", ".", line_number))
                index += 1
                continue
            if char == ",":
                _append(tokens, Token("COMMA", ",", line_number))
                index += 1
                continue
            if char in "()":
                _append(tokens, Token("LPAREN" if char == "(" else "RPAREN", char, line_number))
                index += 1
                continue
            two = code[index : index + 2]
            if two in {"<=", ">="}:
                _append(tokens, Token("OP", two, line_number))
                index += 2
                continue
            if char in "<>=":
                _append(tokens, Token("OP", char, line_number))
                index += 1
                continue
            if char in "+-*/":
                _append(tokens, Token("OP", char, line_number))
                index += 1
                continue
            raise ParseError(f"unexpected character {char!r}", line=line_number)
    tokens.append(Token("EOF", "", tokens[-1].line if tokens else 0))
    return tokens


def _append(tokens: list[Token], token: Token) -> None:
    if len(token.value) > MAX_TOKEN_CHARS:
        raise ParseError(f"token longer than {MAX_TOKEN_CHARS} characters", line=token.line)
    tokens.append(token)
    if len(tokens) > MAX_TOKENS:
        raise ParseError(f"source has more than {MAX_TOKENS} tokens", line=token.line)


def _read_string(code: str, index: int, line: int, *, quote: str) -> tuple[str, int]:
    index += 1
    pieces: list[str] = []
    while index < len(code):
        char = code[index]
        if char == quote:
            if index + 1 < len(code) and code[index + 1] == quote:
                pieces.append(quote)
                index += 2
                continue
            return "".join(pieces), index + 1
        pieces.append(char)
        index += 1
    raise ParseError("unterminated string literal", line=line)
