from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser(description="Governed Yahoo OHLCV and Polygon options ingestion workflow.")
    parser.add_argument("--data-scope", choices=["underlying", "options", "all"], default="all")
    parser.add_argument("--refresh-mode", choices=["cache_only", "refresh_missing", "force_full"], default="refresh_missing")
    parser.add_argument("--universe", default="liquid-us-700")
    parser.add_argument("--symbols")
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--minimum-bars", type=int, default=20)
    parser.add_argument("--stale-after-days", type=int, default=1)
    parser.add_argument("--minimum-coverage-pct", type=float, default=98.0)
    parser.add_argument("--maximum-failed-symbols", type=int, default=10)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--retry-backoff-seconds", type=float, default=2.0)
    parser.add_argument("--maximum-retry-backoff-seconds", type=float, default=60.0)
    parser.add_argument("--retry-jitter-ratio", type=float, default=.20)
    parser.add_argument("--rate-limit-cooldown-seconds", type=float, default=15.0)
    parser.add_argument("--circuit-breaker-threshold", type=int, default=3)
    parser.add_argument("--circuit-breaker-cooldown-seconds", type=float, default=30.0)
    parser.add_argument("--batch-size", type=int, default=100)
    degraded = parser.add_mutually_exclusive_group()
    degraded.add_argument("--continue-on-degraded", dest="continue_on_degraded", action="store_true")
    degraded.add_argument("--block-on-degraded", dest="continue_on_degraded", action="store_false")
    parser.set_defaults(continue_on_degraded=True)
    args = parser.parse_args()

    if args.refresh_mode == "cache_only":
        print("Cache-only selected: no provider ingestion was performed.")
        return 0

    if args.data_scope in {"underlying", "all"}:
        command = [
            sys.executable, "scripts/run_m43_refresh_market_data.py",
            "--mode", args.refresh_mode, "--universe", args.universe,
            "--start", args.start, "--end", args.end,
            "--minimum-bars", str(args.minimum_bars),
            "--stale-after-days", str(args.stale_after_days),
            "--minimum-coverage-pct", str(args.minimum_coverage_pct),
            "--maximum-failed-symbols", str(args.maximum_failed_symbols),
            "--max-retries", str(args.max_retries),
            "--retry-backoff-seconds", str(args.retry_backoff_seconds),
            "--maximum-retry-backoff-seconds", str(args.maximum_retry_backoff_seconds),
            "--retry-jitter-ratio", str(args.retry_jitter_ratio),
            "--rate-limit-cooldown-seconds", str(args.rate_limit_cooldown_seconds),
            "--circuit-breaker-threshold", str(args.circuit_breaker_threshold),
            "--circuit-breaker-cooldown-seconds", str(args.circuit_breaker_cooldown_seconds),
            "--batch-size", str(args.batch_size),
            "--continue-on-degraded" if args.continue_on_degraded else "--block-on-degraded",
        ]
        if args.symbols:
            command += ["--symbols", args.symbols]
        print("========== Yahoo Underlying OHLCV Ingestion ==========")
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return result.returncode

    if args.data_scope in {"options", "all"}:
        command = [
            sys.executable, "scripts/run_market_ingestion.py",
            "--data-scope", "options", "--end", args.end, "--continue-on-error",
        ]
        if args.refresh_mode == "force_full":
            command.append("--force-refresh")
        if args.symbols:
            command += ["--symbols", args.symbols]
        print("========== Polygon Options Ingestion ==========")
        result = subprocess.run(command, check=False)
        if result.returncode != 0:
            return result.returncode

    print("Market ingestion workflow completed. Daily Scanner can now use persisted data only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
