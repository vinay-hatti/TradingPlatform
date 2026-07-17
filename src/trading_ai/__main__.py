from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys
from typing import Sequence

PROJECT_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = PROJECT_ROOT / "scripts"


SCRIPT_COMMANDS: dict[str, str] = {
    "scan": "run_scanner.py",
    "optimize": "optimize_portfolio.py",
    "dashboard": "build_dashboard.py",
    "daily": "run_paper_daily.py",
    "option-details": "option_details.py",
    "option-rankings": "export_option_rankings.py",
    "backtest-smoke": "run_backtest_smoke.py",
    "backtest-engine-test": "test_backtest_engine.py",
    "backtest-datasource-test": "test_historical_datasource.py",
    "strategy-runner-test": "test_strategy_runner.py",
    "trade-generator-test": "test_trade_generator.py",
    "backtest": "run_historical_backtest.py",
    "position-sizer-test": "test_position_sizer.py",
    "backtest-experiments": "run_backtest_experiments.py",
    "analyze-experiments": "analyze_experiments.py",
    "walkforward-splitter-test": "test_walkforward_splitter.py",
    "walkforward-optimizer-test": "test_walkforward_optimizer.py",
    "walkforward-validator-test": "test_walkforward_validator.py",
    "walkforward": "run_walkforward.py",
    "analyze-walkforward": "analyze_walkforward.py",
    "walkforward-report": "build_walkforward_report.py",
    "black-scholes-test": "test_black_scholes.py",
    "analyze-greeks": "analyze_greeks.py",
    "score-strategies": "score_strategies.py",
    "optimization-report": "build_optimization_report.py",
    "profile-comparison": "build_profile_comparison_report.py",
    "select-live-profile": "select_live_profile.py",
    "show-live-profile": "show_live_profile.py",
    "daily-scan": "run_daily_scan.py",
    "risk-metrics-test": "test_risk_metrics.py",
    "show-risk-metrics": "show_risk_metrics.py",
    "score-risk-aware": "score_risk_aware_strategies.py",
    "risk-optimization-report": "risk_optimization_report.py",
    "import-option-chain": "import_option_chain.py",
    "test-option-pricing": "test_option_pricing_service.py",
    "compare-option-pricing": "compare_option_pricing_sources.py",
    "volatility-test": "test_volatility_engine.py",
    "strategy-selector-test": "test_strategy_selector.py",
    "strike-optimizer-test": "test_strike_optimizer.py",
    "expiration-optimizer-test": "test_expiration_optimizer.py",
    "expected-move-test": "test_expected_move_engine.py",
    "strategy-scoring-test": "test_strategy_scoring_engine.py",
    "institutional-ranking-test": "test_institutional_ranking_engine.py",
    "multi-strategy-test": "test_multi_strategy_support.py",
    "portfolio-construction-test": "test_portfolio_construction.py",
    "institutional-decision-test": "test_institutional_decision_engine.py",
    "probability-engine-test": "test_probability_engine.py",
    "scenario-engine-test": "test_scenario_engine.py",
    "distribution-risk-test": "test_distribution_risk_engine.py",
    # Existing runnable workflows that were missing from the root CLI.
    "ingest-market": "run_market_ingestion.py",
    "build-features": "run_indicators.py",
    "generate-signals": "run_daily_scan.py",
    "full-system": "run_full_system.py",
    "options-run": "run_options.py",
    "dashboard-server": "run_dashboard.py",
    "local-doctor": "local_setup_check.py",
    "start": "run_local_platform.py",
}

PAPER_COMMANDS: dict[str, str] = {
    "run": "paper_trade_from_optimizer.py",
    "mark": "mark_paper_positions.py",
    "status": "paper_status.py",
    "reset": "reset_paper.py",
}


def run_script(script_name: str, extra_args: Sequence[str] = ()) -> int:
    script = SCRIPTS_DIR / script_name
    if not script.is_file():
        print(
            f"ERROR: required script does not exist: {script}",
            file=sys.stderr,
        )
        return 2
    command = [sys.executable, str(script), *extra_args]
    completed = subprocess.run(command, cwd=PROJECT_ROOT)
    return int(completed.returncode)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="trading-ai",
        description="Trading AI local command line",
    )
    subparsers = parser.add_subparsers(dest="command")

    help_text = {
        "ingest-market": "Download and persist configured market data.",
        "build-features": "Run the repository's indicator/feature workflow.",
        "generate-signals": "Run the daily scan and signal workflow.",
        "full-system": "Run scanner, options construction, and portfolio assembly.",
        "dashboard-server": "Start the Streamlit dashboard runner.",
        "local-doctor": "Check local Mac configuration and dependencies.",
        "start": "Run the local platform workflow orchestrator.",
    }

    for command in SCRIPT_COMMANDS:
        subparsers.add_parser(
            command,
            help=help_text.get(command),
            add_help=False,
        )

    paper = subparsers.add_parser("paper", help="Paper-trading operations.")
    paper_subparsers = paper.add_subparsers(dest="paper_command")
    for command in PAPER_COMMANDS:
        paper_subparsers.add_parser(command, add_help=False)

    aliases = subparsers.add_parser(
        "paper-trading",
        help="Alias for `paper run`.",
        add_help=False,
    )
    aliases.set_defaults(alias_script=PAPER_COMMANDS["run"])
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args, extra = parser.parse_known_args(argv)

    alias_script = getattr(args, "alias_script", None)
    if alias_script:
        return run_script(alias_script, extra)

    if args.command in SCRIPT_COMMANDS:
        return run_script(SCRIPT_COMMANDS[args.command], extra)

    if args.command == "paper":
        if args.paper_command in PAPER_COMMANDS:
            return run_script(PAPER_COMMANDS[args.paper_command], extra)
        paper_parser = next(
            action
            for action in parser._actions
            if isinstance(action, argparse._SubParsersAction)
        ).choices["paper"]
        paper_parser.print_help()
        return 2

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
