"""Parser for the COBOL-85 subset (see docs/COBOL_SUBSET.md)."""

from __future__ import annotations

from decimal import Decimal

from .data import Condition, Field, parse_picture
from .errors import ParseError
from .lexer import Token, tokenize
from .statements import (
    Accept,
    Arithmetic,
    BinaryOp,
    Compute,
    ConditionName,
    Continue,
    Display,
    Expression,
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

MAX_NESTING = 100
MAX_LITERAL_DIGITS = 100

STATEMENT_KEYWORDS = frozenset(
    {
        "ACCEPT",
        "ADD",
        "CALL",
        "COMPUTE",
        "CONTINUE",
        "DISPLAY",
        "DIVIDE",
        "ELSE",
        "END-ADD",
        "END-COMPUTE",
        "END-DISPLAY",
        "END-IF",
        "END-MULTIPLY",
        "END-PERFORM",
        "END-STRING",
        "END-UNSTRING",
        "GO",
        "IF",
        "INSPECT",
        "MOVE",
        "MULTIPLY",
        "PERFORM",
        "STOP",
        "STRING",
        "SUBTRACT",
        "UNSTRING",
    }
)

SCOPE_END = frozenset({"END-IF", "END-PERFORM", "END-ADD", "END-COMPUTE", "END-DISPLAY", "END-STRING", "END-UNSTRING"})

DATA_END = frozenset(
    {
        "ROUNDED",
        "ON",
        "END-ADD",
        "END-SUBTRACT",
        "END-MULTIPLY",
        "END-DIVIDE",
        "END-COMPUTE",
        "GIVING",
        "TO",
        "FROM",
        "BY",
        "INTO",
        "UNTIL",
        "TIMES",
        "VARYING",
        "UPON",
    }
)

FIGURATIVES = frozenset(
    {
        "ZERO",
        "ZEROS",
        "ZEROES",
        "SPACE",
        "SPACES",
        "HIGH-VALUE",
        "HIGH-VALUES",
        "LOW-VALUE",
        "LOW-VALUES",
        "QUOTE",
        "QUOTES",
    }
)


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.index = 0
        self.data_roots: list[Field] = []
        self.stack: list[Field] = []
        self.last_field: Field | None = None
        self.depth = 0

    # -- token helpers -----------------------------------------------------
    def peek(self, offset: int = 0) -> Token:
        position = min(self.index + offset, len(self.tokens) - 1)
        return self.tokens[position]

    def advance(self) -> Token:
        token = self.peek()
        if token.kind != "EOF":
            self.index += 1
        return token

    def match_word(self, *words: str) -> Token | None:
        token = self.peek()
        if token.kind == "WORD" and token.value in words:
            return self.advance()
        return None

    def expect_word(self, word: str) -> Token:
        token = self.match_word(word)
        if token is None:
            raise self.error(f"expected '{word}'")
        return token

    def expect_period(self) -> Token:
        token = self.peek()
        if token.kind != "PERIOD":
            raise self.error("expected '.' to end the sentence")
        return self.advance()

    def error(self, message: str) -> ParseError:
        token = self.peek()
        found = token.value or token.kind
        return ParseError(f"{message}, found '{found}'", line=token.line)

    # -- program -----------------------------------------------------------
    def parse_program(self) -> Program:
        self.expect_word("IDENTIFICATION")
        self.expect_word("DIVISION")
        self.expect_period()
        program_id = ""
        while True:
            token = self.peek()
            if token.kind == "EOF":
                raise self.error("missing DATA DIVISION")
            if token.kind == "WORD" and token.value in {"DATA", "PROCEDURE", "ENVIRONMENT"}:
                break
            if self.match_word("PROGRAM-ID") is not None:
                self.expect_period()
                name = self.peek()
                if name.kind != "WORD":
                    raise self.error("expected a program name")
                self.advance()
                program_id = name.value
                if self.peek().kind == "PERIOD":
                    self.advance()
                continue
            self.advance()
        if self.match_word("ENVIRONMENT") is not None:
            self.expect_word("DIVISION")
            self.expect_period()
            while True:
                token = self.peek()
                if token.kind == "EOF":
                    raise self.error("missing PROCEDURE DIVISION")
                if token.kind == "WORD" and token.value in {"DATA", "PROCEDURE"}:
                    break
                self.advance()
        if self.match_word("DATA") is not None:
            self.expect_word("DIVISION")
            self.expect_period()
            self.parse_data_division()
        self.expect_word("PROCEDURE")
        self.expect_word("DIVISION")
        self.expect_period()
        paragraphs = self.parse_procedure()
        if not program_id:
            raise ParseError("missing PROGRAM-ID", line=1)
        return Program(program_id, list(self.data_roots), paragraphs)

    # -- data division -----------------------------------------------------
    def parse_data_division(self) -> None:
        while True:
            token = self.peek()
            if token.kind == "EOF":
                raise self.error("missing PROCEDURE DIVISION")
            if token.kind == "WORD" and token.value == "PROCEDURE":
                return
            if token.kind == "WORD" and token.value == "WORKING-STORAGE":
                self.advance()
                self.expect_word("SECTION")
                self.expect_period()
                continue
            if token.kind == "WORD" and token.value in {"FILE", "LOCAL-STORAGE", "LINKAGE", "SCREEN"}:
                raise ParseError(f"{token.value} SECTION is not supported in v0.1", line=token.line)
            if token.kind == "NUMBER":
                self.parse_data_entry()
                continue
            raise self.error("expected a data entry")

    def parse_data_entry(self) -> None:
        level_token = self.advance()
        try:
            level = int(level_token.value)
        except ValueError as error:  # pragma: no cover - lexer only emits digits
            raise ParseError("invalid level number", line=level_token.line) from error
        name_token = self.peek()
        if name_token.kind != "WORD":
            raise self.error("expected a data name")
        self.advance()
        name = name_token.value
        picture = None
        value: object | None = None
        values: list[tuple[object, object | None]] = []
        while True:
            token = self.peek()
            if token.kind == "PERIOD":
                self.advance()
                break
            if token.kind == "EOF":
                raise self.error("unterminated data entry")
            if token.kind == "WORD" and token.value in {"PIC", "PICTURE"}:
                self.advance()
                picture = parse_picture(self.read_picture())
                continue
            if token.kind == "WORD" and token.value in {"VALUE", "VALUES"}:
                self.advance()
                first = self.read_literal()
                if self.match_word("THRU", "THROUGH") is not None:
                    second = self.read_literal()
                    values.append((first, second))
                else:
                    values.append((first, None))
                value = first
                while self.match_word("VALUE", "VALUES") is not None:
                    items = self.read_literal()
                    values.append((items, None))
                continue
            if token.kind == "WORD" and token.value == "USAGE":
                self.advance()
                usage = self.peek()
                if usage.kind != "WORD" or usage.value != "DISPLAY":
                    raise ParseError("only USAGE DISPLAY is supported in v0.1", line=usage.line)
                self.advance()
                continue
            if token.kind == "WORD" and token.value in {"BLANK", "JUSTIFIED", "JUST", "SYNCHRONIZED", "SYNC"}:
                raise ParseError(f"clause {token.value} is not supported in v0.1", line=token.line)
            raise self.error("unsupported data clause")
        if level == 88:
            if self.last_field is None:
                raise ParseError("88 entry without a parent field", line=level_token.line)
            if not values:
                raise ParseError("88 entry requires a VALUE clause", line=level_token.line)
            self.last_field.conditions.append(Condition(name, values))
            return
        if level < 1 or (49 < level < 77) or level > 88:
            raise ParseError(f"unsupported level number {level}", line=level_token.line)
        field = Field(name, level, picture, value, line=level_token.line)
        while self.stack and self.stack[-1].level >= level:
            self.stack.pop()
        if self.stack:
            if level <= self.stack[-1].level:
                raise ParseError(f"level {level} cannot be a child of {self.stack[-1].level}", line=level_token.line)
            self.stack[-1].children.append(field)
        else:
            self.data_roots.append(field)
        self.stack.append(field)
        self.last_field = field

    def read_picture(self) -> str:
        pieces: list[str] = []
        while True:
            token = self.peek()
            if token.kind in {"NUMBER", "LPAREN", "RPAREN"}:
                pieces.append(str(self.advance().value))
                continue
            if token.kind == "WORD" and _is_picture_word(token.value):
                pieces.append(str(self.advance().value))
                continue
            break
        if not pieces:
            raise self.error("expected a PICTURE string")
        return "".join(pieces)

    def read_literal(self) -> object:
        token = self.peek()
        if token.kind == "NUMBER":
            self.advance()
            return self.decimal_literal(token)
        if token.kind == "STRING":
            self.advance()
            return token.value
        if token.kind == "WORD" and token.value in FIGURATIVES:
            self.advance()
            return _figurative_value(token.value)
        raise self.error("expected a literal")

    def decimal_literal(self, token: Token) -> Decimal:
        digits = token.value.replace(".", "")
        if len(digits) > MAX_LITERAL_DIGITS:
            raise ParseError(f"numeric literal has more than {MAX_LITERAL_DIGITS} digits", line=token.line)
        try:
            return Decimal(token.value)
        except Exception as error:  # pragma: no cover - lexer digits only
            raise ParseError("invalid numeric literal", line=token.line) from error

    # -- procedure division -------------------------------------------------
    def parse_procedure(self) -> list[Paragraph]:
        paragraphs: list[Paragraph] = []
        current: Paragraph | None = None
        while self.peek().kind != "EOF":
            token = self.peek()
            if token.kind == "PERIOD":
                self.advance()
                continue
            if (
                token.kind == "WORD"
                and self.peek(1).kind == "PERIOD"
                and token.value not in STATEMENT_KEYWORDS
                and token.value not in SCOPE_END
            ):
                current = Paragraph(token.value)
                paragraphs.append(current)
                self.advance()
                self.advance()
                continue
            if current is None:
                current = Paragraph("")
                paragraphs.append(current)
            current.statements.extend(self.parse_statements(set()))
        return paragraphs

    def parse_statements(self, terminators: set[str]) -> list[Statement]:
        statements: list[Statement] = []
        while True:
            token = self.peek()
            if token.kind == "EOF":
                return statements
            if token.kind == "PERIOD":
                self.advance()
                return statements
            if token.kind == "WORD" and token.value in terminators:
                return statements
            if (
                token.kind == "WORD"
                and self.peek(1).kind == "PERIOD"
                and token.value not in STATEMENT_KEYWORDS
                and not terminators
            ):
                return statements
            statements.append(self.parse_statement())

    def parse_statement(self) -> Statement:
        token = self.peek()
        if token.kind != "WORD":
            raise self.error("expected a statement")
        keyword = token.value
        line = token.line
        if keyword == "MOVE":
            self.advance()
            source = self.parse_operand()
            self.expect_word("TO")
            targets = self.read_identifiers()
            return Move(source, tuple(targets), line=line)
        if keyword in {"ADD", "SUBTRACT", "MULTIPLY", "DIVIDE"}:
            return self.parse_arithmetic(keyword, line)
        if keyword == "COMPUTE":
            return self.parse_compute(line)
        if keyword == "IF":
            return self.parse_if(line)
        if keyword == "PERFORM":
            return self.parse_perform(line)
        if keyword == "GO":
            self.advance()
            self.expect_word("TO")
            return GoTo(tuple(self.read_identifiers()), line=line)
        if keyword == "STOP":
            self.advance()
            self.match_word("RUN")
            return StopRun(line=line)
        if keyword == "DISPLAY":
            self.advance()
            items = self.read_operands_until({"."})
            self.match_word("END-DISPLAY")
            return Display(tuple(items), line=line)
        if keyword == "ACCEPT":
            self.advance()
            name = self.read_identifiers()
            if len(name) != 1:
                raise self.error("ACCEPT needs exactly one target")
            return Accept(name[0], line=line)
        if keyword == "STRING":
            return self.parse_string(line)
        if keyword == "UNSTRING":
            return self.parse_unstring(line)
        if keyword == "INSPECT":
            return self.parse_inspect(line)
        if keyword == "CONTINUE":
            self.advance()
            return Continue(line=line)
        if keyword == "CALL":
            raise ParseError("CALL is not supported in v0.1", line=line)
        if keyword in SCOPE_END or keyword == "ELSE":
            raise ParseError(f"unexpected '{keyword}'", line=line)
        raise ParseError(f"unsupported statement '{keyword}'", line=line)

    def parse_arithmetic(self, keyword: str, line: int) -> Arithmetic:
        self.advance()
        if keyword == "MULTIPLY":
            first = self.parse_expression()
            self.expect_word("BY")
            second = self.parse_expression()
            giving = False
            targets: list[str] = []
            if self.match_word("GIVING") is not None:
                giving = True
                targets = self.read_identifiers()
            else:
                if not isinstance(second, Identifier):
                    raise self.error("MULTIPLY needs a data name as the receiving field")
                targets = [second.name]
            return self.finish_arithmetic(keyword, (first, second), tuple(targets), giving, line)
        if keyword == "DIVIDE":
            first = self.parse_expression()
            into = False
            if self.match_word("BY") is not None:
                second = self.parse_expression()
            else:
                self.expect_word("INTO")
                into = True
                second = self.parse_expression()
            giving = False
            receivers: list[str] = []
            if self.match_word("GIVING") is not None:
                giving = True
                receivers = self.read_identifiers()
            else:
                if not isinstance(second, Identifier):
                    raise self.error("DIVIDE needs a data name as the receiving field")
                receivers = [second.name]
            pair = (second, first) if into else (first, second)
            return self.finish_arithmetic(keyword, pair, tuple(receivers), giving, line)
        operands: list[Expression] = [self.parse_expression()]
        while True:
            token = self.peek()
            if token.kind == "WORD" and token.value in {"TO", "FROM", "GIVING"}:
                break
            if token.kind in {"PERIOD", "EOF"} or (token.kind == "WORD" and token.value in SCOPE_END | DATA_END):
                raise self.error(f"{keyword} needs TO or FROM")
            operands.append(self.parse_expression())
        if self.peek().kind != "WORD" or self.peek().value not in {"TO", "FROM", "GIVING"}:
            raise self.error(f"{keyword} needs TO or FROM")
        connector = str(self.advance().value)
        giving = connector == "GIVING"
        receivers = self.read_identifiers()
        return self.finish_arithmetic(keyword, tuple(operands), tuple(receivers), giving, line)

    def finish_arithmetic(
        self,
        keyword: str,
        operands: tuple[Expression, ...],
        targets: tuple[str, ...],
        giving: bool,
        line: int,
    ) -> Arithmetic:
        rounded = self.match_word("ROUNDED") is not None
        on_size_error: list[Statement] = []
        if self.match_word("ON") is not None:
            self.expect_word("SIZE")
            self.expect_word("ERROR")
            on_size_error = self.parse_statements({f"END-{keyword}"})
        self.match_word(f"END-{keyword}")
        return Arithmetic(keyword, operands, targets, giving, rounded, tuple(on_size_error), line=line)

    def parse_compute(self, line: int) -> Compute:
        self.advance()
        target = self.expect_identifier()
        rounded = self.match_word("ROUNDED") is not None
        token = self.peek()
        if token.kind != "OP" or token.value != "=":
            raise self.error("expected '=' in COMPUTE")
        self.advance()
        expression = self.parse_expression()
        rounded = self.match_word("ROUNDED") is not None or rounded
        on_size_error: list[Statement] = []
        if self.match_word("ON") is not None:
            self.expect_word("SIZE")
            self.expect_word("ERROR")
            on_size_error = self.parse_statements({"END-COMPUTE"})
        self.match_word("END-COMPUTE")
        return Compute(target, expression, rounded, tuple(on_size_error), line=line)

    def parse_if(self, line: int) -> If:
        self.enter()
        try:
            return self._parse_if(line)
        finally:
            self.depth -= 1

    def _parse_if(self, line: int) -> If:
        self.advance()
        condition = self.parse_condition()
        then_body = self.parse_statements({"ELSE", "END-IF"})
        else_body: list[Statement] = []
        if self.match_word("ELSE") is not None:
            else_body = self.parse_statements({"END-IF"})
        self.match_word("END-IF")
        return If(condition, tuple(then_body), tuple(else_body), line=line)

    def parse_perform(self, line: int) -> Perform:
        self.enter()
        try:
            return self._parse_perform(line)
        finally:
            self.depth -= 1

    def _parse_perform(self, line: int) -> Perform:
        self.advance()
        paragraph = None
        thru = None
        if (
            self.peek().kind == "WORD"
            and self.peek().value not in STATEMENT_KEYWORDS
            and self.peek().value
            not in {
                "TIMES",
                "UNTIL",
                "VARYING",
            }
        ):
            paragraph = self.advance().value
            if self.match_word("THRU", "THROUGH") is not None:
                target = self.peek()
                if target.kind != "WORD":
                    raise self.error("expected a paragraph after THRU")
                thru = self.advance().value
        times: Expression | None = None
        until: ConditionType | None = None
        varying = None
        if (
            (
                self.peek().kind == "NUMBER"
                or (self.peek().kind == "WORD" and self.peek().value not in {"UNTIL", "VARYING"})
            )
            and self.peek(1).kind == "WORD"
            and self.peek(1).value == "TIMES"
        ):
            times = self.parse_expression()
            self.advance()
        if self.match_word("TIMES") is not None and times is None:
            times = NumberLiteral(Decimal(1))
        if self.match_word("UNTIL") is not None:
            until = self.parse_condition()
        if self.match_word("VARYING") is not None:
            name = self.expect_identifier()
            self.expect_word("FROM")
            start = self.parse_expression()
            self.expect_word("BY")
            step = self.parse_expression()
            self.expect_word("UNTIL")
            varying_until = self.parse_condition()
            varying = (name, start, step, varying_until)
        body: tuple[Statement, ...] = ()
        if self.match_word("END-PERFORM") is not None:
            body = ()
        elif paragraph is None and (times is not None or until is not None or varying is not None):
            inline = self.parse_statements({"END-PERFORM"})
            self.match_word("END-PERFORM")
            body = tuple(inline)
        return Perform(paragraph, thru, times, until, varying, body, line=line)

    def parse_string(self, line: int) -> StringStatement:
        self.advance()
        parts: list[tuple[Operand, bool]] = []
        while self.peek().kind != "WORD" or self.peek().value != "INTO":
            if self.peek().kind in {"EOF", "PERIOD"}:
                raise self.error("STRING needs INTO")
            operand = self.parse_operand()
            literal = isinstance(operand, StringLiteral)
            if self.match_word("DELIMITED") is not None:
                self.expect_word("BY")
                if self.match_word("SIZE") is None:
                    raise ParseError("STRING supports only DELIMITED BY SIZE in v0.1", line=line)
            parts.append((operand, literal))
        self.expect_word("INTO")
        target = self.expect_identifier()
        while self.match_word("WITH") is not None:
            self.expect_word("POINTER")
            self.expect_identifier()
        self.match_word("END-STRING")
        return StringStatement(tuple(parts), target, line=line)

    def parse_unstring(self, line: int) -> Unstring:
        self.advance()
        source = self.parse_operand()
        delimiter = None
        if self.match_word("DELIMITED") is not None:
            self.expect_word("BY")
            self.match_word("ALL")
            literal = self.read_literal()
            if not isinstance(literal, str):
                raise ParseError("UNSTRING delimiter must be a string literal", line=line)
            delimiter = StringLiteral(literal)
        self.expect_word("INTO")
        targets = tuple(self.read_identifiers())
        self.match_word("END-UNSTRING")
        return Unstring(source, delimiter, targets, line=line)

    def parse_inspect(self, line: int) -> Statement:
        self.advance()
        source = self.parse_operand()
        if self.match_word("TALLYING") is not None:
            target = self.expect_identifier()
            self.expect_word("FOR")
            self.match_word("ALL")
            pattern = self.read_literal()
            if not isinstance(pattern, str):
                raise ParseError("INSPECT TALLYING needs a string literal", line=line)
            return InspectTallying(source, target, StringLiteral(pattern), line=line)
        if self.match_word("REPLACING") is not None:
            self.match_word("ALL")
            old = self.read_literal()
            self.expect_word("BY")
            new = self.read_literal()
            if not isinstance(old, str) or not isinstance(new, str):
                raise ParseError("INSPECT REPLACING needs string literals", line=line)
            return InspectReplacing(source, StringLiteral(old), StringLiteral(new), line=line)
        raise self.error("INSPECT supports TALLYING or REPLACING")

    # -- conditions and expressions ----------------------------------------
    def enter(self) -> None:
        self.depth += 1
        if self.depth > MAX_NESTING:
            raise ParseError(f"statements nest more than {MAX_NESTING} levels deep", line=self.peek().line)

    def parse_condition(self) -> ConditionType:
        self.enter()
        try:
            return self._parse_condition()
        finally:
            self.depth -= 1

    def _parse_condition(self) -> ConditionType:
        left = self.parse_and_condition()
        while self.match_word("OR") is not None:
            left = LogicalCondition("OR", left, self.parse_and_condition())
        return left

    def parse_and_condition(self) -> ConditionType:
        left = self.parse_not_condition()
        while self.match_word("AND") is not None:
            left = LogicalCondition("AND", left, self.parse_not_condition())
        return left

    def parse_not_condition(self) -> ConditionType:
        self.enter()
        try:
            return self._parse_not_condition()
        finally:
            self.depth -= 1

    def _parse_not_condition(self) -> ConditionType:
        if self.match_word("NOT") is not None:
            return NotCondition(self.parse_not_condition())
        if self.peek().kind == "LPAREN":
            self.advance()
            condition = self.parse_condition()
            if self.peek().kind != "RPAREN":
                raise self.error("expected ')'")
            self.advance()
            return condition
        left = self.parse_operand()
        token = self.peek()
        if token.kind == "OP" and token.value in {"=", "<", ">", "<=", ">="}:
            self.advance()
            right = self.parse_operand()
            return Relation(left, str(token.value), right)
        if not isinstance(left, Identifier):
            raise self.error("expected a comparison or a condition name")
        return ConditionName(left.name)

    def parse_expression(self) -> Expression:
        self.enter()
        try:
            return self._parse_expression()
        finally:
            self.depth -= 1

    def _parse_expression(self) -> Expression:
        node = self.parse_term()
        while True:
            token = self.peek()
            if token.kind == "OP" and token.value in {"+", "-"}:
                self.advance()
                node = BinaryOp(str(token.value), node, self.parse_term())
                continue
            return node

    def parse_term(self) -> Expression:
        node = self.parse_factor()
        while True:
            token = self.peek()
            if token.kind == "OP" and token.value in {"*", "/"}:
                self.advance()
                node = BinaryOp(str(token.value), node, self.parse_factor())
                continue
            return node

    def parse_factor(self) -> Expression:
        token = self.peek()
        if token.kind == "OP" and token.value in {"-", "+"}:
            self.advance()
            inner = self.parse_factor()
            return Negate(inner) if token.value == "-" else inner
        if token.kind == "LPAREN":
            self.advance()
            node = self.parse_expression()
            if self.peek().kind != "RPAREN":
                raise self.error("expected ')'")
            self.advance()
            return node
        if token.kind == "NUMBER":
            self.advance()
            return NumberLiteral(self.decimal_literal(token))
        if token.kind == "WORD":
            self.advance()
            return Identifier(token.value)
        raise self.error("expected an expression")

    def parse_operand(self) -> Operand:
        token = self.peek()
        if token.kind == "OP" and token.value in {"-", "+"}:
            self.advance()
            literal = self.parse_operand()
            if not isinstance(literal, NumberLiteral):
                raise ParseError("a sign can only precede a numeric literal", line=token.line)
            return NumberLiteral(-literal.value if token.value == "-" else literal.value)
        if token.kind == "NUMBER":
            self.advance()
            return NumberLiteral(self.decimal_literal(token))
        if token.kind == "STRING":
            self.advance()
            return StringLiteral(token.value)
        if token.kind == "WORD" and token.value in FIGURATIVES:
            self.advance()
            value = _figurative_value(token.value)
            if isinstance(value, str):
                return StringLiteral(value)
            assert isinstance(value, Decimal)
            return NumberLiteral(value)
        if token.kind == "WORD":
            self.advance()
            return Identifier(token.value)
        raise self.error("expected an operand")

    def read_identifiers(self) -> list[str]:
        names: list[str] = []
        while self.peek().kind == "WORD" and self.peek().value not in STATEMENT_KEYWORDS | SCOPE_END | DATA_END | {
            "ELSE"
        }:
            token = self.peek()
            if self.peek(1).kind == "PERIOD" and token.value in {"THRU", "THROUGH"}:
                break
            names.append(self.advance().value)
            if self.peek().kind == "PERIOD":
                break
            if self.peek().kind == "NUMBER":
                break
        if not names:
            raise self.error("expected a data name")
        return names

    def read_operands_until(self, terminators: set[str]) -> list[Operand]:
        items: list[Operand] = []
        while True:
            token = self.peek()
            if token.kind in {"PERIOD", "EOF"}:
                return items
            if token.kind == "WORD" and (
                token.value in terminators or token.value in SCOPE_END or token.value == "ELSE"
            ):
                return items
            if token.kind == "WORD" and token.value == "UPON":
                raise ParseError("DISPLAY UPON is not supported in v0.1", line=token.line)
            items.append(self.parse_operand())

    def expect_identifier(self) -> str:
        token = self.peek()
        if token.kind != "WORD":
            raise self.error("expected a data name")
        self.advance()
        return token.value


def _is_picture_word(word: str) -> bool:
    return bool(word) and all(char in "XSVPA9" for char in word)


def _figurative_value(name: str) -> object:
    if name.startswith("ZERO"):
        return Decimal(0)
    if name.startswith("SPACE"):
        return " "
    if name.startswith("HIGH-VALUE"):
        return "\xff"
    if name.startswith("LOW-VALUE"):
        return "\x00"
    return '"'


def parse_program(text: str) -> Program:
    return Parser(tokenize(text)).parse_program()
