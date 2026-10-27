from __future__ import annotations

import json
from pathlib import Path

import pytest

from cobrun.interpreter import run_source

REPO = Path(__file__).resolve().parents[2]
FIXTURES = REPO / "fixtures"


def load_manifest() -> dict[str, object]:
    return json.loads((FIXTURES / "manifest.json").read_text(encoding="utf-8"))


MANIFEST = load_manifest()


@pytest.mark.parametrize("case", MANIFEST["cases"], ids=[case["name"] for case in MANIFEST["cases"]])
def test_fixture_output_matches(case: dict[str, object]) -> None:
    source = (FIXTURES / "programs" / case["program"]).read_text(encoding="utf-8")
    expected = (FIXTURES / "expected" / case["expected"]).read_text(encoding="utf-8")
    output: list[str] = []

    class Sink:
        def write(self, text: str) -> None:
            output.append(text.removesuffix("\n"))

    run_source(source, output=Sink(), accept=case.get("accept", []), step_limit=int(case.get("step_limit", 100_000)))  # type: ignore[arg-type]
    assert "\n".join(output) + "\n" == expected
