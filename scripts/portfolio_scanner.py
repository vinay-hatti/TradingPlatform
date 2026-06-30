import subprocess
import csv
from pathlib import Path

from trading_ai.portfolio.manager import PortfolioManager

def load_sector_map():

    import json
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    path = root / "config" / "sectors.json"

    try:
        with open(path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Sector map not found: {path}")
        return {}

#def load_sector_map(path="config/sectors.json"):
#    import json
#    try:
#        with open(path, "r") as f:
#            return json.load(f)
#    except FileNotFoundError:
#        return {}

def find_latest_scanner_csv():

    files = sorted(
        Path("reports").glob("scanner_results_*.csv"),
        reverse=True,
    )

    if not files:
        return None

    return files[0]


def run_scanner():

    cmd = [
        "uv",
        "run",
        "python",
        "scripts/run_scanner.py",
        "--only-affordable",
        "--min-confidence",
        "A",
        "--export-csv",
    ]

    subprocess.run(cmd, check=True)


def load_scanner_rows(path):

    with open(path, "r") as f:
        return list(csv.DictReader(f))


def main():

    capital = 100000.0

    sector_map = load_sector_map()

    portfolio = PortfolioManager(
        initial_capital=capital,
        max_symbol_exposure_pct=0.05,
        max_sector_exposure_pct=0.30,
        max_strategy_exposure_pct=0.50,
    )

    run_scanner()

    latest_csv = find_latest_scanner_csv()

    if latest_csv is None:
        print("No scanner CSV found.")
        return

    rows = load_scanner_rows(latest_csv)

    print()
    print("========== Portfolio Scanner ==========")
    print(f"Using scanner file: {latest_csv}")
    print()

    for row in rows:

        symbol = row["symbol"]
        strategy = row["strategy"]
        signal = row["signal"]
        quantity = int(float(row["recommended_contracts"]))
        option_price = float(row["option_price_estimate"])

        allowed, reason = portfolio.can_add_trade(
            symbol=symbol,
            strategy=strategy,
            quantity=quantity,
            option_price=option_price,
#            sector="Technology",
            sector=sector_map.get(symbol, "UNKNOWN"),
        )

        status = "ACCEPTED" if allowed else "REJECTED"

        print(
            f"{symbol:5} | "
            f"{signal:4} | "
            f"{strategy:10} | "
            f"Qty={quantity:3} | "
            f"Opt=${option_price:8.2f} | "
            f"Status={status:8} | "
            f"Reason={reason}"
        )

        if allowed:
            portfolio.add_position(
                symbol=symbol,
                strategy=strategy,
                signal=signal,
                quantity=quantity,
                option_price=option_price,
#                sector="Technology",
                sector=sector_map.get(symbol, "UNKNOWN"),
            )

    snapshot = portfolio.snapshot()

    print()
    print("========== Portfolio Snapshot ==========")
    print(f"Cash           : ${snapshot.cash:,.2f}")
    print(f"Market Value   : ${snapshot.market_value:,.2f}")
    print(f"Net Liquidation: ${snapshot.net_liquidation:,.2f}")
    print()

    print("Sector Exposure:")
    for sector, value in snapshot.sector_exposure.items():
        print(f"  {sector:12}: ${value:,.2f}")

    print()
    print("Strategy Exposure:")
    for strategy, value in snapshot.strategy_exposure.items():
        print(f"  {strategy:12}: ${value:,.2f}")

    print("========================================")
    print()


if __name__ == "__main__":
    main()
