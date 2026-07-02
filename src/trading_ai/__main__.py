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
