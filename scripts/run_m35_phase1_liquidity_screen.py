from __future__ import annotations

import argparse

from trading_ai.scanner.universe_management import LiquidityGovernancePolicy, LiquidityGovernanceService


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply institutional liquidity governance to the canonical universe.")
    parser.add_argument("--universe-csv", default="data/universe/us_listed_equities_etfs.csv")
    parser.add_argument("--metrics-csv", required=True, help="CSV containing current per-symbol liquidity metrics.")
    parser.add_argument("--output-dir", default="data/universe")
    parser.add_argument("--report-dir", default="reports/m35/phase1/liquidity")
    parser.add_argument("--minimum-price", type=float, default=5.0)
    parser.add_argument("--maximum-price", type=float, default=5000.0)
    parser.add_argument("--minimum-average-volume", type=int, default=200000)
    parser.add_argument("--minimum-dollar-volume", type=float, default=10000000.0)
    parser.add_argument("--maximum-spread-pct", type=float, default=0.05)
    parser.add_argument("--minimum-market-cap", type=float, default=300000000.0)
    parser.add_argument("--minimum-option-volume", type=int, default=0)
    parser.add_argument("--minimum-option-open-interest", type=int, default=0)
    parser.add_argument("--require-options-eligible", action="store_true")
    parser.add_argument("--exclude-etfs", action="store_true")
    parser.add_argument("--maximum-market-data-age-hours", type=int, default=48)
    parser.add_argument("--review-missing-metrics", action="store_true")
    args = parser.parse_args()
    policy = LiquidityGovernancePolicy(
        minimum_price=args.minimum_price, maximum_price=args.maximum_price,
        minimum_average_daily_volume=args.minimum_average_volume,
        minimum_average_daily_dollar_volume=args.minimum_dollar_volume,
        maximum_bid_ask_spread_pct=args.maximum_spread_pct,
        minimum_market_cap=args.minimum_market_cap,
        minimum_option_volume=args.minimum_option_volume,
        minimum_option_open_interest=args.minimum_option_open_interest,
        require_options_eligible=args.require_options_eligible, allow_etfs=not args.exclude_etfs,
        maximum_market_data_age_hours=args.maximum_market_data_age_hours,
        missing_metric_action="REVIEW" if args.review_missing_metrics else "REJECT",
    )
    result = LiquidityGovernanceService(policy).screen(universe_csv=args.universe_csv, metrics_csv=args.metrics_csv, output_dir=args.output_dir, report_dir=args.report_dir)
    print("========== Institutional Liquidity Governance ==========")
    print(f"Status          : {result.status}")
    print(f"Evaluated       : {result.evaluated_count}")
    print(f"Eligible        : {result.eligible_count}")
    print(f"Rejected        : {result.rejected_count}")
    print(f"Review          : {result.review_count}")
    print(f"Missing metrics : {result.missing_metrics_count}")
    print(f"Stale metrics   : {result.stale_metrics_count}")
    for reason, count in sorted(result.rejection_breakdown.items(), key=lambda pair: (-pair[1], pair[0])):
        print(f"{reason:<38}: {count}")


if __name__ == "__main__":
    main()
