"""DATA DIVISION model: PICTURE clauses, fields, storage and 88 condition names."""

from __future__ import annotations

import re
from dataclasses import dataclass
from dataclasses import field as dc_field
from decimal import ROUND_DOWN, Decimal

from .errors import ParseError, RunError

MAX_FIELD_LENGTH = 32_767
MAX_FIELDS = 5_000

_PIC_TOKEN = re.compile(r"^(?:S)?(?:[9X]|9\(\d+\)|X\(\d+\)|V|S)+$")


@dataclass(frozen=True)
class Picture:
    kind: str  # "numeric" | "alnum"
    length: int
    digits: int = 0
    scale: int = 0
    signed: bool = False

    def render(self, value: Decimal) -> str:
        """Render a numeric value as the stored character form (no decimal point)."""
        scaled = _scale_value(value, self.scale)
        sign = "-" if scaled < 0 else ""
        digits = str(int(abs(scaled) * (Decimal(10) ** self.scale)))
        digits = digits.rjust(self.digits, "0")
        if len(digits) > self.digits:
            digits = digits[-self.digits :]
        if self.signed:
            return sign + digits
        return digits


@dataclass
class Condition:
    name: str
    values: list[tuple[object, object | None]]


@dataclass
class Field:
    name: str
    level: int
    picture: Picture | None = None
    value: object | None = None
    children: list[Field] = dc_field(default_factory=list)
    conditions: list[Condition] = dc_field(default_factory=list)
    line: int = 0

    @property
    def is_group(self) -> bool:
        return self.picture is None and bool(self.children)

    @property
    def length(self) -> int:
        if self.picture is not None:
            return self.picture.length
        return sum(child.length for child in self.children)

    def elementary_fields(self) -> list[Field]:
        if not self.is_group:
            return [self]
        result: list[Field] = []
        for child in self.children:
            result.extend(child.elementary_fields())
        return result


def parse_picture(text: str) -> Picture:
    normalized = text.upper().replace(" ", "")
    if not normalized:
        raise ParseError("empty PICTURE clause")
    if not _PIC_TOKEN.match(normalized):
        raise ParseError(f"unsupported PICTURE clause '{text}' (v0.1 supports S, 9, X, V and repeats)")
    signed = normalized.startswith("S")
    body = normalized[1:] if signed else normalized
    if "X" in body:
        if signed or "V" in body or "9" in body:
            raise ParseError(f"mixed alphanumeric PICTURE '{text}' is not supported")
        length = _repeat_count(body, "X")
        return Picture("alnum", length)
    digits, scale = _numeric_shape(body)
    if digits == 0:
        raise ParseError(f"PICTURE '{text}' has no digits")
    if digits > MAX_FIELD_LENGTH:
        raise ParseError(f"PICTURE '{text}' exceeds {MAX_FIELD_LENGTH} characters")
    return Picture("numeric", digits + (1 if signed else 0), digits, scale, signed)


def _repeat_count(body: str, char: str) -> int:
    total = 0
    index = 0
    while index < len(body):
        current = body[index]
        if current != char:
            raise ParseError(f"unsupported PICTURE clause near '{body[index:]}'")
        if index + 1 < len(body) and body[index + 1] == "(":
            end = body.find(")", index)
            if end < 0:
                raise ParseError("unclosed repeat in PICTURE clause")
            count = body[index + 2 : end]
            if not count.isdigit() or int(count) == 0:
                raise ParseError("PICTURE repeat must be a positive integer")
            total += int(count)
            index = end + 1
        else:
            total += 1
            index += 1
    if total > MAX_FIELD_LENGTH:
        raise ParseError(f"PICTURE length exceeds {MAX_FIELD_LENGTH}")
    return total


def _numeric_shape(body: str) -> tuple[int, int]:
    integer_digits = 0
    fraction_digits = 0
    after_point = False
    index = 0
    while index < len(body):
        char = body[index]
        if char == "V":
            if after_point:
                raise ParseError("PICTURE clause has more than one 'V'")
            after_point = True
            index += 1
            continue
        if char != "9":
            raise ParseError(f"unsupported PICTURE clause near '{body[index:]}'")
        count = 1
        if index + 1 < len(body) and body[index + 1] == "(":
            end = body.find(")", index)
            if end < 0:
                raise ParseError("unclosed repeat in PICTURE clause")
            text = body[index + 2 : end]
            if not text.isdigit() or int(text) == 0:
                raise ParseError("PICTURE repeat must be a positive integer")
            count = int(text)
            index = end + 1
        else:
            index += 1
        if after_point:
            fraction_digits += count
        else:
            integer_digits += count
    return integer_digits + fraction_digits, fraction_digits


def _scale_value(value: Decimal, scale: int) -> Decimal:
    quant = Decimal(1).scaleb(-scale)
    return value.quantize(quant, rounding=ROUND_DOWN)


class Storage:
    """Flat view over a field hierarchy with COBOL-style read/write helpers."""

    def __init__(self, roots: list[Field]) -> None:
        self.roots = roots
        self.fields: dict[str, Field] = {}
        self.all_fields: dict[str, Field] = {}
        for root in roots:
            self._register(root)
        self.values: dict[str, object] = {}
        for field in self.fields.values():
            self.values[field.name] = self._initial(field)
        self.conditions: dict[str, tuple[Field, Condition]] = {}
        for root in roots:
            self._collect_conditions(root)

    def _register(self, node: Field) -> None:
        if node.name in self.all_fields:
            raise ParseError(f"duplicate data name '{node.name}'")
        self.all_fields[node.name] = node
        if not node.is_group:
            self.fields[node.name] = node
        if len(self.all_fields) > MAX_FIELDS:
            raise ParseError(f"more than {MAX_FIELDS} fields")
        for child in node.children:
            self._register(child)

    def _collect_conditions(self, node: Field) -> None:
        for condition in node.conditions:
            self.conditions[condition.name] = (node, condition)
        for child in node.children:
            self._collect_conditions(child)

    def _initial(self, field: Field) -> object:
        if field.value is None:
            return Decimal(0) if field.picture is not None and field.picture.kind == "numeric" else ""
        if field.picture is None:
            return field.value
        return coerce_literal(field.value, field.picture)

    def field(self, name: str) -> Field:
        try:
            return self.all_fields[name]
        except KeyError as error:
            raise RunError(f"unknown data name '{name}'") from error

    def read(self, name: str) -> object:
        field = self.field(name)
        if field.is_group:
            return self.render(field)
        return self.values[field.name]

    def write(self, name: str, value: object) -> None:
        field = self.field(name)
        if field.picture is not None and field.picture.kind == "numeric":
            if not isinstance(value, Decimal):
                raise RunError(f"'{name}' requires a numeric value")
            self.values[name] = value
            return
        self.values[name] = str(value)

    def text(self, name: str) -> str:
        field = self.field(name)
        return self.render(field)

    def render(self, field: Field) -> str:
        if field.is_group:
            return "".join(self.render(child) for child in field.children)
        value = self.values[field.name]
        picture = field.picture
        assert picture is not None
        if picture.kind == "numeric":
            assert isinstance(value, Decimal)
            return picture.render(value)
        text = str(value)
        return text[: picture.length].ljust(picture.length)

    def display_value(self, name: str) -> str:
        """Value as DISPLAY would show it: numeric fields with sign and decimal point."""
        field = self.field(name)
        value = self.values[name]
        if field.picture is not None and field.picture.kind == "numeric":
            assert isinstance(value, Decimal)
            return format_decimal(value)
        return self.text(name).rstrip()

    def condition_value(self, name: str) -> tuple[Field, Condition]:
        try:
            return self.conditions[name]
        except KeyError as error:
            raise RunError(f"unknown condition name '{name}'") from error


def coerce_literal(value: object, picture: Picture) -> object:
    if picture.kind == "numeric":
        if isinstance(value, Decimal):
            return value
        if isinstance(value, int):
            return Decimal(value)
        raise ParseError("numeric field requires a numeric VALUE")
    return str(value)


def format_decimal(value: Decimal) -> str:
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"
