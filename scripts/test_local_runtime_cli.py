from __future__ import annotations

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from trading_ai.__main__ import PAPER_COMMANDS, SCRIPT_COMMANDS, build_parser


def main() -> None:
    expected = {
        "ingest-market",
        "build-features",
        "generate-signals",
        "full-system",
        "dashboard-server",
        "local-doctor",
        "start",
    }
    assert expected.issubset(SCRIPT_COMMANDS)
    assert {"run", "mark", "status", "reset"} == set(PAPER_COMMANDS)

    assert SCRIPT_COMMANDS["ingest-market"] == "run_market_ingestion.py"
    assert SCRIPT_COMMANDS["build-features"] == "run_indicators.py"
    assert SCRIPT_COMMANDS["generate-signals"] == "run_daily_scan.py"
    assert SCRIPT_COMMANDS["full-system"] == "run_full_system.py"
    assert SCRIPT_COMMANDS["dashboard-server"] == "run_dashboard.py"

    parser = build_parser()
    assert parser.parse_known_args(
        ["start", "--mode", "paper"]
    )[0].command == "start"
    assert parser.parse_known_args(
        ["paper", "status"]
    )[0].paper_command == "status"
    assert parser.parse_known_args(
        ["paper-trading"]
    )[0].alias_script.endswith("paper_trade_from_optimizer.py")

    for new_script in (
        "scripts/local_setup_check.py",
        "scripts/run_local_platform.py",
    ):
        assert (ROOT / new_script).exists(), new_script

    print("All local runtime CLI registration assertions passed.")


if __name__ == "__main__":
    main()
