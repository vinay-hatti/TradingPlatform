import csv
from pathlib import Path

from trading_ai.execution.paper_broker import PaperBroker


def latest_file(pattern):
    files = sorted(Path("reports").glob(pattern), reverse=True)
    return files[0] if files else None


def load_rows(path):
    with open(path, "r") as f:
        return list(csv.DictReader(f))


def main():

    latest = latest_file("optimized_portfolio_*.csv")

    if latest is None:
        print("No optimized portfolio file found.")
        print("Run this first:")
        print("uv run python scripts/optimize_portfolio.py")
        return

    broker = PaperBroker(initial_cash=100000.0)

    rows = load_rows(latest)

    print()
    print("========== Paper Trade Import ==========")
    print(f"Source: {latest}")
    print()

    for row in rows:

        if row["status"] != "ACCEPTED":
            continue

        quantity = int(float(row["recommended_contracts"]))

        if quantity <= 0:
            continue

        if broker.has_open_position(
            row["symbol"],
            row["signal"],
            float(row["strike"]),
            row["expiry"],
        ):
            print(
                f"{row['symbol']:5} | "
                f"SKIPPED | DUPLICATE_OPEN_POSITION"
            )
            continue

        order = broker.submit_order(
            symbol=row["symbol"],
            signal=row["signal"],
            strategy=row["strategy"],
            strike=float(row.get("strike", 0.0) or 0.0),
            expiry=row.get("expiry", ""),
            quantity=quantity,
            price=float(row["option_price_estimate"]),
            implied_volatility=float(row.get("iv", 0.25) or 0.25),
        )

        if order is None:
            print(
                f"{row['symbol']:5} | "
                f"SKIPPED | insufficient cash or invalid quantity"
            )
        else:
            print(
                f"{row['symbol']:5} | "
                f"{row['signal']:4} | "
                f"{row['strategy']:10} | "
                f"Qty={quantity:3} | "
                f"Price=${float(row['option_price_estimate']):8.2f} | "
                f"FILLED"
            )

    print()
    print("Broker Summary:")
    print(broker.summary())
    print("========================================")
    print()


if __name__ == "__main__":
    main()
