from __future__ import annotations

import argparse
from pathlib import Path

from trading_ai.indicators.engine import IndicatorEngine
from trading_ai.market.yahoo import YahooProvider


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download Yahoo market data and compute technical indicators."
    )
    parser.add_argument("--symbol", default="AAPL")
    parser.add_argument("--period", default="6mo")
    parser.add_argument("--interval", default="1d")
    parser.add_argument(
        "--output",
        help="Optional CSV output path.",
    )
    parser.add_argument(
        "--tail",
        type=int,
        default=10,
        help="Rows to display. Default: 10.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    provider = YahooProvider()
    frame = provider.history(
        args.symbol.upper(),
        period=args.period,
        interval=args.interval,
    )
    if frame.empty:
        raise RuntimeError(
            f"No Yahoo market data returned for {args.symbol.upper()}"
        )

    result = IndicatorEngine().run(frame)

    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        result.to_csv(output_path, index=False)
        print(f"Indicator output written to {output_path}")

    display_columns = [
        column
        for column in (
            "date",
            "close",
            "ema_8",
            "ema_21",
            "ema_50",
            "ema_200",
            "rsi_14",
            "macd",
            "macd_signal",
            "macd_histogram",
            "atr_14",
            "vwap",
            "bb_mid",
            "bb_upper",
            "bb_lower",
        )
        if column in result.columns
    ]

    print(result[display_columns].tail(args.tail).to_string(index=False))
    print(
        f"Computed indicators for {args.symbol.upper()}: "
        f"{len(result)} rows."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
