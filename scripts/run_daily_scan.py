import argparse
from datetime import date

from trading_ai.app.bootstrap import container
from trading_ai.backtest.datasource import HistoricalDataSource
from trading_ai.daily.live_profile import LiveProfileLoader
from trading_ai.daily.scanner import DailyScanner
from trading_ai.daily.reporter import DailyRecommendationReporter
from trading_ai.daily.recommender import LiveTradeRecommender
from trading_ai.daily.trade_reporter import LiveTradeCandidateReporter
from trading_ai.portfolio.awareness import PortfolioAwareness


def parse_args():

    parser = argparse.ArgumentParser(
        description="Run daily AI options scanner"
    )

    parser.add_argument(
        "--symbols",
        default="AAPL,MSFT,AMZN,NVDA,META,GOOGL,TSLA,AMD,SPY,QQQ",
    )

    parser.add_argument("--start", default="2026-01-01")
    parser.add_argument("--end", default="2026-06-01")
    parser.add_argument("--min-score", type=float, default=60.0)
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--pricing-dte", type=int, default=30)

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
        "--report-date",
        default=None,
        help="Report date folder, default today",
    )

    return parser.parse_args()


def print_candidate(idx, c):

    print()
    print(f"{idx}. {c.symbol} {c.signal}")
    print(f"   Strategy       : {c.strategy}")
    print(f"   Sector         : {c.sector}")
    print(f"   AI Score       : {c.ai_score:.2f}")
    print(f"   Technical      : {c.technical_score:.2f}")
    print(f"   Greeks         : {c.greeks_score:.2f}")
    print(f"   Regime         : {c.regime_score:.2f}")
    print(f"   Volatility     : {c.volatility_score:.2f}")
    print(f"   Risk           : {c.risk_score:.2f}")
    print(f"   Ranking Reason : {c.ranking_reason}")
    print(f"   Adjusted Score : {c.adjusted_score:.2f}")
    print(f"   Base Score     : {c.final_score:.2f}")
    print(f"   Penalty        : {c.portfolio_penalty:.2f}")

    if c.portfolio_notes:
        print("   Portfolio Notes:")
        for note in c.portfolio_notes:
            print(f"     - {note}")

    print(f"   Signal Score   : {c.score:.2f}")
    print(f"   Call / Put     : {c.call_score:.2f} / {c.put_score:.2f}")
    print(f"   Market Regime  : {c.market_regime}")
    print(f"   Underlying     : ${c.close:.2f}")
    print(f"   Strike         : ${c.strike:.2f}")
    print(f"   Option Price   : ${c.option_price:.2f}")
    print(f"   Expiry Proxy   : {c.expiry}")
    print(
        f"   Greeks Values  : "
        f"Δ={c.delta:.4f}, "
        f"Γ={c.gamma:.5f}, "
        f"Θ={c.theta:.4f}, "
        f"V={c.vega:.4f}, "
        f"ρ={c.rho:.4f}"
    )
    print(f"   Vol / DTE      : {c.volatility:.2%} / {c.dte}")


def print_trade(idx, t):

    print()
    print(f"{idx}. LIVE TRADE CANDIDATE — {t.symbol} {t.signal}")
    print(f"   Confidence    : {t.confidence}")
    print(f"   AI Score      : {t.ai_score:.2f}")
    print(f"   Strategy      : {t.strategy}")
    print(f"   Sector        : {t.sector}")
    print(f"   Underlying    : ${t.underlying_price:.2f}")
    print(f"   Strike        : ${t.strike:.2f}")
    print(f"   Entry         : ${t.option_entry:.2f}")
    print(f"   Target        : ${t.target_price:.2f}")
    print(f"   Stop          : ${t.stop_price:.2f}")
    print(f"   Contracts     : {t.contracts}")
    print(f"   Est. Cost     : ${t.estimated_cost:,.2f}")
    print(f"   Max Risk      : ${t.max_risk:,.2f}")
    print(f"   Est. Reward   : ${t.estimated_reward:,.2f}")
    print(f"   Reward/Risk   : {t.reward_risk_ratio:.2f}")
    print(
        f"   Greeks        : "
        f"Δ={t.delta:.4f}, "
        f"Γ={t.gamma:.5f}, "
        f"Θ={t.theta:.4f}, "
        f"V={t.vega:.4f}, "
        f"ρ={t.rho:.4f}"
    )
    print(f"   Regime        : {t.market_regime}")
    print(f"   Reason        : {t.ranking_reason}")

    if t.trade_notes:
        print("   Notes:")
        for note in t.trade_notes:
            print(f"     - {note}")


def main():

    args = parse_args()

    symbols = [
        s.strip().upper()
        for s in args.symbols.split(",")
        if s.strip()
    ]

    live_profile = LiveProfileLoader().load()
    datasource = HistoricalDataSource(container.market)

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
    )

    candidates = scanner.scan(symbols)

    recommender = LiveTradeRecommender(
        capital=args.capital,
        risk_per_trade_pct=args.risk_per_trade_pct,
        max_position_pct=args.max_position_pct,
        take_profit_pct=args.take_profit_pct,
        stop_loss_pct=args.stop_loss_pct,
    )

    live_trades = recommender.build_many(
        candidates[:args.top]
    )

    portfolio_summary = portfolio.exposure_summary()

    metadata = {
        "date": args.report_date or date.today().isoformat(),
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
    }

    recommendation_paths = DailyRecommendationReporter().generate(
        candidates=candidates,
        metadata=metadata,
        portfolio_summary=portfolio_summary,
        report_date=args.report_date,
    )

    trade_metadata = dict(metadata)
    trade_metadata.update({
        "capital": args.capital,
        "risk_per_trade_pct": args.risk_per_trade_pct,
        "max_position_pct": args.max_position_pct,
        "take_profit_pct": args.take_profit_pct,
        "stop_loss_pct": args.stop_loss_pct,
    })

    trade_paths = LiveTradeCandidateReporter().generate(
        trades=live_trades,
        metadata=trade_metadata,
        report_date=args.report_date,
    )

    print()
    print("========== Daily AI Trading Scan ==========")
    print(f"Symbols Scanned : {len(symbols)}")
    print(f"Candidates      : {len(candidates)}")
    print(f"Live Trades     : {len(live_trades)}")
    print(f"Live Profile    : {live_profile.get('profile', 'unknown')}")
    print(f"Min Score       : {args.min_score}")
    print(f"Pricing DTE     : {args.pricing_dte}")
    print(f"Positions       : {portfolio_summary.get('positions', 0)}")
    print("-------------------------------------------")

    print("Portfolio Exposure")
    print("-------------------------------------------")
    print(f"By Symbol : {portfolio_summary.get('by_symbol', {})}")
    print(f"By Sector : {portfolio_summary.get('by_sector', {})}")
    print("-------------------------------------------")

    if not candidates:
        print("No candidates passed signal and Greek filters.")
    else:
        print()
        print("Ranked Candidates")
        print("-------------------------------------------")
        for idx, c in enumerate(candidates[:args.top], start=1):
            print_candidate(idx, c)

    if live_trades:
        print()
        print("Live Trade Candidates")
        print("-------------------------------------------")
        for idx, t in enumerate(live_trades, start=1):
            print_trade(idx, t)

    print()
    print("Reports")
    print("-------------------------------------------")
    print(f"Recommendations CSV  : {recommendation_paths['csv']}")
    print(f"Recommendations JSON : {recommendation_paths['json']}")
    print(f"Recommendations HTML : {recommendation_paths['html']}")
    print(f"Live Trades CSV      : {trade_paths['csv']}")
    print(f"Live Trades JSON     : {trade_paths['json']}")
    print(f"Live Trades HTML     : {trade_paths['html']}")
    print("===========================================")
    print()


if __name__ == "__main__":
    main()
