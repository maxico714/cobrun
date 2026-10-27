from __future__ import annotations

import sys
from pathlib import Path

import pytest

from cobrun.diff import compare, normalize_text, run_original, run_port
from cobrun.errors import OracleError

REPO = Path(__file__).resolve().parents[2]
PROGRAMS = REPO / "fixtures" / "programs"
PORTS = REPO / "fixtures" / "ports"


def test_normalize_text_strips_trailing_spaces_and_blank_lines() -> None:
    assert normalize_text("A  \r\nB\t\r\n\r\n") == "A\nB"


def test_normalize_text_keeps_internal_blank_lines() -> None:
    assert normalize_text("A\n\nB") == "A\n\nB"


def test_compare_match() -> None:
    result = compare("HELLO\n", "HELLO   \r\n")
    assert result.match and result.difference == ""


def test_compare_mismatch_reports_line() -> None:
    result = compare("A\nB\n", "A\nC\n")
    assert not result.match
    assert "line 2" in result.difference


def test_compare_extra_lines() -> None:
    result = compare("A\n", "A\nB\n")
    assert not result.match
    assert "more lines" in result.difference


def test_run_original_executes_cobol() -> None:
    source = (PROGRAMS / "hello.cbl").read_text(encoding="utf-8")
    assert run_original(source) == "HELLO WORLD\n"


def test_run_original_maps_runtime_errors_to_oracle_errors() -> None:
    source = """IDENTIFICATION DIVISION.
PROGRAM-ID. P.
PROCEDURE DIVISION.
MAIN.
    PERFORM MISSING.
    STOP RUN.
"""
    with pytest.raises(OracleError):
        run_original(source)


def test_run_port_with_python_script() -> None:
    output = run_port([sys.executable, str(PORTS / "hello_port.py")])
    assert output == "HELLO WORLD\n"


def test_run_port_reports_non_zero_exit(tmp_path: Path) -> None:
    script = tmp_path / "fail.py"
    script.write_text("import sys\nsys.exit(3)\n", encoding="utf-8")
    with pytest.raises(OracleError) as caught:
        run_port([sys.executable, str(script)])
    assert "exited with 3" in str(caught.value)


def test_run_port_reports_missing_command() -> None:
    with pytest.raises(OracleError):
        run_port(["definitely-not-a-command-xyz"])


def test_run_port_empty_command() -> None:
    with pytest.raises(OracleError):
        run_port([])


def test_run_port_passes_stdin(tmp_path: Path) -> None:
    script = tmp_path / "echo.py"
    script.write_text("print(input().upper())\n", encoding="utf-8")
    assert run_port([sys.executable, str(script)], "abc\n") == "ABC\n"
