"""Command-line interface: run, parse, doctor, diff, fetch-ccvs, conformance, dry-run."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from . import __version__
from .ccvs import CCVS85_URL, fetch_ccvs, run_conformance, summarize
from .diff import compare, default_port_command, run_original, run_port
from .errors import CobolError, ConfigError, ConformanceError, OracleError, ParseError, RunError, StepLimitError
from .interpreter import DEFAULT_STEP_LIMIT, Interpreter
from .parser import parse_program

EXIT_OK = 0
EXIT_RUNTIME = 1
EXIT_PARSE = 2
EXIT_CONFORMANCE = 3
EXIT_ORACLE = 4
EXIT_USAGE = 5

MAX_SOURCE_BYTES = 5 * 1024 * 1024


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        self.print_usage(sys.stderr)
        self.exit(EXIT_USAGE, f"{self.prog}: error: {message}\n")


def build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="cobrun", description="COBOL-85 core-subset interpreter with differential testing")
    parser.add_argument("--version", action="version", version=f"cobrun {__version__}")
    commands = parser.add_subparsers(dest="command", required=True, parser_class=_Parser)

    run_parser = commands.add_parser("run", help="run a COBOL program")
    run_parser.add_argument("source")
    run_parser.add_argument("--input", help="file with ACCEPT input lines")
    run_parser.add_argument("--json", action="store_true", help="print a run report as JSON")
    run_parser.add_argument("--step-limit", type=int, default=DEFAULT_STEP_LIMIT)

    parse_parser = commands.add_parser("parse", help="parse a program and print a summary")
    parse_parser.add_argument("source")
    parse_parser.add_argument("--json", action="store_true")

    dry_parser = commands.add_parser("dry-run", help="parse only (alias of parse)")
    dry_parser.add_argument("source")

    diff_parser = commands.add_parser("diff", help="run the original and a port, then compare output")
    diff_parser.add_argument("source")
    diff_parser.add_argument("--port", required=True, help="command that runs the port, e.g. 'python port.py'")
    diff_parser.add_argument("--input", help="file with stdin for both programs")
    diff_parser.add_argument("--json", action="store_true")
    diff_parser.add_argument("--step-limit", type=int, default=DEFAULT_STEP_LIMIT)

    fetch_parser = commands.add_parser("fetch-ccvs", help="download NIST CCVS85 (never bundled)")
    fetch_parser.add_argument("--target", default="ccvs85.zip")
    fetch_parser.add_argument("--url", default=CCVS85_URL)

    conformance_parser = commands.add_parser("conformance", help="run .cbl/.out cases from a directory")
    conformance_parser.add_argument("--ccvs", required=True)
    conformance_parser.add_argument("--json", action="store_true")
    conformance_parser.add_argument("--step-limit", type=int, default=DEFAULT_STEP_LIMIT)

    doctor_parser = commands.add_parser("doctor", help="check the installation")
    doctor_parser.add_argument("--json", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    arguments = parser.parse_args(list(argv) if argv is not None else None)
    try:
        if arguments.command == "run":
            return _command_run(arguments)
        if arguments.command == "parse":
            return _command_parse(arguments)
        if arguments.command == "dry-run":
            return _command_dry_run(arguments)
        if arguments.command == "diff":
            return _command_diff(arguments)
        if arguments.command == "fetch-ccvs":
            return _command_fetch(arguments)
        if arguments.command == "conformance":
            return _command_conformance(arguments)
        if arguments.command == "doctor":
            return _command_doctor(arguments)
    except ParseError as error:
        print(f"parse error: {error}", file=sys.stderr)
        return EXIT_PARSE
    except StepLimitError as error:
        print(f"runtime error: {error}", file=sys.stderr)
        return EXIT_RUNTIME
    except RunError as error:
        print(f"runtime error: {error}", file=sys.stderr)
        return EXIT_RUNTIME
    except ConformanceError as error:
        print(f"conformance error: {error}", file=sys.stderr)
        return EXIT_CONFORMANCE
    except OracleError as error:
        print(f"error: {error}", file=sys.stderr)
        return EXIT_ORACLE
    except ConfigError as error:
        print(f"config error: {error}", file=sys.stderr)
        return EXIT_USAGE
    except CobolError as error:  # pragma: no cover - defensive
        print(f"error [{error.code}]: {error}", file=sys.stderr)
        return EXIT_RUNTIME
    raise AssertionError(f"unhandled command {arguments.command}")  # pragma: no cover


def _read_source(path: str) -> str:
    target = Path(path)
    try:
        size = target.stat().st_size
    except OSError as error:
        raise ConfigError(f"cannot read '{path}': {error}") from error
    if size > MAX_SOURCE_BYTES:
        raise ConfigError(f"'{path}' is larger than {MAX_SOURCE_BYTES} bytes")
    try:
        return target.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise ConfigError(f"cannot read '{path}': {error}") from error


def _read_input(path: str | None) -> str:
    if path is None:
        return ""
    return _read_source(path)


def _command_run(arguments: argparse.Namespace) -> int:
    source = _read_source(arguments.source)
    accept = _read_input(arguments.input).splitlines()
    interpreter = Interpreter(parse_program(source), accept_source=accept, step_limit=arguments.step_limit)
    interpreter.output = lambda text: print(text)
    interpreter.run()
    if arguments.json:
        print(json.dumps(interpreter.report(), ensure_ascii=False))
    return EXIT_OK


def _command_parse(arguments: argparse.Namespace) -> int:
    program = parse_program(_read_source(arguments.source))
    paragraph_names = [paragraph.name for paragraph in program.paragraphs if paragraph.name]
    payload: dict[str, Any] = {
        "program": program.program_id,
        "paragraphs": paragraph_names,
        "data_roots": len(program.data_roots),
    }
    if arguments.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(f"program: {program.program_id}")
        print(f"paragraphs: {', '.join(paragraph_names) or 'none'}")
        print(f"data roots: {len(program.data_roots)}")
    return EXIT_OK


def _command_dry_run(arguments: argparse.Namespace) -> int:
    program = parse_program(_read_source(arguments.source))
    print(f"parse ok: {program.program_id} ({len(program.paragraphs)} paragraph(s))")
    return EXIT_OK


def _command_diff(arguments: argparse.Namespace) -> int:
    source = _read_source(arguments.source)
    stdin_text = _read_input(arguments.input)
    original = run_original(source, stdin_text, arguments.step_limit)
    command = _split_command(arguments.port)
    port = run_port(command, stdin_text)
    result = compare(original, port)
    if arguments.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False))
    else:
        print("match" if result.match else f"mismatch: {result.difference}")
        if not result.match:
            print("--- original ---")
            print(result.original)
            print("--- port ---")
            print(result.port)
    return EXIT_OK if result.match else EXIT_RUNTIME


def _split_command(text: str) -> list[str]:
    import shlex

    if text.endswith(".py") and not text.startswith("python"):
        return default_port_command(text)
    try:
        return shlex.split(text)
    except ValueError as error:
        raise ConfigError(f"cannot parse the port command: {error}") from error


def _command_fetch(arguments: argparse.Namespace) -> int:
    path = fetch_ccvs(Path(arguments.target), arguments.url)
    print(f"downloaded {path}")
    return EXIT_OK


def _command_conformance(arguments: argparse.Namespace) -> int:
    results = run_conformance(Path(arguments.ccvs), arguments.step_limit)
    report = summarize(results)
    payload: dict[str, Any] = {"summary": report, "results": [result.to_dict() for result in results]}
    if arguments.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        for result in results:
            detail = f" ({result.detail})" if result.detail else ""
            print(f"{result.status:11} {result.name}{detail}")
        print(
            f"{report['passed']}/{report['total']} passed, {report['failed']} failed, "
            f"{report['unsupported']} unsupported"
        )
    return EXIT_OK if report["failed"] == 0 else EXIT_CONFORMANCE


def _command_doctor(arguments: argparse.Namespace) -> int:
    report = {
        "version": __version__,
        "python": sys.version.split()[0],
        "platform": sys.platform,
        "ccvs85_url": CCVS85_URL,
        "statements": [
            "MOVE",
            "ADD",
            "SUBTRACT",
            "MULTIPLY",
            "DIVIDE",
            "COMPUTE",
            "IF/ELSE",
            "PERFORM",
            "GO TO",
            "STOP RUN",
            "DISPLAY",
            "ACCEPT",
            "STRING",
            "UNSTRING",
            "INSPECT",
        ],
        "rounding": "ROUND_HALF_UP",
    }
    if arguments.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        print(f"cobrun {report['version']}")
        print(f"python: {report['python']} ({report['platform']})")
        print(f"rounding: {report['rounding']} (COBOL ROUNDED)")
        print("statements: " + ", ".join(report["statements"]))
        print(f"ccvs85: fetched at runtime, never bundled ({report['ccvs85_url']})")
        print("OK")
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
