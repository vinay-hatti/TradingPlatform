from datetime import datetime

from trading_ai.app.bootstrap import container
from trading_ai.execution.paper_broker import PaperBroker
from trading_ai.options.pricing import BlackScholesPricer

def days_held(opened_at):

    try:
        opened = datetime.fromisoformat(str(opened_at))
        now = datetime.now()
        return (now - opened).days
    except Exception:
        return 0

def time_to_expiry_years(expiry):

    try:
        expiry_dt = datetime.strptime(str(expiry), "%Y-%m-%d")
        today = datetime.now()
        days = (expiry_dt - today).days
        return max(days / 365.0, 1 / 365.0)
    except Exception:
        return 30 / 365.0


def latest_stock_price(symbol):

    df = container.market.get_history(
        symbol,
        "2026-01-01",
        "2026-06-01",
    )

    if df.empty:
        return None

    return float(df.iloc[-1]["close"])


def main():

    broker = PaperBroker(initial_cash=100000.0)
    pricer = BlackScholesPricer()

    open_positions = broker.open_positions()

    print()
    print("========== Mark Paper Positions ==========")

    if not open_positions:
        print("No open paper positions.")
        print(broker.summary())
        return

    for position in open_positions:

        symbol = position["symbol"]
        signal = position["signal"]
        strike = float(position["strike"])
        expiry = position["expiry"]

        stock_price = latest_stock_price(symbol)

        if stock_price is None:
            print(f"{symbol:5} | SKIPPED | no market data")
            continue

        current_option_price = pricer.price(
            spot=stock_price,
            strike=strike,
            time_to_expiry=time_to_expiry_years(expiry),
            volatility=float(position.get("implied_volatility", 0.25) or 0.25),
            option_type=signal,
        )

        current_option_price = max(current_option_price, 0.05)

        updated = broker.mark_position(
            order_id=position["order_id"],
            current_price=current_option_price,
        )

        entry_price = float(position["entry_price"])

        MAX_HOLD_DAYS = 10

        return_pct = (
            current_option_price - entry_price
        ) / max(entry_price, 0.01)

        held_days = days_held(position.get("opened_at"))

        exit_reason = None

        if return_pct >= 0.15:
            exit_reason = "TAKE_PROFIT"

        elif return_pct <= -0.08:
            exit_reason = "STOP_LOSS"

        elif held_days >= MAX_HOLD_DAYS:
            exit_reason = "MAX_HOLD"

        if exit_reason is not None:
            closed = broker.close_position(
                order_id=position["order_id"],
                exit_price=current_option_price,
                reason=exit_reason,
            )

            print(
                f"{symbol:5} | "
                f"{signal:4} | "
                f"Strike={strike:8.2f} | "
                f"Stock=${stock_price:8.2f} | "
                f"Entry=${entry_price:8.2f} | "
                f"Exit=${current_option_price:8.2f} | "
                f"Return={return_pct:7.2%} | "
                f"Closed={exit_reason} | "
                f"Held={held_days:3}d | "
                f"Realized=${closed.realized_pnl:9.2f}"
            )
        else:
            print(
                f"{symbol:5} | "
                f"{signal:4} | "
                f"Strike={strike:8.2f} | "
                f"Stock=${stock_price:8.2f} | "
                f"Entry=${entry_price:8.2f} | "
                f"Current=${current_option_price:8.2f} | "
                f"Return={return_pct:7.2%} | "
                f"Held={held_days:3}d | "
                f"Unrealized=${updated.unrealized_pnl:9.2f}"
            )

    print()
    print("Broker Summary:")
    print(broker.summary())
    print("==========================================")
    print()


if __name__ == "__main__":
    main()
