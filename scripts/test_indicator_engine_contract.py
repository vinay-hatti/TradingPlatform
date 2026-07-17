from __future__ import annotations

import numpy as np
import pandas as pd

from trading_ai.indicators.atr import ATR, ATRIndicator
from trading_ai.indicators.ema import EMA, EMAIndicator
from trading_ai.indicators.engine import IndicatorEngine
from trading_ai.indicators.macd import MACD, MACDIndicator
from trading_ai.indicators.rsi import RSI, RSIIndicator
from trading_ai.indicators.vwap import VWAP, VWAPIndicator


def sample_frame(rows: int = 250) -> pd.DataFrame:
    index = pd.date_range("2025-01-01", periods=rows, freq="D")
    close = pd.Series(
        100.0 + np.linspace(0.0, 30.0, rows) + np.sin(np.arange(rows) / 5.0),
        index=index,
    )
    return pd.DataFrame(
        {
            "Date": index,
            "Open": close - 0.5,
            "High": close + 1.0,
            "Low": close - 1.0,
            "Close": close,
            "Volume": np.arange(rows) + 1_000,
        }
    ).reset_index(drop=True)


def main() -> None:
    frame = sample_frame()

    assert EMA(8).calculate(frame["Close"]).notna().all()
    assert RSI(14).calculate(frame["Close"]).notna().sum() > 0
    assert "macd" in MACD().calculate(frame["Close"])
    assert ATR(14).calculate(frame).notna().sum() > 0

    for indicator in (
        EMAIndicator(8),
        RSIIndicator(14),
        MACDIndicator(),
        ATRIndicator(14),
        VWAPIndicator(),
        VWAP(),
    ):
        assert callable(getattr(indicator, "compute", None))

    result = IndicatorEngine().run(frame)
    expected = {
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
    }
    missing = expected.difference(result.columns)
    assert not missing, f"Missing indicator columns: {sorted(missing)}"
    assert "close" in result.columns
    assert "Close" not in result.columns
    assert result["ema_8"].notna().all()
    assert result["vwap"].notna().all()
    assert result["ema_200"].iloc[-1] > 0

    # Simulate yfinance's common single-symbol MultiIndex output.
    multi = frame.drop(columns=["Date"]).copy()
    multi.columns = pd.MultiIndex.from_tuples(
        [(column, "AAPL") for column in multi.columns]
    )
    multi_result = IndicatorEngine().run(multi)
    assert expected.issubset(multi_result.columns)

    print("All indicator compatibility and engine assertions passed.")


if __name__ == "__main__":
    main()
