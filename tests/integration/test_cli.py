from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from cobrun.cli import (
    EXIT_CONFORMANCE,
    EXIT_OK,
    EXIT_ORACLE,
    EXIT_PARSE,
    EXIT_RUNTIME,
    EXIT_USAGE,
    main,
)

REPO = Path(__file__).resolve().parents[2]
PROGRAMS = REPO / "fixtures" / "programs"
EXPECTED = REPO / "fixtures" / "expected"
PORTS = REPO / "fixtures" / "ports"


def run(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    code = main(list(argv))
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def test_run_hello(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run(capsys, "run", str(PROGRAMS / "hello.cbl"))
    assert code == EXIT_OK and out == "HELLO WORLD\n" and err == ""


def test_run_with_input(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    stdin = tmp_path / "in.txt"
    stdin.write_text("ZZ\n", encoding="utf-8")
    code, out, _ = run(capsys, "run", str(PROGRAMS / "string-ops.cbl"), "--input", str(stdin))
    assert code == EXIT_OK and out.endswith("ZZ\n")


def test_run_json_report(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "run", str(PROGRAMS / "arithmetic.cbl"), "--json")
    payload = json.loads(out.strip().splitlines()[-1])
    assert code == EXIT_OK
    assert payload["program"] == "ARITH" and payload["rounding_ops"] == 1


def test_run_step_limit_is_a_runtime_error(capsys: pytest.CaptureFixture[str]) -> None:
    code, _, err = run(capsys, "run", str(PROGRAMS / "loop.cbl"), "--step-limit", "25")
    assert code == EXIT_RUNTIME and "25 statements" in err


def test_parse_and_dry_run(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "parse", str(PROGRAMS / "hello.cbl"))
    assert code == EXIT_OK and "program: HELLO" in out
    code, out, _ = run(capsys, "dry-run", str(PROGRAMS / "hello.cbl"))
    assert code == EXIT_OK and out.startswith("parse ok: HELLO")


def test_parse_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "parse", str(PROGRAMS / "hello.cbl"), "--json")
    payload = json.loads(out)
    assert code == EXIT_OK and payload["program"] == "HELLO" and "MAIN" in payload["paragraphs"]


def test_parse_error_exit_code(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    bad = tmp_path / "bad.cbl"
    bad.write_text("DISPLAY 'X'.\n", encoding="utf-8")
    code, _, err = run(capsys, "parse", str(bad))
    assert code == EXIT_PARSE and "parse error" in err


def test_missing_source_is_a_config_error(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code, _, err = run(capsys, "run", str(tmp_path / "missing.cbl"))
    assert code == EXIT_USAGE and "cannot read" in err


def test_oversized_source_is_rejected(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    big = tmp_path / "big.cbl"
    big.write_text("A" * (5 * 1024 * 1024 + 1), encoding="utf-8")
    code, _, err = run(capsys, "parse", str(big))
    assert code == EXIT_USAGE and "larger than" in err


def test_diff_match(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "diff", str(PROGRAMS / "hello.cbl"), "--port", str(PORTS / "hello_port.py"))
    assert code == EXIT_OK and "match" in out


def test_diff_mismatch(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "diff", str(PROGRAMS / "hello.cbl"), "--port", str(PORTS / "hello_bad.py"))
    assert code == EXIT_RUNTIME and "mismatch" in out and "line 1" in out


def test_diff_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(
        capsys,
        "diff",
        str(PROGRAMS / "hello.cbl"),
        "--port",
        str(PORTS / "hello_bad.py"),
        "--json",
    )
    payload = json.loads(out)
    assert code == EXIT_RUNTIME and payload["match"] is False


def test_doctor(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "doctor")
    assert code == EXIT_OK and "ROUND_HALF_UP" in out and "OK" in out


def test_doctor_json(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, _ = run(capsys, "doctor", "--json")
    payload = json.loads(out)
    assert code == EXIT_OK and payload["version"] == "0.1.0" and payload["rounding"] == "ROUND_HALF_UP"


def test_conformance_pass(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    (tmp_path / "CM101-hello.cbl").write_text((PROGRAMS / "hello.cbl").read_text(encoding="utf-8"))
    (tmp_path / "CM101-hello.out").write_text("HELLO WORLD\n", encoding="utf-8")
    code, out, _ = run(capsys, "conformance", "--ccvs", str(tmp_path))
    assert code == EXIT_OK and "1/1 passed" in out


def test_conformance_failure(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    (tmp_path / "CM101-hello.cbl").write_text((PROGRAMS / "hello.cbl").read_text(encoding="utf-8"))
    (tmp_path / "CM101-hello.out").write_text("OTHER\n", encoding="utf-8")
    code, _, _ = run(capsys, "conformance", "--ccvs", str(tmp_path))
    assert code == EXIT_CONFORMANCE


def test_conformance_missing_directory(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    code, _, err = run(capsys, "conformance", "--ccvs", str(tmp_path / "nope"))
    assert code == EXIT_CONFORMANCE and "does not exist" in err


def test_fetch_rejects_non_zip(capsys: pytest.CaptureFixture[str], tmp_path: Path) -> None:
    url = "file:///" + str(tmp_path / "payload.html").replace("\\", "/")
    (tmp_path / "payload.html").write_text("<html>moved</html>", encoding="utf-8")
    code, _, err = run(capsys, "fetch-ccvs", "--target", str(tmp_path / "ccvs85.zip"), "--url", url)
    assert code == EXIT_ORACLE and "did not return a ZIP" in err


def test_usage_errors() -> None:
    with pytest.raises(SystemExit) as caught:
        main(["run"])
    assert caught.value.code == EXIT_USAGE
    with pytest.raises(SystemExit) as caught:
        main(["nonsense"])
    assert caught.value.code == EXIT_USAGE


def test_module_entry_point() -> None:
    import os
    import subprocess

    env = dict(os.environ)
    env["PYTHONPATH"] = str(REPO / "src")
    result = subprocess.run(
        [sys.executable, "-m", "cobrun.cli", "--version"],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == "cobrun 0.1.0"
