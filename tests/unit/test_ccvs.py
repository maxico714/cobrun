from __future__ import annotations

import io
import zipfile
from pathlib import Path

import pytest

from cobrun.ccvs import (
    ConformanceResult,
    discover_cases,
    fetch_ccvs,
    run_conformance,
    section_of,
    summarize,
)
from cobrun.errors import ConformanceError, OracleError

HELLO = """IDENTIFICATION DIVISION.
PROGRAM-ID. HELLO.
PROCEDURE DIVISION.
MAIN.
    DISPLAY "HI".
    STOP RUN.
"""

UNSUPPORTED = """IDENTIFICATION DIVISION.
PROGRAM-ID. CALLER.
PROCEDURE DIVISION.
MAIN.
    CALL "OTHER".
    STOP RUN.
"""


def write_case(directory: Path, name: str, source: str, expected: str) -> None:
    (directory / f"{name}.cbl").write_text(source, encoding="utf-8")
    (directory / f"{name}.out").write_text(expected, encoding="utf-8")


def test_discover_cases_requires_pairs(tmp_path: Path) -> None:
    with pytest.raises(ConformanceError):
        discover_cases(tmp_path / "missing")
    with pytest.raises(ConformanceError):
        discover_cases(tmp_path)
    (tmp_path / "only.cbl").write_text(HELLO, encoding="utf-8")
    with pytest.raises(ConformanceError) as caught:
        discover_cases(tmp_path)
    assert "no .cbl/.out pairs" in str(caught.value)


def test_run_conformance_pass_and_fail(tmp_path: Path) -> None:
    write_case(tmp_path, "CM101-hello", HELLO, "HI\n")
    write_case(tmp_path, "CM102-fail", HELLO, "WRONG\n")
    results = run_conformance(tmp_path)
    statuses = {result.name: result.status for result in results}
    assert statuses == {"CM101-hello": "pass", "CM102-fail": "fail"}
    report = summarize(results)
    assert report["passed"] == 1 and report["failed"] == 1 and report["total"] == 2
    assert report["sections"]["CM101"] == {"pass": 1, "fail": 0, "unsupported": 0}


def test_run_conformance_marks_unsupported_constructs(tmp_path: Path) -> None:
    write_case(tmp_path, "SM201-call", UNSUPPORTED, "")
    results = run_conformance(tmp_path)
    assert results[0].status == "unsupported"
    assert summarize(results)["unsupported"] == 1


def test_section_of() -> None:
    assert section_of("CM101-hello") == "CM101"
    assert section_of("IC-201") == "IC"
    assert section_of("simple") == "SIMPLE"


def test_fetch_ccvs_rejects_non_zip_payloads(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Response(io.BytesIO):
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(request: object, timeout: int = 0) -> Response:
        return Response(b"<html>moved</html>")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(OracleError) as caught:
        fetch_ccvs(tmp_path / "ccvs85.zip")
    assert "did not return a ZIP" in str(caught.value)
    assert not (tmp_path / "ccvs85.zip").exists()


def test_fetch_ccvs_accepts_a_valid_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("README.txt", "suite")
    data = payload.getvalue()

    class Response(io.BytesIO):
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(request: object, timeout: int = 0) -> Response:
        return Response(data)

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    target = fetch_ccvs(tmp_path / "nested" / "ccvs85.zip")
    assert target.is_file()
    assert target.read_bytes() == data


def test_fetch_ccvs_rejects_invalid_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class Response(io.BytesIO):
        def __enter__(self) -> Response:
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def fake_urlopen(request: object, timeout: int = 0) -> Response:
        return Response(b"PK\x03\x04broken")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(OracleError):
        fetch_ccvs(tmp_path / "ccvs85.zip")
    assert not (tmp_path / "ccvs85.zip").exists()


def test_fetch_ccvs_network_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(request: object, timeout: int = 0) -> object:
        raise OSError("network down")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    with pytest.raises(OracleError) as caught:
        fetch_ccvs(tmp_path / "ccvs85.zip")
    assert "cannot download" in str(caught.value)


def test_summarize_empty() -> None:
    assert summarize([]) == {"passed": 0, "total": 0, "failed": 0, "unsupported": 0, "sections": {}}


def test_conformance_result_dict() -> None:
    result = ConformanceResult("CM101-hello", "CM101", "pass", "")
    assert result.to_dict() == {"name": "CM101-hello", "section": "CM101", "status": "pass", "detail": ""}
