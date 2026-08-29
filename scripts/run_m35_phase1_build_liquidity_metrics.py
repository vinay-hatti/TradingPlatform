from __future__ import annotations

import argparse

from trading_ai.database.session import create_session
from trading_ai.scanner.universe_management.liquidity_metrics_builder import (
    LiquidityMetricsBuildPolicy,
    LiquidityMetricsBuilder,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Build per-symbol liquidity metrics from the platform market-data workflow.")
    parser.add_argument("--universe-csv", default="data/universe/us_listed_equities_etfs.csv")
    parser.add_argument("--output-csv", default="data/market/liquidity_metrics.csv")
    parser.add_argument("--manifest-json", default="data/market/liquidity_metrics_manifest.json")
    parser.add_argument("--diagnostics-json", default="reports/m35/phase1/liquidity_metrics/build_diagnostics.json")
    parser.add_argument("--reference-csv", help="Optional symbol,market_cap,halted enrichment CSV.")
    parser.add_argument("--quote-csv", help="Optional symbol,bid,ask or bid_ask_spread_pct quote CSV.")
    parser.add_argument("--lookback-trading-days", type=int, default=20)
    parser.add_argument("--calendar-lookback-days", type=int, default=45)
    parser.add_argument("--minimum-price-observations", type=int, default=5)
    parser.add_argument("--allow-missing-price-history", action="store_true")
    args = parser.parse_args()
    policy = LiquidityMetricsBuildPolicy(
        lookback_trading_days=args.lookback_trading_days,
        calendar_lookback_days=args.calendar_lookback_days,
        minimum_price_observations=args.minimum_price_observations,
        require_price_history=not args.allow_missing_price_history,
    )
    session = create_session()
    try:
        result = LiquidityMetricsBuilder(policy).build(
            session=session, universe_csv=args.universe_csv, output_csv=args.output_csv,
            manifest_json=args.manifest_json, diagnostics_json=args.diagnostics_json,
            reference_csv=args.reference_csv, quote_csv=args.quote_csv,
        )
    finally:
        session.close()
    print("========== Liquidity Metrics Builder ==========")
    print(f"Status              : {result.status}")
    print(f"Universe symbols    : {result.universe_count}")
    print(f"Metrics published   : {result.metrics_count}")
    print(f"Missing price       : {result.missing_price_count}")
    print(f"Missing reference   : {result.missing_reference_count}")
    print(f"Missing options     : {result.missing_option_count}")
    print(f"Output              : {result.output_csv}")
    print(f"Manifest            : {result.manifest_json}")
    print(f"Diagnostics         : {result.diagnostics_json}")
    print(f"SHA256              : {result.sha256}")


if __name__ == "__main__":
    main()
