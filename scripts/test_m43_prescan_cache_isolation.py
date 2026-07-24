from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_m43_daily_scan_workflow import main


class Completed:
    returncode = 0


def run_case(auto_refresh: bool, refresh_mode: str = "refresh_missing") -> list[list[str]]:
    commands: list[list[str]] = []

    def fake_run(command, check=False):
        commands.append(list(command))
        return Completed()

    argv = [
        "run_m43_daily_scan_workflow.py",
        "--refresh-mode", refresh_mode,
        "--universe", "sp500-top100",
        "--start", "2025-07-23",
        "--end", "2026-07-23",
    ]
    if auto_refresh:
        argv.append("--auto-refresh")

    with (
        patch.object(sys, "argv", argv),
        patch(
            "scripts.run_m43_daily_scan_workflow.subprocess.run",
            side_effect=fake_run,
        ),
    ):
        assert main() == 0
    return commands


def command_script(command: list[str]) -> str:
    assert len(command) >= 2, command
    return command[1]


def main_test() -> None:
    # refresh_missing + auto-refresh intentionally runs:
    #   1. governed Yahoo OHLCV refresh
    #   2. persisted Polygon options ingestion
    #   3. cache/database-only daily scan
    auto_commands = run_case(True)
    assert len(auto_commands) == 3, auto_commands

    ohlcv_refresh, options_refresh, auto_scan = auto_commands
    assert command_script(ohlcv_refresh) == "scripts/run_m43_refresh_market_data.py", ohlcv_refresh
    assert "--mode" in ohlcv_refresh and "refresh_missing" in ohlcv_refresh, ohlcv_refresh

    assert command_script(options_refresh) == "scripts/run_market_ingestion.py", options_refresh
    assert "--data-scope" in options_refresh and "options" in options_refresh, options_refresh

    assert command_script(auto_scan) == "scripts/run_daily_scan.py", auto_scan
    assert "--allow-network" not in auto_scan, auto_scan

    # Without auto-refresh, one scan command is launched and the legacy explicit
    # network path remains available for refresh_missing/force_full operation.
    manual_commands = run_case(False)
    assert len(manual_commands) == 1, manual_commands
    manual_scan = manual_commands[0]
    assert command_script(manual_scan) == "scripts/run_daily_scan.py", manual_scan
    assert "--allow-network" in manual_scan, manual_scan

    # cache_only must never launch provider ingestion or permit network access,
    # even when the auto-refresh toggle is present.
    cache_only_commands = run_case(True, refresh_mode="cache_only")
    assert len(cache_only_commands) == 2, cache_only_commands
    cache_refresh, cache_scan = cache_only_commands
    assert command_script(cache_refresh) == "scripts/run_m43_refresh_market_data.py", cache_refresh
    assert command_script(cache_scan) == "scripts/run_daily_scan.py", cache_scan
    assert all("scripts/run_market_ingestion.py" not in command for command in cache_only_commands)
    assert "--allow-network" not in cache_scan, cache_scan

    print("Milestone 43 pre-scan cache isolation assertions passed.")


if __name__ == "__main__":
    main_test()
