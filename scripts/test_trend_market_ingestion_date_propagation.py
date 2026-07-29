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


def main() -> None:
    module = _load_module()
    captured: list[tuple[str, list[str]]] = []

    def capture(name: str, command: list[str]) -> None:
        captured.append((name, command))

    module._run_command_stage = capture
    args = Namespace(
        skip_trend_intelligence=False,
        symbols="AAPL,MSFT",
        symbols_file=None,
        start=None,
        end=None,
        trend_platform_report="reports/trend_intelligence/platform_integration_latest.json",
    )

    assert module._run_trend_intelligence_pipeline(args, ("AAPL", "MSFT")) is True
    stage_commands = {name: command for name, command in captured}
    institutional = stage_commands["institutional participation"]
    assert "--end" in institutional
    end_index = institutional.index("--end")
    assert institutional[end_index + 1] == date.today().isoformat()

    # A caller-supplied end date must be preserved exactly.
    captured.clear()
    args.end = "2026-07-28"
    assert module._run_trend_intelligence_pipeline(args, ("AAPL", "MSFT")) is True
    stage_commands = {name: command for name, command in captured}
    for name in ("trend state", "trend transitions", "trend forecasts", "institutional participation"):
        command = stage_commands[name]
        end_index = command.index("--end")
        assert command[end_index + 1] == "2026-07-28"

    print("All Trend Market Ingestion date propagation assertions passed.")


if __name__ == "__main__":
    main()
