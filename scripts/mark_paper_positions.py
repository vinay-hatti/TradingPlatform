from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from typing import Any

from trading_ai.app.bootstrap import container
from trading_ai.execution.paper_broker import PaperBroker
from trading_ai.options.pricing import BlackScholesPricer


DEFAULT_MAX_HOLD_DAYS = 10
DEFAULT_TAKE_PROFIT_PCT = 0.15
DEFAULT_STOP_LOSS_PCT = -0.08


def days_held(opened_at: Any) -> int:
    try:
        opened = datetime.fromisoformat(str(opened_at))
        return max((datetime.now() - opened).days, 0)
    except (TypeError, ValueError):
        return 0


def time_to_expiry_years(expiry: Any) -> float:
    try:
        expiry_date = date.fromisoformat(str(expiry)[:10])
        remaining_days = max((expiry_date - date.today()).days, 1)
        return remaining_days / 365.0
    except (TypeError, ValueError):
        return 30.0 / 365.0


def latest_stock_price(
    symbol: str,
    *,
    lookback_days: int = 30,
) -> float | None:
    end_date = date.today()
    start_date = end_date - timedelta(days=lookback_days)

    frame = container.market.get_history(
        symbol,
        start_date.isoformat(),
        end_date.isoformat(),
    )
    if frame is None or frame.empty:
        return None

    close_column = "close" if "close" in frame.columns else "Close"
    if close_column not in frame.columns:
        raise ValueError(
            f"Market history for {symbol} has no close column. "
            f"Available columns: {list(frame.columns)}"
        )

    close_values = frame[close_column].dropna()
    if close_values.empty:
        return None
    return float(close_values.iloc[-1])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Mark and automatically exit open paper option positions."
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=30,
        help="Calendar-day market-history lookback. Default: 30.",
    )
    parser.add_argument(
        "--max-hold-days",
        type=int,
        default=DEFAULT_MAX_HOLD_DAYS,
    )
    parser.add_argument(
        "--take-profit",
        type=float,
        default=DEFAULT_TAKE_PROFIT_PCT,
        help="Decimal return threshold. Default: 0.15.",
    )
    parser.add_argument(
        "--stop-loss",
        type=float,
        default=DEFAULT_STOP_LOSS_PCT,
        help="Decimal return threshold. Default: -0.08.",
    )
    parser.add_argument(
        "--risk-free-rate",
        type=float,
        default=0.04,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.lookback_days <= 0:
        raise ValueError("--lookback-days must be positive")
    if args.max_hold_days <= 0:
        raise ValueError("--max-hold-days must be positive")
    if args.take_profit <= 0:
        raise ValueError("--take-profit must be positive")
    if args.stop_loss >= 0:
        raise ValueError("--stop-loss must be negative")

    broker = PaperBroker(initial_cash=100000.0)
    pricer = BlackScholesPricer(
        risk_free_rate=args.risk_free_rate
    )
    open_positions = broker.open_positions()

    print()
    print("========== Mark Paper Positions ==========")

    if not open_positions:
        print("No open paper positions.")
        print(broker.summary())
        return 0

    failures = 0

    for position in open_positions:
        symbol = str(position["symbol"]).upper()
        signal = str(position["signal"]).upper()
        strike = float(position["strike"])
        expiry = position["expiry"]

        try:
            stock_price = latest_stock_price(
                symbol,
                lookback_days=args.lookback_days,
            )
            if stock_price is None:
                failures += 1
                print(f"{symbol:5} | SKIPPED | no market data")
                continue

            current_option_price = pricer.price(
                spot=stock_price,
                strike=strike,
                time_to_expiry=time_to_expiry_years(expiry),
                volatility=float(
                    position.get("implied_volatility", 0.25) or 0.25
                ),
                option_type=signal,
            )
            current_option_price = max(current_option_price, 0.05)

            updated = broker.mark_position(
                order_id=position["order_id"],
                current_price=current_option_price,
            )

            entry_price = float(position["entry_price"])
            return_pct = (
                current_option_price - entry_price
            ) / max(entry_price, 0.01)
            held_days = days_held(position.get("opened_at"))

            exit_reason = None
            if return_pct >= args.take_profit:
                exit_reason = "TAKE_PROFIT"
            elif return_pct <= args.stop_loss:
                exit_reason = "STOP_LOSS"
            elif held_days >= args.max_hold_days:
                exit_reason = "MAX_HOLD"

            if exit_reason is not None:
                closed = broker.close_position(
                    order_id=position["order_id"],
                    exit_price=current_option_price,
                    reason=exit_reason,
                )
                print(
                    f"{symbol:5} | {signal:4} | "
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
                    f"{symbol:5} | {signal:4} | "
                    f"Strike={strike:8.2f} | "
                    f"Stock=${stock_price:8.2f} | "
                    f"Entry=${entry_price:8.2f} | "
                    f"Current=${current_option_price:8.2f} | "
                    f"Return={return_pct:7.2%} | "
                    f"Held={held_days:3}d | "
                    f"Unrealized=${updated.unrealized_pnl:9.2f}"
                )
        except Exception as exc:
            failures += 1
            print(
                f"{symbol:5} | FAILED | "
                f"{type(exc).__name__}: {exc}"
            )

    print()
    print("Broker Summary:")
    print(broker.summary())
    print("==========================================")
    print()

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
