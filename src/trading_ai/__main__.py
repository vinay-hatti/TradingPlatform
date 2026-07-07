import argparse
import subprocess
import sys


def run_script(script, extra_args=None):

    cmd = [sys.executable, script]

    if extra_args:
        cmd.extend(extra_args)

    result = subprocess.run(cmd)

    raise SystemExit(result.returncode)


def main():

    parser = argparse.ArgumentParser(
        description="Trading AI command line"
    )

    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan")
    sub.add_parser("optimize")
    sub.add_parser("dashboard")
    sub.add_parser("daily")
    sub.add_parser("option-details")
    sub.add_parser("option-rankings")
    sub.add_parser("backtest-smoke")
    sub.add_parser("backtest-engine-test")
    sub.add_parser("backtest-datasource-test")
    sub.add_parser("strategy-runner-test")
    sub.add_parser("trade-generator-test")
    sub.add_parser("backtest")
    sub.add_parser("position-sizer-test")
    sub.add_parser("backtest-experiments")
    sub.add_parser("analyze-experiments")
    sub.add_parser("walkforward-splitter-test")
    sub.add_parser("walkforward-optimizer-test")
    sub.add_parser("walkforward-validator-test")
    sub.add_parser("walkforward")
    sub.add_parser("analyze-walkforward")
    sub.add_parser("walkforward-report")
    sub.add_parser("black-scholes-test")
    sub.add_parser("analyze-greeks")

    paper = sub.add_parser("paper")
    paper_sub = paper.add_subparsers(dest="paper_command")

    paper_sub.add_parser("run")
    paper_sub.add_parser("mark")
    paper_sub.add_parser("status")
    paper_sub.add_parser("reset")

    args, extra = parser.parse_known_args()

    if args.command == "scan":
        run_script("scripts/run_scanner.py", extra)

    elif args.command == "optimize":
        run_script("scripts/optimize_portfolio.py", extra)

    elif args.command == "dashboard":
        run_script("scripts/build_dashboard.py", extra)

    elif args.command == "daily":
        run_script("scripts/run_paper_daily.py", extra)

    elif args.command == "option-details":
        run_script("scripts/option_details.py", extra)

    elif args.command == "option-rankings":
        run_script("scripts/export_option_rankings.py", extra)

    elif args.command == "backtest-smoke":
        run_script("scripts/run_backtest_smoke.py", extra)

    elif args.command == "backtest-engine-test":
        run_script("scripts/test_backtest_engine.py", extra)

    elif args.command == "backtest-datasource-test":
        run_script("scripts/test_historical_datasource.py", extra)

    elif args.command == "strategy-runner-test":
        run_script("scripts/test_strategy_runner.py", extra)

    elif args.command == "trade-generator-test":
        run_script("scripts/test_trade_generator.py", extra)

    elif args.command == "backtest":
        run_script("scripts/run_historical_backtest.py", extra)

    elif args.command == "position-sizer-test":
        run_script("scripts/test_position_sizer.py", extra)

    elif args.command == "backtest-experiments":
        run_script("scripts/run_backtest_experiments.py", extra)

    elif args.command == "analyze-experiments":
        run_script("scripts/analyze_experiments.py", extra)

    elif args.command == "walkforward-splitter-test":
        run_script("scripts/test_walkforward_splitter.py", extra)

    elif args.command == "walkforward-optimizer-test":
        run_script(
            "scripts/test_walkforward_optimizer.py",
            extra,
        )

    elif args.command == "walkforward-validator-test":
        run_script("scripts/test_walkforward_validator.py", extra)

    elif args.command == "walkforward":
        run_script("scripts/run_walkforward.py", extra)

    elif args.command == "analyze-walkforward":
        run_script("scripts/analyze_walkforward.py", extra)

    elif args.command == "walkforward-report":
        run_script("scripts/build_walkforward_report.py", extra)

    elif args.command == "black-scholes-test":
        run_script("scripts/test_black_scholes.py", extra)

    elif args.command == "analyze-greeks":
        run_script("scripts/analyze_greeks.py", extra)

    elif args.command == "paper":

        if args.paper_command == "run":
            run_script("scripts/paper_trade_from_optimizer.py", extra)

        elif args.paper_command == "mark":
            run_script("scripts/mark_paper_positions.py", extra)

        elif args.paper_command == "status":
            run_script("scripts/paper_status.py", extra)

        elif args.paper_command == "reset":
            run_script("scripts/reset_paper.py", extra)

        else:
            parser.print_help()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
