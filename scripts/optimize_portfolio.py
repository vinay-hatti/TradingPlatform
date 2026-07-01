import csv
import subprocess
from pathlib import Path

from trading_ai.portfolio.optimizer import PortfolioOptimizer

def calculate_portfolio_metrics(trades, capital):

    accepted = [
        t for t in trades
        if t.status == "ACCEPTED"
    ]

    if not accepted:
        return {
            "accepted_trades": 0,
            "portfolio_heat": 0.0,
            "avg_win_probability": 0.0,
            "avg_reward_risk": 0.0,
            "avg_kelly": 0.0,
            "expected_return": 0.0,
        }

    total_allocated = sum(t.final_allocation for t in accepted)

    return {
        "accepted_trades": len(accepted),
        "portfolio_heat": total_allocated / capital,
        "avg_win_probability": sum(t.win_probability for t in accepted) / len(accepted),
        "avg_reward_risk": sum(t.reward_risk for t in accepted) / len(accepted),
        "avg_kelly": sum(t.kelly_fraction for t in accepted) / len(accepted),
        "expected_return": sum(
            t.win_probability * t.reward_risk - (1.0 - t.win_probability)
            for t in accepted
        ) / len(accepted),
    }

def export_optimized_trades(trades, path=None):

    import csv
    from pathlib import Path
    from datetime import datetime

    if path is None:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"reports/optimized_portfolio_{timestamp}.csv"

    Path(path).parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", newline="") as f:
        writer = csv.writer(f)

        writer.writerow([
            "symbol",
            "signal",
            "strategy",
            "strike",
            "expiry",
            "confidence",
            "rank_score",
            "win_probability",
            "reward_risk",
            "kelly_fraction",
            "option_price_estimate",
            "contract_cost",
            "iv",
            "requested_allocation",
            "final_allocation",
            "recommended_contracts",
            "status",
            "reason",
            "risk_portfolio_heat",
            "risk_cash_reserve",
            "risk_symbol_exposure",
            "risk_sector_exposure",
            "risk_strategy_exposure",
            "risk_net_delta",
        ])

        for t in trades:
            writer.writerow([
                t.symbol,
                t.signal,
                t.strategy,
                t.strike,
                t.expiry,
                t.confidence,
                t.rank_score,
                t.win_probability,
                t.reward_risk,
                t.kelly_fraction,
                t.option_price_estimate,
                t.contract_cost,
                t.iv,
                t.requested_allocation,
                t.final_allocation,
                t.recommended_contracts,
                t.status,
                t.reason,
                t.risk_metrics.get("portfolio_heat", ""),
                t.risk_metrics.get("cash_reserve", ""),
                t.risk_metrics.get("symbol_exposure", ""),
                t.risk_metrics.get("sector_exposure", ""),
                t.risk_metrics.get("strategy_exposure", ""),
                t.risk_metrics.get("net_delta", ""),
            ])

    print(f"Optimized portfolio exported to {path}")

def run_scanner():

    cmd = [
        "uv",
        "run",
        "python",
        "scripts/run_scanner.py",
        "--only-affordable",
        "--min-confidence",
        "A",
        "--min-days-to-expiry",
        "45",
        "--export-csv",
    ]

    subprocess.run(cmd, check=True)


def find_latest_scanner_csv():

    files = sorted(
        Path("reports").glob("scanner_results_*.csv"),
        reverse=True,
    )

    if not files:
        return None

    return files[0]


def load_rows(path):

    with open(path, "r") as f:
        return list(csv.DictReader(f))


def main():

    capital = 100000.0

    run_scanner()

    latest = find_latest_scanner_csv()

    if latest is None:
        print("No scanner CSV found.")
        return

    rows = load_rows(latest)

    optimizer = PortfolioOptimizer(
        capital=capital,
        max_position_pct=0.05,
        max_total_allocation_pct=0.20,
        cash_reserve_pct=0.15,
    )

    optimized = optimizer.optimize(rows)

    print()
    print("========== Optimized Portfolio ==========")
    print(f"Scanner File : {latest}")
    print(f"Capital      : ${capital:,.2f}")
    print()

    total_allocated = 0.0

    for trade in optimized:

        total_allocated += trade.final_allocation
        heat = trade.risk_metrics.get("portfolio_heat", 0.0)
        net_delta = trade.risk_metrics.get("net_delta", 0.0)

        print(
            f"{trade.symbol:5} | "
            f"{trade.signal:4} | "
            f"{trade.strategy:10} | "
            f"Conf={trade.confidence:2} | "
            f"Rank={trade.rank_score:6.2f} | "
            f"Win={trade.win_probability:6.2%} | "
            f"RR={trade.reward_risk:4.2f} | "
            f"Kelly={trade.kelly_fraction:5.2%} | "
            f"Opt=${trade.option_price_estimate:7.2f} | "
            f"Cost=${trade.contract_cost:8.2f} | "
            f"Alloc=${trade.final_allocation:8.2f} | "
            f"Qty={trade.recommended_contracts:3} | "
            f"Heat={heat:5.2%} | "
            f"NetDelta={net_delta:5.2f} | "
            f"Status={trade.status:8} | "
            f"Reason={trade.reason}"
        )

    print()
    print(f"Total Allocated: ${total_allocated:,.2f}")
    print(f"Cash Reserve   : ${capital - total_allocated:,.2f}")
    metrics = calculate_portfolio_metrics(optimized, capital)
    print()
    print("Portfolio Metrics:")
    print(f"  Accepted Trades : {metrics['accepted_trades']}")
    print(f"  Portfolio Heat  : {metrics['portfolio_heat']:.2%}")
    print(f"  Avg Win Prob    : {metrics['avg_win_probability']:.2%}")
    print(f"  Avg Reward/Risk : {metrics['avg_reward_risk']:.2f}")
    print(f"  Avg Kelly       : {metrics['avg_kelly']:.2%}")
    print(f"  Exp Return Score: {metrics['expected_return']:.2f}")
    print("=========================================")
    export_optimized_trades(optimized)
    print()

if __name__ == "__main__":
    main()
