from __future__ import annotations

import argparse
import subprocess
import sys


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--refresh-mode", choices=["cache_only", "refresh_missing", "force_full"], required=True)
    parser.add_argument("--auto-refresh", action="store_true")
    parser.add_argument("--minimum-refresh-coverage-pct", type=float, default=98.0)
    parser.add_argument("--maximum-failed-refresh-symbols", type=int, default=10)
    parser.add_argument("--refresh-max-retries", type=int, default=3)
    parser.add_argument("--refresh-retry-backoff-seconds", type=float, default=2.0)
    parser.add_argument("--refresh-maximum-retry-backoff-seconds", type=float, default=60.0)
    parser.add_argument("--refresh-retry-jitter-ratio", type=float, default=0.20)
    parser.add_argument("--refresh-rate-limit-cooldown-seconds", type=float, default=15.0)
    parser.add_argument("--refresh-circuit-breaker-threshold", type=int, default=3)
    parser.add_argument("--refresh-circuit-breaker-cooldown-seconds", type=float, default=30.0)
    degraded = parser.add_mutually_exclusive_group()
    degraded.add_argument("--continue-on-degraded-refresh", dest="continue_on_degraded", action="store_true")
    degraded.add_argument("--block-on-degraded-refresh", dest="continue_on_degraded", action="store_false")
    parser.set_defaults(continue_on_degraded=True)
    args, rest = parser.parse_known_args()

    def value(flag: str, default: str | None = None) -> str | None:
        try:
            return rest[rest.index(flag) + 1]
        except (ValueError, IndexError):
            return default

    if args.auto_refresh:
        refresh = [
            sys.executable,
            "scripts/run_m43_refresh_market_data.py",
            "--mode", args.refresh_mode,
            "--universe", value("--universe", "liquid-us-700") or "liquid-us-700",
            "--start", value("--start") or "",
            "--end", value("--end") or "",
            "--minimum-coverage-pct", str(args.minimum_refresh_coverage_pct),
            "--maximum-failed-symbols", str(args.maximum_failed_refresh_symbols),
            "--max-retries", str(args.refresh_max_retries),
            "--retry-backoff-seconds", str(args.refresh_retry_backoff_seconds),
            "--maximum-retry-backoff-seconds", str(args.refresh_maximum_retry_backoff_seconds),
            "--retry-jitter-ratio", str(args.refresh_retry_jitter_ratio),
            "--rate-limit-cooldown-seconds", str(args.refresh_rate_limit_cooldown_seconds),
            "--circuit-breaker-threshold", str(args.refresh_circuit_breaker_threshold),
            "--circuit-breaker-cooldown-seconds", str(args.refresh_circuit_breaker_cooldown_seconds),
        ]
        refresh.append("--continue-on-degraded" if args.continue_on_degraded else "--block-on-degraded")
        symbols = value("--symbols")
        if symbols:
            refresh += ["--symbols", symbols]
        print("========== Pre-Scan Data Refresh ==========")
        result = subprocess.run(refresh, check=False)
        if result.returncode != 0:
            print(
                f"Pre-scan refresh did not meet governance thresholds (exit code {result.returncode}); "
                "scan was not started."
            )
            return result.returncode
        print("Pre-scan OHLCV refresh met governance thresholds.")

        if args.refresh_mode != "cache_only":
            option_refresh = [
                sys.executable,
                "scripts/run_market_ingestion.py",
                "--data-scope", "options",
                "--end", value("--end") or "",
                "--continue-on-error",
            ]
            if args.refresh_mode == "force_full":
                option_refresh.append("--force-refresh")
            if symbols:
                option_refresh += ["--symbols", symbols]
            print("========== Pre-Scan Polygon Options Refresh ==========")
            option_result = subprocess.run(option_refresh, check=False)
            if option_result.returncode != 0:
                print(
                    f"Pre-scan options ingestion failed (exit code {option_result.returncode}); "
                    "scan was not started because live mode requires persisted Polygon data."
                )
                return option_result.returncode
        print("Pre-scan ingestion completed; starting cache/database-only daily scan.")

    scan = [sys.executable, "scripts/run_daily_scan.py", *rest]
    # Auto-refresh has already populated and governed the cache. Keep the scan
    # cache-only so one excluded symbol cannot fan out into hundreds of Polygon
    # fallback requests. Network fallback remains available when auto-refresh is
    # explicitly disabled.
    if not args.auto_refresh and args.refresh_mode != "cache_only" and "--allow-network" not in scan:
        scan.append("--allow-network")
    return subprocess.run(scan, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
