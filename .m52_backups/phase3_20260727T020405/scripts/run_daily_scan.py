from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone

from trading_ai.app.bootstrap import container
from trading_ai.daily.database_market_data import DatabaseHistoricalDataSource
from trading_ai.daily.live_profile import LiveProfileLoader
from trading_ai.daily.recommender import LiveTradeRecommender
from trading_ai.daily.reporter import DailyRecommendationReporter
from trading_ai.daily.scanner import DailyScanner
from trading_ai.daily.trade_reporter import LiveTradeCandidateReporter
from trading_ai.daily.published_context import ScannerPublishedStateContext
from trading_ai.database import SessionLocal
from trading_ai.published_state import PublishedMarketStateResolver, PublishedStatePolicy
from trading_ai.market.universe import get_universe
from trading_ai.portfolio.awareness import PortfolioAwareness
from trading_ai.lineage import LineagePersistenceService, ScannerRunLineage, new_run_id


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
    parser.add_argument("--pricing-dte", type=int, default=30, help="Fixed/proxy target DTE; retained for compatibility.")
    parser.add_argument("--expiration-mode", choices=["automatic","short","swing","medium","long","custom","fixed"], default="automatic")
    parser.add_argument("--minimum-dte", type=int, default=14)
    parser.add_argument("--maximum-dte", type=int, default=90)
    parser.add_argument("--maximum-expirations-per-symbol", type=int, default=4)
    parser.add_argument("--maximum-trades-per-expiration", type=int, default=3, help="0 disables expiry diversification.")
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
        help=argparse.SUPPRESS,
    )
    dealer_group = parser.add_mutually_exclusive_group()
    dealer_group.add_argument("--enable-dealer-positioning", dest="enable_dealer_positioning", action="store_true", default=True)
    dealer_group.add_argument("--disable-dealer-positioning", dest="enable_dealer_positioning", action="store_false")
    parser.add_argument("--dealer-positioning-max-age-days", type=int, default=1)
    parser.add_argument("--dealer-positioning-weight", type=float, default=1.0)
    parser.add_argument("--dealer-positioning-max-adjustment", type=float, default=15.0)
    parser.add_argument("--published-state-maximum-age-hours", type=float, default=36.0)
    parser.add_argument("--published-state-warning-age-hours", type=float, default=24.0)
    parser.add_argument("--require-ready-published-state", action="store_true")
    parser.add_argument("--allow-unpublished-state", action="store_true", help="Emergency compatibility override; disables published-state governance.")
    parser.add_argument(
        "--report-date",
        default=None,
        help="Report-date folder; defaults to today.",
    )
    return parser.parse_args(argv)



def resolve_scanner_published_state(args: argparse.Namespace) -> ScannerPublishedStateContext | None:
    if args.allow_unpublished_state:
        return None
    policy = PublishedStatePolicy.for_consumer(
        "scanner",
        maximum_age_seconds=max(1, int(float(args.published_state_maximum_age_hours) * 3600.0)),
        warning_age_seconds=max(1, int(float(args.published_state_warning_age_hours) * 3600.0)),
        allow_degraded=not bool(args.require_ready_published_state),
    )
    with SessionLocal() as session:
        state = PublishedMarketStateResolver(session, policy).require()
    return ScannerPublishedStateContext.from_state(state)

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
    print(f"   Base AI Score  : {candidate.base_ai_score:.2f}")
    print(f"   Dealer Adj.    : {candidate.dealer_score_adjustment:+.2f}")
    print(f"   Dealer Context : {candidate.dealer_context_status} / {candidate.positioning_label}")
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
    print(f"   Base AI     : {trade.base_ai_score:.2f}")
    print(f"   Dealer Adj. : {trade.dealer_score_adjustment:+.2f}")
    print(f"   Dealer      : {trade.dealer_context_status} / {trade.positioning_label}")
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
    published_state_context = resolve_scanner_published_state(args)
    scanner_run_id = new_run_id("scanner")
    scanner_started_at = datetime.now(timezone.utc)

    if args.top <= 0:
        raise ValueError("--top must be positive")
    if args.pricing_dte <= 0:
        raise ValueError("--pricing-dte must be positive")
    if args.minimum_dte <= 0 or args.maximum_dte <= 0 or args.minimum_dte > args.maximum_dte:
        raise ValueError("DTE range must be positive and minimum-dte cannot exceed maximum-dte")
    if args.maximum_expirations_per_symbol <= 0:
        raise ValueError("--maximum-expirations-per-symbol must be positive")
    if args.start > args.end:
        raise ValueError("--start cannot be after --end")

    if args.allow_network:
        raise ValueError(
            "--allow-network is not supported by the Daily Scanner. "
            "Run the governed ingestion workflow separately, then scan PostgreSQL."
        )

    live_profile = LiveProfileLoader().load()
    effective_market_end = (
        published_state_context.market_as_of_date
        if published_state_context is not None
        else args.end
    )
    datasource = DatabaseHistoricalDataSource(
        maximum_as_of_date=effective_market_end,
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
        expiration_mode=args.expiration_mode,
        minimum_dte=args.minimum_dte,
        maximum_dte=args.maximum_dte,
        maximum_expirations_per_symbol=args.maximum_expirations_per_symbol,
        maximum_trades_per_expiration=args.maximum_trades_per_expiration,
        start=args.start,
        end=min(args.end, effective_market_end),
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
        enable_dealer_positioning=args.enable_dealer_positioning,
        maximum_dealer_snapshot_age_days=args.dealer_positioning_max_age_days,
        dealer_positioning_weight=args.dealer_positioning_weight,
        maximum_dealer_score_adjustment=args.dealer_positioning_max_adjustment,
        published_state_context=published_state_context,
        option_snapshot_as_of=args.end,
    )

    print()
    print("========== Daily AI Trading Scan ==========")
    print(f"Universe        : {args.universe if not args.symbols else 'custom'}")
    print(f"Symbols Selected: {len(symbols)}")
    effective_end = min(args.end, effective_market_end)
    print(f"History Requested: {args.start} -> {args.end}")
    print(f"History Effective: {args.start} -> {effective_end}")
    print(f"Minimum Score   : {args.min_score}")
    print(f"Option Data     : {args.option_data_mode}")
    print(f"Expiry Mode     : {args.expiration_mode}")
    print(f"DTE Range       : {args.minimum_dte} -> {args.maximum_dte}")
    print(f"Expiry Limit    : {args.maximum_trades_per_expiration or 'disabled'} trades per expiration")
    print(
        "Data Mode       : PostgreSQL database only"
    )
    if published_state_context:
        print(f"Published State : {published_state_context.publication_status}")
        print(f"Ingestion Run   : {published_state_context.ingestion_run_id}")
        print(f"Market As-Of    : {published_state_context.market_as_of_date}")
        print(f"Option Snapshot : {published_state_context.option_snapshot_id}")
        print(f"Option As-Of    : {args.end}")
        print(f"Coverage        : {published_state_context.option_snapshot_completeness_pct if published_state_context.option_snapshot_completeness_pct is not None else 'unavailable'}")
    else:
        print("Published State : BYPASSED (override)")
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

    lineage_values = published_state_context.to_dict() if published_state_context else {}
    scanner_lineage = ScannerRunLineage(
        scanner_run_id=scanner_run_id,
        publication_name=lineage_values.get("publication_name"),
        ingestion_run_id=lineage_values.get("ingestion_run_id"),
        publication_status=lineage_values.get("publication_status", "BYPASSED"),
        published_at=lineage_values.get("published_at"),
        market_as_of_date=lineage_values.get("market_as_of_date"),
        market_intelligence_snapshot_timestamp=lineage_values.get("market_intelligence_snapshot_timestamp"),
        option_snapshot_timestamp=lineage_values.get("option_snapshot_timestamp"),
        option_snapshot_id=lineage_values.get("option_snapshot_id"),
        option_snapshot_completeness_pct=lineage_values.get("option_snapshot_completeness_pct"),
        published_state_degraded=bool(lineage_values.get("degraded", False)),
        scanner_version="m47.phase6.v1",
        started_at=scanner_started_at,
    )
    lineage_summary = LineagePersistenceService().persist_scanner_run(
        scanner_lineage,
        candidates,
        metadata={"symbols": symbols, "top": args.top, "allow_unpublished_state": args.allow_unpublished_state},
    )
    candidate_by_symbol = {getattr(candidate, "symbol", None): candidate for candidate in candidates}
    for trade in live_trades:
        source = candidate_by_symbol.get(getattr(trade, "symbol", None))
        if source is not None:
            for field_name in ("scanner_run_id", "candidate_id", "market_state_hash", "scanner_version"):
                try:
                    setattr(trade, field_name, getattr(source, field_name, ""))
                except Exception:
                    pass

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
        "expiration_mode": args.expiration_mode,
        "minimum_dte": args.minimum_dte,
        "maximum_dte": args.maximum_dte,
        "maximum_expirations_per_symbol": args.maximum_expirations_per_symbol,
        "maximum_trades_per_expiration": args.maximum_trades_per_expiration,
        "requested_start": args.start,
        "requested_end": args.end,
        "effective_start": args.start,
        "effective_end": effective_end,
        "positions_file": args.positions_file,
        "dealer_positioning_enabled": args.enable_dealer_positioning,
        "dealer_positioning_max_age_days": args.dealer_positioning_max_age_days,
        "dealer_positioning_weight": args.dealer_positioning_weight,
        "dealer_positioning_max_adjustment": args.dealer_positioning_max_adjustment,
        "data_mode": "database_only",
        "market_data_source": "PostgreSQL.price_history",
        "network_access": False,
        "ingestion_allowed": False,
        "published_state": published_state_context.to_dict() if published_state_context else {"bypassed": True},
        "scanner_run_id": scanner_run_id,
        "scanner_version": "m47.phase6.v1",
        "lineage_persistence": {"status": lineage_summary.status, "candidate_rows": lineage_summary.item_rows, **lineage_summary.metadata},
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
    print(f"Scanner Run     : {scanner_run_id}")
    print(f"Lineage Rows    : {lineage_summary.item_rows}")
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
    print(f"Recommendations Manifest: {recommendation_paths['manifest']}")
    print(f"Live Trades CSV       : {trade_paths['csv']}")
    print(f"Live Trades JSON      : {trade_paths['json']}")
    print(f"Live Trades HTML      : {trade_paths['html']}")
    print(f"Live Trades Manifest  : {trade_paths['manifest']}")
    print("===========================================")
    print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
