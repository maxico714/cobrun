"""Provenance, never-bundle and dependency checks."""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / "src" / "cobrun"
FIXTURES = REPO / "fixtures"

STDLIB_ONLY = {
    "__future__",
    "argparse",
    "collections",
    "contextlib",
    "dataclasses",
    "decimal",
    "io",
    "json",
    "pathlib",
    "shlex",
    "subprocess",
    "sys",
    "typing",
    "re",
    "urllib",
    "zipfile",
}

CCVS_PATTERNS = ("ccvs", "CCVS", "NIST", "itl.nist.gov")


def iter_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def test_repository_has_no_ccvs85_archives_or_sources() -> None:
    own_programs = (FIXTURES / "programs").resolve()
    for path in iter_files(REPO):
        if any(
            part in {".git", "node_modules", ".venv", "dist", "build", ".pytest_cache", ".ruff_cache", ".mypy_cache"}
            for part in path.parts
        ):
            continue
        assert path.suffix.lower() not in {".zip", ".cob", ".cbl85"}, f"unexpected archive/COBOL file: {path}"
        if path.suffix.lower() == ".cbl":
            assert path.resolve().parent == own_programs, f"COBOL file outside fixtures/programs: {path}"
            assert not any(marker in path.name.upper() for marker in ("CCVS", "NIST")), path
    assert not (REPO / "ccvs85").exists()


def test_fixture_programs_are_own_work() -> None:
    allowed = {
        "hello.cbl",
        "arithmetic.cbl",
        "rounding.cbl",
        "perform.cbl",
        "conditions.cbl",
        "string-ops.cbl",
        "loop.cbl",
    }
    programs = {path.name for path in (FIXTURES / "programs").glob("*.cbl")}
    assert programs == allowed


def test_third_party_notices_state_fetch_at_runtime() -> None:
    text = (REPO / "THIRD_PARTY_NOTICES.md").read_text(encoding="utf-8")
    assert "CCVS85" in text
    assert "fetched at runtime" in text.lower() or "never bundled" in text.lower()


def test_readme_states_the_subset_and_never_bundle_policy() -> None:
    text = (REPO / "README.md").read_text(encoding="utf-8")
    assert "ROUND_HALF_UP" in text
    lowered = text.lower()
    assert "not bundled" in lowered or "no ccvs85 files" in lowered


def test_core_imports_only_the_standard_library() -> None:
    offenders: list[str] = []
    for path in SRC.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root not in STDLIB_ONLY:
                        offenders.append(f"{path.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                root = node.module.split(".")[0]
                if root not in STDLIB_ONLY and root != "cobrun":
                    offenders.append(f"{path.name}: from {node.module}")
    assert offenders == []


def test_pyproject_declares_mit_and_no_runtime_dependencies() -> None:
    text = (REPO / "pyproject.toml").read_text(encoding="utf-8")
    assert 'license = { text = "MIT" }' in text
    before_optional = text.split("[project.optional-dependencies]")[0]
    assert "dependencies = [" not in before_optional


def test_no_todo_markers_in_source() -> None:
    pattern = re.compile(r"\b(TODO|FIXME|XXX)\b")
    offenders = []
    for path in SRC.glob("*.py"):
        if pattern.search(path.read_text(encoding="utf-8")):
            offenders.append(path.name)
    assert offenders == []
