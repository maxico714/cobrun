"""AST nodes for the COBOL subset."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True)
class NumberLiteral:
    value: Decimal


@dataclass(frozen=True)
class StringLiteral:
    value: str


@dataclass(frozen=True)
class Figurative:
    name: str  # ZERO / SPACE / HIGH-VALUE / LOW-VALUE / QUOTE


@dataclass(frozen=True)
class Identifier:
    name: str


Operand = NumberLiteral | StringLiteral | Figurative | Identifier


# -- expressions (COMPUTE, arithmetic operands) ---------------------------
@dataclass(frozen=True)
class BinaryOp:
    operator: str
    left: Expression
    right: Expression


@dataclass(frozen=True)
class Negate:
    operand: Expression


Expression = NumberLiteral | Identifier | BinaryOp | Negate


# -- conditions ------------------------------------------------------------
@dataclass(frozen=True)
class Relation:
    left: Operand
    operator: str
    right: Operand


@dataclass(frozen=True)
class ConditionName:
    name: str


@dataclass(frozen=True)
class NotCondition:
    condition: Condition


@dataclass(frozen=True)
class LogicalCondition:
    operator: str  # AND / OR
    left: Condition
    right: Condition


Condition = Relation | ConditionName | NotCondition | LogicalCondition


# -- statements ------------------------------------------------------------
@dataclass(frozen=True)
class Move:
    source: Operand
    targets: tuple[str, ...]
    line: int = 0


@dataclass(frozen=True)
class Arithmetic:
    statement: str  # ADD / SUBTRACT / MULTIPLY / DIVIDE
    operands: tuple[Expression, ...]
    targets: tuple[str, ...]
    giving: bool
    rounded: bool
    on_size_error: tuple[Statement, ...]
    line: int = 0


@dataclass(frozen=True)
class Compute:
    target: str
    expression: Expression
    rounded: bool
    on_size_error: tuple[Statement, ...]
    line: int = 0


@dataclass(frozen=True)
class If:
    condition: Condition
    then_body: tuple[Statement, ...]
    else_body: tuple[Statement, ...]
    line: int = 0


@dataclass(frozen=True)
class Perform:
    paragraph: str | None
    thru: str | None
    times: Expression | None
    until: Condition | None
    varying: tuple[str, Expression, Expression, Condition] | None
    body: tuple[Statement, ...]
    line: int = 0


@dataclass(frozen=True)
class GoTo:
    targets: tuple[str, ...]
    line: int = 0


@dataclass(frozen=True)
class StopRun:
    line: int = 0


@dataclass(frozen=True)
class Display:
    items: tuple[Operand, ...]
    line: int = 0


@dataclass(frozen=True)
class Accept:
    target: str
    line: int = 0


@dataclass(frozen=True)
class StringStatement:
    parts: tuple[tuple[Operand, bool], ...]  # (operand, literal?)
    target: str
    line: int = 0


@dataclass(frozen=True)
class Unstring:
    source: Operand
    delimiter: StringLiteral | None
    targets: tuple[str, ...]
    line: int = 0


@dataclass(frozen=True)
class InspectTallying:
    source: Operand
    target: str
    pattern: StringLiteral
    line: int = 0


@dataclass(frozen=True)
class InspectReplacing:
    source: Operand
    old: StringLiteral
    new: StringLiteral
    line: int = 0


@dataclass(frozen=True)
class Continue:
    line: int = 0


Statement = (
    Move
    | Arithmetic
    | Compute
    | If
    | Perform
    | GoTo
    | StopRun
    | Display
    | Accept
    | StringStatement
    | Unstring
    | InspectTallying
    | InspectReplacing
    | Continue
)


@dataclass
class Paragraph:
    name: str
    statements: list[Statement] = field(default_factory=list)


@dataclass
class Program:
    program_id: str
    data_roots: list[object]
    paragraphs: list[Paragraph]
