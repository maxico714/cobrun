"""NIST CCVS85 plumbing: fetch-at-runtime only, never bundled.

As of 2026-10-26 the historical NIST URLs redirect to https://www.nist.gov/itl and no
longer serve the suite. ``fetch_ccvs`` therefore verifies the response looks like a ZIP
archive and fails closed otherwise. The repository never stores CCVS85 material.
"""

from __future__ import annotations

import urllib.error
import urllib.request
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .diff import normalize_text, run_original
from .errors import ConformanceError, OracleError

CCVS85_URL = "https://www.itl.nist.gov/div897/ctg/software/ccvs85.zip"
FETCH_TIMEOUT_SECONDS = 60
MAX_DOWNLOAD_BYTES = 200 * 1024 * 1024
MAX_CASE_BYTES = 5 * 1024 * 1024
ZIP_MAGIC = b"PK\x03\x04"


@dataclass(frozen=True)
class ConformanceCase:
    source: Path
    expected: Path


@dataclass(frozen=True)
class ConformanceResult:
    name: str
    section: str
    status: str  # pass | fail | unsupported
    detail: str

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "section": self.section, "status": self.status, "detail": self.detail}


def fetch_ccvs(target: Path, url: str = CCVS85_URL) -> Path:
    """Download the CCVS85 archive. Fails closed; never called by the library or tests."""
    request = urllib.request.Request(url, headers={"User-Agent": "cobrun/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=FETCH_TIMEOUT_SECONDS) as response:
            payload = response.read(MAX_DOWNLOAD_BYTES + 1)
    except (urllib.error.URLError, OSError) as error:
        raise OracleError(f"cannot download CCVS85 from {url}: {error}") from error
    if len(payload) > MAX_DOWNLOAD_BYTES:
        raise OracleError("CCVS85 download exceeds the size limit")
    if not payload.startswith(ZIP_MAGIC):
        raise OracleError(f"{url} did not return a ZIP archive (the URL may have moved; see docs/EVIDENCE.md)")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    try:
        with zipfile.ZipFile(target) as archive:
            archive.infolist()
    except zipfile.BadZipFile as error:
        target.unlink(missing_ok=True)
        raise OracleError(f"downloaded file is not a valid ZIP: {error}") from error
    return target


def discover_cases(directory: Path) -> list[ConformanceCase]:
    if not directory.is_dir():
        raise ConformanceError(f"conformance directory '{directory}' does not exist")
    cases: list[ConformanceCase] = []
    for source in sorted(directory.glob("*.cbl")):
        expected = source.with_suffix(".out")
        if expected.is_file():
            cases.append(ConformanceCase(source, expected))
    if not cases:
        raise ConformanceError("no .cbl/.out pairs found; see docs/CONFORMANCE.md for the layout")
    return cases


def section_of(name: str) -> str:
    return name.split("-", 1)[0].split("_", 1)[0].upper()


def _read_case(path: Path) -> str:
    try:
        size = path.stat().st_size
    except OSError as error:
        raise ConformanceError(f"cannot read '{path.name}': {error}") from error
    if size > MAX_CASE_BYTES:
        raise ConformanceError(f"'{path.name}' is larger than {MAX_CASE_BYTES} bytes")
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ConformanceError(f"cannot read '{path.name}' as UTF-8: {error}") from error


def run_conformance(directory: Path, step_limit: int = 100_000) -> list[ConformanceResult]:
    results: list[ConformanceResult] = []
    for case in discover_cases(directory):
        section = section_of(case.source.stem)
        try:
            source_text = _read_case(case.source)
        except ConformanceError as error:
            results.append(ConformanceResult(case.source.stem, section, "fail", str(error)[:200]))
            continue
        try:
            actual = run_original(source_text, step_limit=step_limit)
        except OracleError as error:
            message = str(error)
            status = "unsupported" if "not supported" in message or "unsupported" in message else "fail"
            results.append(ConformanceResult(case.source.stem, section, status, message[:200]))
            continue
        try:
            expected = normalize_text(_read_case(case.expected))
        except ConformanceError as error:
            results.append(ConformanceResult(case.source.stem, section, "fail", str(error)[:200]))
            continue
        observed = normalize_text(actual)
        if expected == observed:
            results.append(ConformanceResult(case.source.stem, section, "pass", ""))
        else:
            results.append(
                ConformanceResult(case.source.stem, section, "fail", f"expected {expected!r}, got {observed!r}")
            )
    return results


def summarize(results: list[ConformanceResult]) -> dict[str, object]:
    sections: dict[str, dict[str, int]] = {}
    for result in results:
        bucket = sections.setdefault(result.section, {"pass": 0, "fail": 0, "unsupported": 0})
        bucket[result.status] += 1
    passed = sum(1 for result in results if result.status == "pass")
    return {
        "passed": passed,
        "total": len(results),
        "failed": sum(1 for result in results if result.status == "fail"),
        "unsupported": sum(1 for result in results if result.status == "unsupported"),
        "sections": sections,
    }
