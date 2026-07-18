from __future__ import annotations

import argparse
from datetime import date, timedelta

from trading_ai.app.bootstrap import container
from trading_ai.backtest.datasource import HistoricalDataSource
from trading_ai.daily.live_profile import LiveProfileLoader
from trading_ai.daily.recommender import LiveTradeRecommender
from trading_ai.daily.reporter import DailyRecommendationReporter
from trading_ai.daily.scanner import DailyScanner
from trading_ai.daily.trade_reporter import LiveTradeCandidateReporter
from trading_ai.market.universe import get_universe
from trading_ai.portfolio.awareness import PortfolioAwareness


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    today = date.today()
    default_start = (today - timedelta(days=365)).isoformat()
    default_end = today.isoformat()

    parser = argparse.ArgumentParser(
        description="Run the daily AI options trade scanner."
    )
    parser.add_argument(
        "--universe",
        default="sp500-top100",
        help="Named universe. Default: sp500-top100.",
    )
    parser.add_argument(
        "--symbols",
        default=None,
        help=(
            "Optional comma-separated symbols. When supplied, overrides "
            "--universe."
        ),
    )
    parser.add_argument(
        "--start",
        default=default_start,
        help=f"Historical-data start date. Default: {default_start}.",
    )
    parser.add_argument(
        "--end",
        default=default_end,
        help=f"Historical-data end date. Default: {default_end}.",
    )
    parser.add_argument("--min-score", type=float, default=60.0)
    parser.add_argument(
        "--top",
        type=int,
        default=10,
        help="Maximum ranked candidates converted into trade ideas.",
    )
    parser.add_argument("--pricing-dte", type=int, default=30)
    parser.add_argument("--option-data-mode", choices=["live", "auto", "proxy"], default="live")
    parser.add_argument("--max-option-spread-pct", type=float, default=0.25)
    parser.add_argument("--min-option-open-interest", type=int, default=100)
    parser.add_argument("--min-option-volume", type=int, default=10)
    parser.add_argument("--option-delta-weight", type=float, default=0.25)
    parser.add_argument("--option-expiration-weight", type=float, default=0.15)
    parser.add_argument("--option-strike-weight", type=float, default=0.10)
    parser.add_argument("--option-spread-weight", type=float, default=0.15)
    parser.add_argument("--option-oi-weight", type=float, default=0.20)
    parser.add_argument("--option-volume-weight", type=float, default=0.15)
    parser.add_argument("--liquidity-data-mode", choices=["adaptive", "strict"], default="adaptive")
    parser.add_argument("--capital", type=float, default=100000.0)
    parser.add_argument("--risk-per-trade-pct", type=float, default=0.02)
    parser.add_argument("--max-position-pct", type=float, default=0.05)
    parser.add_argument("--take-profit-pct", type=float, default=0.30)
    parser.add_argument("--stop-loss-pct", type=float, default=0.15)
    parser.add_argument(
        "--positions-file",
        default="data/portfolio/current_positions.csv",
    )
    parser.add_argument(
        "--allow-network",
        action="store_true",
        help=(
            "Allow Polygon fallback when cache is missing. "
            "Default is cache-only."
        ),
    )
    parser.add_argument(
        "--report-date",
        default=None,
        help="Report-date folder; defaults to today.",
    )
    return parser.parse_args(argv)


def resolve_symbols(args: argparse.Namespace) -> list[str]:
    if args.symbols:
        symbols = [
            symbol.strip().upper().replace("_", ".")
            for symbol in args.symbols.split(",")
            if symbol.strip()
        ]
    else:
        symbols = list(get_universe(args.universe))

    symbols = list(dict.fromkeys(symbols))
    if not symbols:
        raise ValueError("No symbols were selected for scanning")
    return symbols


def print_candidate(index: int, candidate) -> None:
    print()
    print(f"{index}. {candidate.symbol} {candidate.signal}")
    print(f"   Strategy       : {candidate.strategy}")
    print(f"   Sector         : {candidate.sector}")
    print(f"   AI Score       : {candidate.ai_score:.2f}")
    print(f"   Adjusted Score : {candidate.adjusted_score:.2f}")
    print(f"   Base Score     : {candidate.final_score:.2f}")
    print(f"   Signal Score   : {candidate.score:.2f}")
    print(
        f"   Call / Put     : "
        f"{candidate.call_score:.2f} / {candidate.put_score:.2f}"
    )
    print(f"   Market Regime  : {candidate.market_regime}")
    print(f"   Underlying     : ${candidate.close:.2f}")
    print(f"   Strike         : ${candidate.strike:.2f}")
    print(f"   Contract       : {candidate.contract_ticker or 'PROXY'}")
    print(f"   Expiration     : {candidate.expiry}")
    print(f"   Bid / Ask      : ${candidate.bid:.2f} / ${candidate.ask:.2f}")
    print(f"   Price Source   : {candidate.price_source}")
    print(f"   Data Source    : {candidate.option_data_source}")
    print(f"   Quote Time     : {candidate.quote_timestamp or 'unavailable'}")
    print(f"   Option Price   : ${candidate.option_price:.2f}")
    print(f"   Expiration   : {candidate.expiry}")
    print(f"   DTE            : {candidate.dte}")
    print(f"   Expiry Source  : {candidate.expiry_source}")
    print(f"   Ranking Reason : {candidate.ranking_reason}")
    if candidate.portfolio_notes:
        print("   Portfolio Notes:")
        for note in candidate.portfolio_notes:
            print(f"     - {note}")


def print_trade(index: int, trade) -> None:
    print()
    print(f"{index}. LIVE TRADE CANDIDATE — {trade.symbol} {trade.signal}")
    print(f"   Confidence  : {trade.confidence}")
    print(f"   AI Score    : {trade.ai_score:.2f}")
    print(f"   Strategy    : {trade.strategy}")
    print(f"   Underlying  : ${trade.underlying_price:.2f}")
    print(f"   Strike      : ${trade.strike:.2f}")
    print(f"   Contract    : {trade.contract_ticker or 'PROXY'}")
    print(f"   Expiration  : {trade.expiry}")
    print(f"   Bid / Ask   : ${trade.bid:.2f} / ${trade.ask:.2f}")
    print(f"   Price Src   : {trade.price_source}")
    print(f"   Quote Time  : {trade.quote_timestamp or 'unavailable'}")
    print(f"   Expiration  : {trade.expiry}")
    print(f"   DTE         : {trade.dte}")
    print(f"   Expiry Src  : {trade.expiry_source}")
    print(f"   Entry       : ${trade.option_entry:.2f}")
    print(f"   Target      : ${trade.target_price:.2f}")
    print(f"   Stop        : ${trade.stop_price:.2f}")
    print(f"   Contracts   : {trade.contracts}")
    print(f"   Est. Cost   : ${trade.estimated_cost:,.2f}")
    print(f"   Max Risk    : ${trade.max_risk:,.2f}")
    print(f"   Est. Reward : ${trade.estimated_reward:,.2f}")
    print(f"   Reward/Risk : {trade.reward_risk_ratio:.2f}")
    print(f"   Regime      : {trade.market_regime}")
    print(f"   Reason      : {trade.ranking_reason}")
    if trade.trade_notes:
        print("   Notes:")
        for note in trade.trade_notes:
            print(f"     - {note}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    symbols = resolve_symbols(args)

    if args.top <= 0:
        raise ValueError("--top must be positive")
    if args.pricing_dte <= 0:
        raise ValueError("--pricing-dte must be positive")
    if args.start > args.end:
        raise ValueError("--start cannot be after --end")

    live_profile = LiveProfileLoader().load()
    datasource = HistoricalDataSource(
        container.market,
        cache_only=not args.allow_network,
    )
    portfolio = PortfolioAwareness(
        positions_file=args.positions_file,
    )

    scanner = DailyScanner(
        market_service=datasource,
        feature_pipeline=container.pipeline,
        live_profile=live_profile,
        portfolio_awareness=portfolio,
        min_score=args.min_score,
        pricing_dte=args.pricing_dte,
        start=args.start,
        end=args.end,
        option_data_mode=args.option_data_mode,
        maximum_option_spread_pct=args.max_option_spread_pct,
        minimum_option_open_interest=args.min_option_open_interest,
        minimum_option_volume=args.min_option_volume,
        delta_weight=args.option_delta_weight,
        expiration_weight=args.option_expiration_weight,
        strike_weight=args.option_strike_weight,
        spread_weight=args.option_spread_weight,
        open_interest_weight=args.option_oi_weight,
        volume_weight=args.option_volume_weight,
        liquidity_data_mode=args.liquidity_data_mode,
    )

    print()
    print("========== Daily AI Trading Scan ==========")
    print(f"Universe        : {args.universe if not args.symbols else 'custom'}")
    print(f"Symbols Selected: {len(symbols)}")
    print(f"History         : {args.start} -> {args.end}")
    print(f"Minimum Score   : {args.min_score}")
    print(f"Option Data     : {args.option_data_mode}")
    print(
        f"Data Mode       : "
        f"{'network allowed' if args.allow_network else 'cache only'}"
    )
    print("-------------------------------------------")

    candidates = scanner.scan(symbols)

    recommender = LiveTradeRecommender(
        capital=args.capital,
        risk_per_trade_pct=args.risk_per_trade_pct,
        max_position_pct=args.max_position_pct,
        take_profit_pct=args.take_profit_pct,
        stop_loss_pct=args.stop_loss_pct,
    )
    live_trades = recommender.build_many(candidates[: args.top])

    portfolio_summary = portfolio.exposure_summary()
    metadata = {
        "date": args.report_date or date.today().isoformat(),
        "universe": args.universe if not args.symbols else "custom",
        "symbols": symbols,
        "symbols_scanned": len(symbols),
        "candidates": len(candidates),
        "live_trade_candidates": len(live_trades),
        "live_profile": live_profile.get("profile", "unknown"),
        "min_score": args.min_score,
        "pricing_dte": args.pricing_dte,
        "start": args.start,
        "end": args.end,
        "positions_file": args.positions_file,
        "data_mode": (
            "network_allowed" if args.allow_network else "cache_only"
        ),
    }

    recommendation_paths = DailyRecommendationReporter().generate(
        candidates=candidates,
        metadata=metadata,
        portfolio_summary=portfolio_summary,
        report_date=args.report_date,
    )

    trade_metadata = dict(metadata)
    trade_metadata.update(
        {
            "capital": args.capital,
            "risk_per_trade_pct": args.risk_per_trade_pct,
            "max_position_pct": args.max_position_pct,
            "take_profit_pct": args.take_profit_pct,
            "stop_loss_pct": args.stop_loss_pct,
        }
    )
    trade_paths = LiveTradeCandidateReporter().generate(
        trades=live_trades,
        metadata=trade_metadata,
        report_date=args.report_date,
    )

    print()
    print(f"Symbols Scanned : {len(symbols)}")
    print(f"Candidates      : {len(candidates)}")
    print(f"Live Trades     : {len(live_trades)}")
    print(f"Live Profile    : {live_profile.get('profile', 'unknown')}")
    print("-------------------------------------------")

    if not candidates:
        print("No candidates passed signal and Greek filters.")
    else:
        print("Ranked Candidates")
        print("-------------------------------------------")
        for index, candidate in enumerate(
            candidates[: args.top],
            start=1,
        ):
            print_candidate(index, candidate)

    if live_trades:
        print()
        print("Live Trade Candidates")
        print("-------------------------------------------")
        for index, trade in enumerate(live_trades, start=1):
            print_trade(index, trade)

    print()
    print("Reports")
    print("-------------------------------------------")
    print(f"Recommendations CSV  : {recommendation_paths['csv']}")
    print(f"Recommendations JSON : {recommendation_paths['json']}")
    print(f"Recommendations HTML : {recommendation_paths['html']}")
    print(f"Live Trades CSV       : {trade_paths['csv']}")
    print(f"Live Trades JSON      : {trade_paths['json']}")
    print(f"Live Trades HTML      : {trade_paths['html']}")
    print("===========================================")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
