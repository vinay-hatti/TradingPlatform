from __future__ import annotations
from datetime import datetime, timezone
import math
import numpy as np
import pandas as pd
from .forecast_contracts import TrendForecastSnapshot
from .forecast_policy import TrendForecastPolicy

class TrendForecastEngine:
    def __init__(self, policy: TrendForecastPolicy | None = None):
        self.policy = policy or TrendForecastPolicy()
        self.policy.validate()

    @staticmethod
    def _clip(value: float, low: float, high: float) -> float:
        return float(max(low, min(high, value)))

    def calculate(self, symbol: str, prices: pd.DataFrame, horizon_days: int) -> TrendForecastSnapshot:
        if horizon_days not in self.policy.horizons:
            raise ValueError(f"unsupported horizon: {horizon_days}")
        if prices is None or len(prices) < self.policy.minimum_history_rows:
            raise ValueError(f"insufficient forecast history for {symbol}: {0 if prices is None else len(prices)} rows")
        close = pd.to_numeric(prices["close"], errors="coerce").dropna()
        if len(close) < self.policy.minimum_history_rows:
            raise ValueError(f"insufficient valid close history for {symbol}: {len(close)} rows")
        returns = close.pct_change().dropna()
        short = close.pct_change(horizon_days).iloc[-1]
        medium = close.pct_change(min(63, len(close)-1)).iloc[-1]
        ema20 = close.ewm(span=20, adjust=False).mean().iloc[-1]
        ema50 = close.ewm(span=50, adjust=False).mean().iloc[-1]
        trend_sign = 1.0 if ema20 >= ema50 else -1.0
        recent = returns.tail(max(40, horizon_days * 4))
        drift = float(recent.mean()) * horizon_days
        vol = float(recent.std(ddof=0)) * math.sqrt(horizon_days)
        momentum = self._clip((float(short) * 8.0 + float(medium) * 2.0) * trend_sign, -1.0, 1.0)
        signal_to_noise = abs(drift) / max(vol, 1e-6)
        continuation = self._clip(50.0 + momentum * 22.0 + min(signal_to_noise, 2.0) * 10.0, 5.0, 95.0)
        reversal = self._clip(100.0 - continuation, 5.0, 95.0)
        directional_edge = self._clip(50.0 + trend_sign * (continuation - 50.0), 5.0, 95.0)
        bullish = directional_edge
        bearish = 100.0 - directional_edge
        confidence = self._clip(35.0 + abs(continuation - 50.0) * 1.3 + min(signal_to_noise, 2.0) * 12.0, 0.0, 100.0)
        grade = "A" if confidence >= 80 else "B" if confidence >= 65 else "C" if confidence >= 50 else "D"
        direction = "BULLISH" if bullish >= 58 else "BEARISH" if bearish >= 58 else "NEUTRAL"
        persistence = int(round(self._clip(horizon_days * (continuation / 50.0), 1, 60)))
        expected_return = drift * 100.0
        expected_volatility = vol * 100.0

        # M68.2.1.15.5: the probability model describes continuation/reversal
        # relative to the EMA-defined prevailing trend, while expected_return is
        # an independent realized-drift estimate.  Do not advertise a directional
        # forecast downstream when those authorities materially disagree.
        prevailing_trend_direction = "BULLISH" if trend_sign > 0 else "BEARISH"
        conflict_codes: list[str] = []
        material_return_threshold = max(0.75, expected_volatility * 0.15)
        if direction == "BULLISH" and expected_return < -material_return_threshold:
            conflict_codes.append("EXPECTED_RETURN_DIRECTION_CONFLICT")
        elif direction == "BEARISH" and expected_return > material_return_threshold:
            conflict_codes.append("EXPECTED_RETURN_DIRECTION_CONFLICT")
        if conflict_codes:
            direction = "NEUTRAL"
        base_adjustment = 0.0
        if confidence >= self.policy.minimum_confidence_for_adjustment and not conflict_codes:
            directional_probability = bullish if direction == "BULLISH" else bearish if direction == "BEARISH" else 50.0
            base_adjustment = self._clip((directional_probability - 50.0) / 25.0, 0.0, 1.0) * self.policy.maximum_signal_adjustment
        call_adjustment = base_adjustment if direction == "BULLISH" else -base_adjustment if direction == "BEARISH" else 0.0
        put_adjustment = -call_adjustment
        as_of = prices.index[-1] if getattr(prices.index, "__len__", None) else datetime.now(timezone.utc).date()
        as_of_text = str(getattr(as_of, "date", lambda: as_of)())[:10]
        return TrendForecastSnapshot(
            symbol=symbol.upper(), as_of_date=as_of_text, snapshot_timestamp=datetime.now(timezone.utc),
            horizon_days=horizon_days, continuation_probability=round(continuation, 4),
            reversal_probability=round(reversal, 4), bullish_probability=round(bullish, 4),
            bearish_probability=round(bearish, 4), expected_return_pct=round(expected_return, 6),
            expected_volatility_pct=round(expected_volatility, 6), confidence_score=round(confidence, 4),
            confidence_grade=grade, persistence_days_estimate=persistence, forecast_direction=direction,
            regime_transition_probabilities={"CONTINUATION": round(continuation,4), "REVERSAL": round(reversal,4)},
            signal_adjustment={"CALL": round(call_adjustment,4), "PUT": round(put_adjustment,4)},
            metadata={
                "ema20": float(ema20),
                "ema50": float(ema50),
                "signal_to_noise": signal_to_noise,
                "prevailing_trend_direction": prevailing_trend_direction,
                "directional_consistency": not conflict_codes,
                "conflict_codes": conflict_codes,
                "direction_semantics": "DIRECTIONAL_PROBABILITY_RECONCILED_WITH_EXPECTED_RETURN",
                "continuation_reversal_semantics": "RELATIVE_TO_PREVAILING_EMA_TREND",
            },
        )
