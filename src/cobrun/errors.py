"""Structured errors with stable rule ids."""

from __future__ import annotations


class CobolError(Exception):
    """Base class for every error raised by cobrun."""

    code = "E_COBOL"

    def __init__(self, message: str, *, line: int = 0, statement: str = "") -> None:
        self.message = message
        self.line = line
        self.statement = statement
        location = f" (line {line})" if line else ""
        super().__init__(f"{message}{location}")

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {"code": self.code, "message": self.message}
        if self.line:
            payload["line"] = self.line
        if self.statement:
            payload["statement"] = self.statement
        return payload


class ParseError(CobolError):
    code = "E_PARSE"


class RunError(CobolError):
    code = "E_RUNTIME"


class StepLimitError(CobolError):
    code = "E_STEPLIMIT"


class ConfigError(CobolError):
    code = "E_CONFIG"


class OracleError(CobolError):
    code = "E_ORACLE"


class ConformanceError(CobolError):
    code = "E_CONFORMANCE"
