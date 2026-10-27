"""Differential mode: run the original COBOL and a port, compare their output.

The comparison contract is documented in docs/DIFF_CONTRACT.md: text is decoded as
UTF-8, line endings are normalised, trailing spaces on each line and trailing blank
lines are ignored, everything else must match byte for byte.
"""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from .errors import CobolError, OracleError
from .interpreter import DEFAULT_STEP_LIMIT, run_source

PORT_TIMEOUT_SECONDS = 60


@dataclass(frozen=True)
class DiffResult:
    match: bool
    original: str
    port: str
    difference: str

    def to_dict(self) -> dict[str, object]:
        return {
            "match": self.match,
            "difference": self.difference,
            "original": self.original,
            "port": self.port,
        }


def normalize_text(text: str) -> str:
    lines = [line.rstrip() for line in text.replace("\r\n", "\n").replace("\r", "\n").split("\n")]
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def run_original(source: str, stdin_text: str = "", step_limit: int = DEFAULT_STEP_LIMIT) -> str:
    from io import StringIO

    output = StringIO()
    try:
        run_source(source, output=output, accept=stdin_text.splitlines(), step_limit=step_limit)
    except CobolError as error:
        raise OracleError(f"original COBOL failed: {error.message}") from error
    return output.getvalue()


def run_port(command: Sequence[str], stdin_text: str = "", cwd: Path | None = None) -> str:
    if not command:
        raise OracleError("port command is empty")
    try:
        completed = subprocess.run(  # noqa: S603 - explicit argv, no shell
            list(command),
            input=stdin_text,
            capture_output=True,
            text=True,
            timeout=PORT_TIMEOUT_SECONDS,
            cwd=str(cwd) if cwd else None,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as error:
        raise OracleError(f"cannot run the port: {error}") from error
    if completed.returncode != 0:
        raise OracleError(f"port exited with {completed.returncode}: {completed.stderr.strip()[:200]}")
    return completed.stdout


def compare(original: str, port: str) -> DiffResult:
    left = normalize_text(original)
    right = normalize_text(port)
    if left == right:
        return DiffResult(True, left, right, "")
    left_lines = left.split("\n")
    right_lines = right.split("\n")
    for index, (expected, actual) in enumerate(zip(left_lines, right_lines, strict=False)):
        if expected != actual:
            return DiffResult(False, left, right, f"line {index + 1}: original {expected!r} vs port {actual!r}")
    longer = "original" if len(left_lines) > len(right_lines) else "port"
    return DiffResult(False, left, right, f"{longer} has more lines ({len(left_lines)} vs {len(right_lines)})")


def default_port_command(path: str) -> list[str]:
    return [sys.executable, path]
