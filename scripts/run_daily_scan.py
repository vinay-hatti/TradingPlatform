import argparse

from trading_ai.app.bootstrap import container
from trading_ai.backtest.datasource import HistoricalDataSource
from trading_ai.daily.live_profile import LiveProfileLoader
from trading_ai.daily.scanner import DailyScanner


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

    return parser.parse_args()


def main():

    args = parse_args()

    symbols = [
        s.strip().upper()
        for s in args.symbols.split(",")
        if s.strip()
    ]

    live_profile = LiveProfileLoader().load()

    datasource = HistoricalDataSource(container.market)

    scanner = DailyScanner(
        market_service=datasource,
        feature_pipeline=container.pipeline,
        live_profile=live_profile,
        min_score=args.min_score,
        pricing_dte=args.pricing_dte,
        start=args.start,
        end=args.end,
    )


    candidates = scanner.scan(symbols)

    print()
    print("========== Daily AI Trading Scan ==========")
    print(f"Symbols Scanned : {len(symbols)}")
    print(f"Candidates      : {len(candidates)}")
    print(f"Live Profile    : {live_profile.get('profile', 'unknown')}")
    print(f"Min Score       : {args.min_score}")
    print(f"Pricing DTE     : {args.pricing_dte}")
    print("-------------------------------------------")

    if not candidates:
        print("No candidates passed signal and Greek filters.")
        print("===========================================")
        print()
        return

    for idx, c in enumerate(candidates[:args.top], start=1):
        print()
        print(f"{idx}. {c.symbol} {c.signal}")
        print(f"   Strategy      : {c.strategy}")
        print(f"   Final Score   : {c.final_score:.2f}")
        print(f"   Signal Score  : {c.score:.2f}")
        print(f"   Call / Put    : {c.call_score:.2f} / {c.put_score:.2f}")
        print(f"   Regime        : {c.market_regime}")
        print(f"   Underlying    : ${c.close:.2f}")
        print(f"   Strike        : ${c.strike:.2f}")
        print(f"   Option Price  : ${c.option_price:.2f}")
        print(f"   Expiry Proxy  : {c.expiry}")
        print(
            f"   Greeks        : "
            f"Δ={c.delta:.4f}, "
            f"Γ={c.gamma:.5f}, "
            f"Θ={c.theta:.4f}, "
            f"V={c.vega:.4f}, "
            f"ρ={c.rho:.4f}"
        )
        print(f"   Vol / DTE     : {c.volatility:.2%} / {c.dte}")

    print()
    print("===========================================")
    print()


if __name__ == "__main__":
    main()
