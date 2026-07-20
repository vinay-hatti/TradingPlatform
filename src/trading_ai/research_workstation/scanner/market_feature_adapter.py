from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from statistics import mean
from typing import Protocol, Sequence

from .market_data_adapter import MarketBarProfile


@dataclass(frozen=True)
class MarketFeatureSnapshot:
    symbol: str
    price: float
    average_volume: int
    atr_pct: float
    trend_score: float
    momentum_score: float
    liquidity_score: float
    volatility_score: float
    regime_score: float
    signal: str
    regime: str
    metadata: dict


class MarketFeatureAdapter(Protocol):
    def build(
        self,
        symbol: str,
        bars: Sequence[MarketBarProfile],
    ) -> MarketFeatureSnapshot | None:
        ...


class HistoricalFeatureAdapter:
    def __init__(
        self,
        *,
        average_volume_window: int = 20,
        momentum_window: int = 10,
        trend_window: int = 20,
        atr_window: int = 14,
    ):
        self.average_volume_window = average_volume_window
        self.momentum_window = momentum_window
        self.trend_window = trend_window
        self.atr_window = atr_window

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, value))

    @staticmethod
    def _safe_pct(numerator: float, denominator: float) -> float:
        if denominator == 0:
            return 0.0
        value = numerator / denominator
        return value if isfinite(value) else 0.0

    def build(
        self,
        symbol: str,
        bars: Sequence[MarketBarProfile],
    ) -> MarketFeatureSnapshot | None:
        minimum = max(
            self.average_volume_window,
            self.momentum_window + 1,
            self.trend_window,
            self.atr_window + 1,
        )
        if len(bars) < minimum:
            return None

        ordered = sorted(bars, key=lambda item: item.trading_date)
        closes = [bar.close for bar in ordered]
        volumes = [bar.volume for bar in ordered]

        price = closes[-1]
        average_volume = int(mean(volumes[-self.average_volume_window:]))

        previous_close = closes[-2]
        true_ranges: list[float] = []
        for index, bar in enumerate(ordered[-self.atr_window:]):
            absolute_index = len(ordered) - self.atr_window + index
            prior = closes[absolute_index - 1]
            true_ranges.append(
                max(
                    bar.high - bar.low,
                    abs(bar.high - prior),
                    abs(bar.low - prior),
                )
            )
        atr = mean(true_ranges)
        atr_pct = self._safe_pct(atr, price) * 100.0

        trend_reference = mean(closes[-self.trend_window:])
        trend_return = self._safe_pct(price - trend_reference, trend_reference)
        momentum_reference = closes[-(self.momentum_window + 1)]
        momentum_return = self._safe_pct(price - momentum_reference, momentum_reference)

        trend_score = self._clamp(50.0 + trend_return * 500.0)
        momentum_score = self._clamp(50.0 + momentum_return * 500.0)

        liquidity_score = self._clamp(
            20.0 + (average_volume / 1_000_000.0) * 8.0
        )
        volatility_score = self._clamp(atr_pct * 25.0)

        if trend_return > 0.01 and momentum_return > 0:
            signal = "CALL"
            regime = "TREND_UP"
            regime_score = 85.0
        elif trend_return < -0.01 and momentum_return < 0:
            signal = "PUT"
            regime = "TREND_DOWN"
            regime_score = 85.0
        else:
            signal = "NEUTRAL"
            regime = "CHOP"
            regime_score = 45.0

        return MarketFeatureSnapshot(
            symbol=symbol,
            price=price,
            average_volume=average_volume,
            atr_pct=round(atr_pct, 6),
            trend_score=round(trend_score, 6),
            momentum_score=round(momentum_score, 6),
            liquidity_score=round(liquidity_score, 6),
            volatility_score=round(volatility_score, 6),
            regime_score=round(regime_score, 6),
            signal=signal,
            regime=regime,
            metadata={
                "latest_date": ordered[-1].trading_date.isoformat(),
                "bars_used": len(ordered),
                "trend_reference": round(trend_reference, 6),
                "momentum_reference": round(momentum_reference, 6),
                "atr": round(atr, 6),
            },
        )
