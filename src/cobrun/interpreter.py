"""Interpreter for the COBOL subset: arithmetic, control flow and output."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, DecimalException, localcontext
from typing import TextIO

from .data import MAX_FIELD_LENGTH, Field, Picture, Storage, format_decimal
from .errors import RunError, StepLimitError
from .parser import parse_program
from .statements import (
    Accept,
    Arithmetic,
    BinaryOp,
    Compute,
    ConditionName,
    Continue,
    Display,
    Expression,
    Figurative,
    GoTo,
    Identifier,
    If,
    InspectReplacing,
    InspectTallying,
    LogicalCondition,
    Move,
    Negate,
    NotCondition,
    NumberLiteral,
    Operand,
    Paragraph,
    Perform,
    Program,
    Relation,
    Statement,
    StopRun,
    StringLiteral,
    StringStatement,
    Unstring,
)
from .statements import (
    Condition as ConditionType,
)

DEFAULT_STEP_LIMIT = 100_000
DEFAULT_SCALE = 18


class Interpreter:
    def __init__(
        self,
        program: Program,
        *,
        output: Callable[[str], None] | None = None,
        accept_source: Iterable[str] | None = None,
        step_limit: int = DEFAULT_STEP_LIMIT,
    ) -> None:
        self.program = program
        self.storage = Storage(program.data_roots)  # type: ignore[arg-type]
        self.output = output or (lambda text: None)
        self._accept = iter(accept_source or [])
        self.step_limit = step_limit
        self.steps = 0
        self.loop_iterations = 0
        self.decimal_ops = 0
        self.rounding_ops = 0
        self.stopped = False
        self.paragraphs: dict[str, int] = {}
        for index, paragraph in enumerate(program.paragraphs):
            if paragraph.name:
                self.paragraphs.setdefault(paragraph.name, index)

    # -- public ------------------------------------------------------------
    def run(self) -> None:
        index = self.paragraphs.get("MAIN", 0)
        try:
            while index < len(self.program.paragraphs) and not self.stopped:
                paragraph = self.program.paragraphs[index]
                next_index = self.execute_paragraph(paragraph)
                index = next_index if next_index is not None else index + 1
        except RecursionError as error:
            raise StepLimitError(f"program exceeded {self.step_limit} statements (runaway recursion)") from error
        if self.steps > self.step_limit:
            raise StepLimitError(f"program exceeded {self.step_limit} statements", statement="STEP LIMIT")

    def report(self) -> dict[str, object]:
        return {
            "program": self.program.program_id,
            "statements_executed": self.steps,
            "decimal_ops": self.decimal_ops,
            "rounding_ops": self.rounding_ops,
            "stopped": self.stopped,
        }

    def execute_paragraph(self, paragraph: Paragraph) -> int | None:
        return self.execute_statements(paragraph.statements)

    def execute_statements(self, statements: Iterable[Statement]) -> int | None:
        for statement in statements:
            if self.stopped:
                return None
            target = self.execute(statement)
            if target is not None:
                return target
        return None

    def execute(self, statement: Statement) -> int | None:
        self.steps += 1
        if self.steps > self.step_limit:
            raise StepLimitError(f"program exceeded {self.step_limit} statements")
        if isinstance(statement, Move):
            self.do_move(statement)
            return None
        if isinstance(statement, Arithmetic):
            self.do_arithmetic(statement)
            return None
        if isinstance(statement, Compute):
            self.do_compute(statement)
            return None
        if isinstance(statement, If):
            condition = self.evaluate_condition(statement.condition)
            body = statement.then_body if condition else statement.else_body
            return self.execute_statements(body)
        if isinstance(statement, Perform):
            return self.do_perform(statement)
        if isinstance(statement, GoTo):
            if len(statement.targets) != 1:
                raise RunError("GO TO with multiple targets needs DEPENDING ON, not supported", statement="GO TO")
            target = statement.targets[0]
            if target not in self.paragraphs:
                raise RunError(f"unknown paragraph '{target}'", statement="GO TO")
            return self.paragraphs[target]
        if isinstance(statement, StopRun):
            self.stopped = True
            return None
        if isinstance(statement, Display):
            self.output("".join(self.display_item(item) for item in statement.items))
            return None
        if isinstance(statement, Accept):
            try:
                line = next(self._accept)
            except StopIteration:
                line = ""
            self.store_token(statement.target, line.rstrip("\r\n"))
            return None
        if isinstance(statement, StringStatement):
            text = "".join(self.operand_text(item) for item, _ in statement.parts)
            self.store_token(statement.target, text)
            return None
        if isinstance(statement, Unstring):
            text = self.operand_text(statement.source)
            delimiter = statement.delimiter.value if statement.delimiter else None
            if delimiter == "":
                raise RunError("UNSTRING delimiter must not be empty", statement="UNSTRING")
            pieces = text.split(delimiter) if delimiter is not None else [text]
            for name, piece in zip(statement.targets, pieces, strict=False):
                self.store_token(name, piece)
            return None
        if isinstance(statement, InspectTallying):
            text = self.operand_text(statement.source)
            pattern = statement.pattern.value
            count = text.count(pattern) if pattern else 0
            current = self.numeric_value(Identifier(statement.target))
            self.store_numeric(statement.target, current + Decimal(count), rounded=False, size_error=())
            return None
        if isinstance(statement, InspectReplacing):
            text = self.operand_text(statement.source)
            replaced = text.replace(statement.old.value, statement.new.value) if statement.old.value else text
            self.store_token(_name_of(statement.source), replaced)
            return None
        if isinstance(statement, Continue):
            return None
        raise RunError(f"unsupported statement {type(statement).__name__}")

    # -- statements --------------------------------------------------------
    def do_move(self, statement: Move) -> None:
        value = self.operand_value(statement.source)
        for target in statement.targets:
            field = self.storage.field(target)
            if field.is_group:
                self.move_to_group(field, self.operand_text(statement.source))
                continue
            if field.picture is not None and field.picture.kind == "numeric":
                if isinstance(value, Decimal):
                    self.store_numeric(target, value, rounded=False, size_error=())
                else:
                    self.store_numeric(target, self.parse_numeric_text(str(value)), rounded=False, size_error=())
            else:
                self.store_token(target, self.operand_text(statement.source))

    def move_to_group(self, group: Field, text: str) -> None:
        offset = 0
        for child in group.elementary_fields():
            chunk = text[offset : offset + child.length].ljust(child.length)
            offset += child.length
            self.store_token(child.name, chunk)

    def do_arithmetic(self, statement: Arithmetic) -> None:
        values = [self.numeric_value(operand) for operand in statement.operands]
        if statement.statement == "ADD" or statement.statement == "SUBTRACT":
            result = sum(values, Decimal(0))
        elif statement.statement == "MULTIPLY":
            result = values[0] * values[1] if len(values) > 1 else values[0]
        elif statement.statement == "DIVIDE":
            if len(values) != 2:
                raise RunError("DIVIDE needs two operands", statement="DIVIDE")
            if values[1] == 0:
                raise RunError("division by zero", statement="DIVIDE")
            result = values[0] / values[1]
        else:  # pragma: no cover - parser restricts this
            raise RunError(f"unsupported arithmetic '{statement.statement}'")
        self.decimal_ops += 1
        if statement.giving or statement.statement in {"MULTIPLY", "DIVIDE"}:
            self.store_all(statement.targets, result, statement.rounded, statement.on_size_error)
            return
        for target in statement.targets:
            base = self.numeric_value(Identifier(target))
            combined = base - result if statement.statement == "SUBTRACT" else base + result
            self.store_numeric(target, combined, rounded=statement.rounded, size_error=statement.on_size_error)

    def do_compute(self, statement: Compute) -> None:
        result = self.evaluate_expression(statement.expression)
        self.decimal_ops += 1
        self.store_numeric(statement.target, result, rounded=statement.rounded, size_error=statement.on_size_error)

    def do_perform(self, statement: Perform) -> int | None:
        if statement.paragraph is not None:
            names = self._paragraph_span(statement.paragraph, statement.thru)
            if statement.times is not None:
                count = self.numeric_value(statement.times)
                for _ in range(int(count)):
                    self.count_iteration()
                    self.execute_paragraphs(names)
            elif statement.until is not None:
                while not self.evaluate_condition(statement.until):
                    self.count_iteration()
                    self.execute_paragraphs(names)
            elif statement.varying is not None:
                name, start, step, until = statement.varying
                self.store_numeric(name, self.numeric_value(start), rounded=False, size_error=())
                while not self.evaluate_condition(until):
                    self.count_iteration()
                    self.execute_paragraphs(names)
                    self.store_numeric(
                        name,
                        self.numeric_value(Identifier(name)) + self.numeric_value(step),
                        rounded=False,
                        size_error=(),
                    )
            else:
                self.execute_paragraphs(names)
            return None
        if statement.times is not None:
            count = self.numeric_value(statement.times)
            for _ in range(int(count)):
                self.count_iteration()
                self.execute_statements(statement.body)
        elif statement.until is not None:
            while not self.evaluate_condition(statement.until):
                self.count_iteration()
                self.execute_statements(statement.body)
        elif statement.varying is not None:
            name, start, step, until = statement.varying
            self.store_numeric(name, self.numeric_value(start), rounded=False, size_error=())
            while not self.evaluate_condition(until):
                self.count_iteration()
                self.execute_statements(statement.body)
                self.store_numeric(
                    name,
                    self.numeric_value(Identifier(name)) + self.numeric_value(step),
                    rounded=False,
                    size_error=(),
                )
        else:
            self.execute_statements(statement.body)
        return None

    def _paragraph_span(self, start: str, thru: str | None) -> list[Paragraph]:
        if start not in self.paragraphs:
            raise RunError(f"unknown paragraph '{start}'", statement="PERFORM")
        begin = self.paragraphs[start]
        if thru is None:
            return [self.program.paragraphs[begin]]
        if thru not in self.paragraphs:
            raise RunError(f"unknown paragraph '{thru}'", statement="PERFORM")
        end = self.paragraphs[thru]
        if end < begin:
            raise RunError("PERFORM THRU end precedes start", statement="PERFORM")
        return self.program.paragraphs[begin : end + 1]

    def execute_paragraphs(self, paragraphs: list[Paragraph]) -> None:
        for paragraph in paragraphs:
            target = self.execute_paragraph(paragraph)
            if target is not None:
                raise RunError("GO TO out of a PERFORMed paragraph is not supported", statement="GO TO")
            if self.stopped:
                return

    def count_iteration(self) -> None:
        """Bound PERFORM loops even when the repeated paragraph executes no statements."""
        self.loop_iterations += 1
        if self.loop_iterations > self.step_limit:
            raise StepLimitError(f"program exceeded {self.step_limit} statements")

    def store_all(
        self, targets: tuple[str, ...], value: Decimal, rounded: bool, size_error: tuple[Statement, ...]
    ) -> None:
        for target in targets:
            self.store_numeric(target, value, rounded=rounded, size_error=size_error)

    # -- values ------------------------------------------------------------
    def operand_value(self, operand: Operand) -> object:
        if isinstance(operand, NumberLiteral):
            return operand.value
        if isinstance(operand, StringLiteral):
            return operand.value
        if isinstance(operand, Figurative):
            return Decimal(0) if operand.name.startswith("ZERO") else " "
        if isinstance(operand, Identifier):
            field = self.storage.field(operand.name)
            if field.is_group:
                return self.storage.render(field)
            value = self.storage.read(operand.name)
            return value
        raise RunError(f"unsupported operand {type(operand).__name__}")

    def operand_text(self, operand: Operand) -> str:
        value = self.operand_value(operand)
        if isinstance(value, Decimal):
            if isinstance(operand, Identifier):
                field = self.storage.field(operand.name)
                if field.picture is not None and field.picture.kind == "alnum":
                    return self.storage.text(operand.name)
            return format_decimal(value)
        return str(value)

    def display_item(self, operand: Operand) -> str:
        if isinstance(operand, Identifier):
            return self.storage.display_value(operand.name)
        return self.operand_text(operand)

    def numeric_value(self, operand: Expression) -> Decimal:
        if isinstance(operand, NumberLiteral):
            return operand.value
        if isinstance(operand, Negate):
            return -self.numeric_value(operand.operand)
        if isinstance(operand, BinaryOp):
            left = self.numeric_value(operand.left)
            right = self.numeric_value(operand.right)
            self.decimal_ops += 1
            if operand.operator == "+":
                return left + right
            if operand.operator == "-":
                return left - right
            if operand.operator == "*":
                return left * right
            if right == 0:
                raise RunError("division by zero", statement="COMPUTE")
            return left / right
        if isinstance(operand, Identifier):
            field = self.storage.field(operand.name)
            value = self.storage.read(operand.name)
            if field.picture is not None and field.picture.kind == "numeric":
                assert isinstance(value, Decimal)
                return value
            return self.parse_numeric_text(self.storage.text(operand.name))
        raise RunError(f"unsupported expression {type(operand).__name__}")

    def evaluate_expression(self, expression: Expression) -> Decimal:
        return self.numeric_value(expression)

    def evaluate_condition(self, condition: ConditionType) -> bool:
        if isinstance(condition, LogicalCondition):
            if condition.operator == "AND":
                return self.evaluate_condition(condition.left) and self.evaluate_condition(condition.right)
            return self.evaluate_condition(condition.left) or self.evaluate_condition(condition.right)
        if isinstance(condition, NotCondition):
            return not self.evaluate_condition(condition.condition)
        if isinstance(condition, ConditionName):
            return self.evaluate_condition_name(condition.name)
        if isinstance(condition, Relation):
            return self.compare(condition.left, condition.operator, condition.right)
        raise RunError(f"unsupported condition {type(condition).__name__}")

    def evaluate_condition_name(self, name: str) -> bool:
        field, condition = self.storage.condition_value(name)
        current = self.storage.read(field.name)
        for low, high in condition.values:
            if high is None:
                if self.values_equal(current, low):
                    return True
            else:
                lower = _compare_values(current, low)
                upper = _compare_values(current, high)
                if lower is not None and upper is not None and lower >= 0 and upper <= 0:
                    return True
        return False

    def compare(self, left: Operand, operator: str, right: Operand) -> bool:
        left_value = self.operand_value_for_compare(left)
        right_value = self.operand_value_for_compare(right)
        if isinstance(left_value, Decimal) and isinstance(right_value, Decimal):
            order = (left_value > right_value) - (left_value < right_value)
        else:
            left_text = str(left_value).rstrip()
            right_text = str(right_value).rstrip()
            order = (left_text > right_text) - (left_text < right_text)
        if operator == "=":
            return order == 0
        if operator == "<":
            return order < 0
        if operator == ">":
            return order > 0
        if operator == "<=":
            return order <= 0
        if operator == ">=":
            return order >= 0
        raise RunError(f"unsupported comparison '{operator}'")

    def operand_value_for_compare(self, operand: Operand) -> object:
        if isinstance(operand, Identifier):
            field = self.storage.field(operand.name)
            value = self.storage.read(operand.name)
            if field.picture is not None and field.picture.kind == "numeric":
                return value
            return self.storage.text(operand.name).rstrip()
        value = self.operand_value(operand)
        return value

    def values_equal(self, value: object, expected: object) -> bool:
        if isinstance(value, Decimal) and isinstance(expected, Decimal):
            return value == expected
        return str(value).rstrip() == str(expected).rstrip()

    # -- storage -----------------------------------------------------------
    def store_numeric(
        self,
        name: str,
        value: Decimal,
        *,
        rounded: bool,
        size_error: tuple[Statement, ...],
    ) -> None:
        field = self.storage.field(name)
        picture = field.picture
        if picture is None or picture.kind != "numeric":
            raise RunError(f"'{name}' is not a numeric field")
        precision = _picture_precision(picture, value)
        try:
            if rounded:
                quant = Decimal(1).scaleb(-picture.scale)
                value = _quantize(value, quant, ROUND_HALF_UP, precision)
                self.rounding_ops += 1
            truncated = _truncate(value, picture.scale, precision)
            integer_digits = max(1, truncated.adjusted() + 1)
            overflow = integer_digits > picture.digits - picture.scale
            negative_into_unsigned = truncated < 0 and not picture.signed
            if overflow or negative_into_unsigned:
                if size_error:
                    self.execute_statements(size_error)
                    return
                truncated = _truncate_high_order(truncated, picture.digits - picture.scale, precision)
        except DecimalException as error:
            if size_error:
                self.execute_statements(size_error)
                return
            raise RunError(f"numeric value does not fit '{name}'", statement="ARITHMETIC") from error
        self.storage.write(name, truncated)

    def store_token(self, name: str, text: str) -> None:
        field = self.storage.field(name)
        if field.is_group:
            self.move_to_group(field, text)
            return
        if field.picture is not None and field.picture.kind == "numeric":
            self.store_numeric(name, self.parse_numeric_text(text), rounded=False, size_error=())
            return
        self.storage.write(name, text)

    def parse_numeric_text(self, text: str) -> Decimal:
        cleaned = text.strip()
        if not cleaned:
            return Decimal(0)
        try:
            return Decimal(cleaned)
        except Exception as error:
            raise RunError(f"'{text}' is not numeric") from error


def _picture_precision(picture: Picture, value: Decimal) -> int:
    needed = max(picture.digits + 2, max(value.adjusted(), 0) + picture.scale + 3)
    return max(28, min(MAX_FIELD_LENGTH + 2, needed))


def _quantize(value: Decimal, quant: Decimal, rounding: str, precision: int) -> Decimal:
    with localcontext() as context:
        context.prec = precision
        return value.quantize(quant, rounding=rounding)


def _truncate(value: Decimal, scale: int, precision: int) -> Decimal:
    quant = Decimal(1).scaleb(-scale)
    return _quantize(value, quant, ROUND_DOWN, precision)


def _truncate_high_order(value: Decimal, integer_digits: int, precision: int) -> Decimal:
    if integer_digits <= 0:
        return Decimal(0)
    with localcontext() as context:
        context.prec = precision
        quant = Decimal(1).scaleb(integer_digits)
        return (value % quant) if value >= 0 else -((-value) % quant)


def _compare_values(left: object, right: object) -> int | None:
    if isinstance(left, Decimal) and isinstance(right, Decimal):
        return (left > right) - (left < right)
    if isinstance(left, str) and isinstance(right, str):
        return (left > right) - (left < right)
    return None


def _name_of(operand: Operand) -> str:
    if isinstance(operand, Identifier):
        return operand.name
    raise RunError("INSPECT REPLACING needs a data name")


def run_source(
    source: str,
    *,
    output: TextIO | None = None,
    accept: Iterable[str] | None = None,
    step_limit: int = DEFAULT_STEP_LIMIT,
) -> Interpreter:
    program = parse_program(source)
    stream = output

    def emit(text: str) -> None:
        if stream is not None:
            stream.write(text + "\n")

    interpreter = Interpreter(program, output=emit, accept_source=accept, step_limit=step_limit)
    interpreter.run()
    return interpreter
