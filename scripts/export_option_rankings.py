import csv
from pathlib import Path
from datetime import datetime

from trading_ai.app.bootstrap import container
from trading_ai.backtest.config import BacktestConfig


def format_spread(value):

    try:
        value = float(value)
    except Exception:
        return "N/A"

    if value < 0:
        return "N/A"

    return f"{value:.2%}"

def export_rows(rows, path=None):

    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"reports/option_rankings_{timestamp}.csv"

    Path(path).parent.mkdir(parents=True, exist_ok=True)

    fieldnames = [
        "symbol",
        "rank",
        "signal",
        "strike",
        "expiry",
        "total_score",
        "option_score",
        "atm_score",
        "probability_of_profit",
        "liquidity_score",
        "delta_score",
        "iv_score",
        "dte_score",
        "spread_score",
        "spread_pct",
        "delta",
        "iv",
        "open_interest",
        "volume",
        "bid",
        "ask",
        "gamma",
        "theta",
        "vega",
        "rho",
        "option_symbol",
        "option_score_contribution",
        "atm_score_contribution",
        "dte_score_contribution",
        "liquidity_contribution",
        "spread_contribution",
        "option_weight",
        "atm_weight",
        "dte_weight",
        "liquidity_weight",
        "spread_weight",
    ]

    with open(path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Option rankings exported to {path}")


def main():

    config = BacktestConfig(
        symbols=[
            "AAPL",
            "MSFT",
            "NVDA",
            "AMD",
            "GOOGL",
            "AMZN",
            "META",
            "TSLA",
        ],
        start="2026-01-01",
        end="2026-06-01",
    )

    rows = []

    for symbol in config.symbols:

        df = container.market.get_history(
            symbol,
            config.start,
            config.end,
        )

        df = container.pipeline.run(df)

        if df.empty:
            continue

        row = df.iloc[-1]
        ctx = row["trade_context"]

        analytics = container.market.provider.get_analytics(symbol)

        recommendation = container.strategy_engine.recommend(
            symbol,
            ctx,
            analytics,
        )

        if recommendation is None:
            continue

#        ranked = container.options.rank_contracts(
#        ranked = container.strategy_engine.options.rank_contracts(
#            symbol=symbol,
#            ctx=ctx,
#            analytics=analytics,
#            strategy=recommendation.strategy,
#            limit=10,
#        )
        ranked = container.options_engine.rank_contracts(
            symbol=symbol,
            ctx=ctx,
            analytics=analytics,
            strategy=recommendation.strategy,
            limit=10,
        )

        for ranked_option in ranked:

            option = ranked_option.option

            rows.append({
                "symbol": symbol,
                "rank": ranked_option.rank,
                "signal": option.option_type,
                "strike": option.strike,
                "expiry": option.expiry,
                "total_score": ranked_option.total_score,
                "option_score": ranked_option.option_score,
                "atm_score": ranked_option.atm_score,
                "probability_of_profit": ranked_option.probability_of_profit,
                "liquidity_score": ranked_option.liquidity_score,
                "delta_score": ranked_option.delta_score,
                "iv_score": ranked_option.iv_score,
                "dte_score": ranked_option.dte_score,
                "spread_score": ranked_option.spread_score,
                "spread_pct": ranked_option.spread_pct,
                "delta": option.delta,
                "iv": option.implied_volatility,
                "open_interest": option.open_interest,
                "volume": getattr(option, "volume", 0),
                "bid": getattr(option, "bid", 0),
                "ask": getattr(option, "ask", 0),
                "gamma": getattr(option, "gamma", 0.0),
                "theta": getattr(option, "theta", 0.0),
                "vega": getattr(option, "vega", 0.0),
                "rho": getattr(option, "rho", 0.0),
                "option_symbol": getattr(option, "option_symbol", ""),
                "option_score_contribution": ranked_option.option_score_contribution,
                "atm_score_contribution": ranked_option.atm_score_contribution,
                "dte_score_contribution": ranked_option.dte_score_contribution,
                "liquidity_contribution": ranked_option.liquidity_contribution,
                "spread_contribution": ranked_option.spread_contribution,
                "option_weight": ranked_option.option_weight,
                "atm_weight": ranked_option.atm_weight,
                "dte_weight": ranked_option.dte_weight,
                "liquidity_weight": ranked_option.liquidity_weight,
                "spread_weight": ranked_option.spread_weight,
            })

    rows = sorted(
        rows,
        key=lambda r: (r["symbol"], r["rank"]),
    )

    print()
    print("========== Top Option Rankings ==========")

    for r in rows:
        print(
            f"{r['symbol']:5} | "
            f"Rank={int(r['rank']):2} | "
            f"{r['signal']:4} | "
            f"Strike={float(r['strike']):8.2f} | "
            f"Exp={r['expiry']} | "
            f"Total={float(r['total_score']):6.2f} | "
            f"OptScore={float(r['option_score']):6.2f} | "
            f"ATM={float(r['atm_score']):6.2f} | "
            f"POP={float(r['probability_of_profit']):6.2%} | "
            f"Liq={float(r['liquidity_score']):6.2f} | "
            f"DTE={float(r['dte_score']):6.2f} | "
            f"Spread={format_spread(r['spread_pct'])} |"
            f"Delta={float(r['delta']):5.2f} | "
            f"Gamma={float(r['gamma']):7.4f} | "
            f"Theta={float(r['theta']):8.2f} | "
            f"Vega={float(r['vega']):7.4f} | "
        )

    print("========================================")
    print()

    export_rows(rows)


if __name__ == "__main__":
    main()
