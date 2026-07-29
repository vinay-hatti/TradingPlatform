from __future__ import annotations

import importlib.util
from argparse import Namespace
from datetime import date
from pathlib import Path


def _load_module():
    path = Path(__file__).with_name("run_market_ingestion.py")
    spec = importlib.util.spec_from_file_location("m52_market_ingestion", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _capture_commands(module, args):
    captured: list[tuple[str, list[str]]] = []
    module._run_command_stage = lambda name, command: captured.append((name, command))
    assert module._run_trend_intelligence_pipeline(args, ("AAPL", "MSFT")) is True
    return {name: command for name, command in captured}


def _assert_absent(command: list[str], *flags: str) -> None:
    for flag in flags:
        assert flag not in command, f"{flag} unexpectedly present in {command}"


def main() -> None:
    module = _load_module()
    args = Namespace(
        skip_trend_intelligence=False,
        symbols="AAPL,MSFT",
        symbols_file=None,
        start="2025-01-01",
        end=None,
        trend_platform_report="reports/trend_intelligence/platform_integration_latest.json",
    )

    commands = _capture_commands(module, args)
    phase1 = commands["trend state"]
    phase2 = commands["trend transitions"]
    phase3 = commands["trend forecasts"]
    phase4 = commands["institutional participation"]

    for command in (phase1, phase2):
        assert command[2:] == ["--symbols", "AAPL,MSFT"]
        _assert_absent(command, "--start", "--end")

    for command in (phase3, phase4):
        assert command[command.index("--symbols") + 1] == "AAPL,MSFT"
        assert command[command.index("--start") + 1] == "2025-01-01"
        assert command[command.index("--end") + 1] == date.today().isoformat()

    args.end = "2026-07-28"
    commands = _capture_commands(module, args)
    for name in ("trend forecasts", "institutional participation"):
        command = commands[name]
        assert command[command.index("--end") + 1] == "2026-07-28"
    for name in ("trend state", "trend transitions"):
        _assert_absent(commands[name], "--start", "--end")

    print("All Trend Market Ingestion stage CLI contract assertions passed.")


if __name__ == "__main__":
    main()
