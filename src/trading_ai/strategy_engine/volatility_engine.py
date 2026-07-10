import pandas as pd

from trading_ai.strategy_engine.expected_move_engine import ExpectedMoveEngine
from trading_ai.strategy_engine.historical_volatility import HistoricalVolatility
from trading_ai.strategy_engine.iv_percentile import IVPercentile
from trading_ai.strategy_engine.iv_rank import IVRank
from trading_ai.strategy_engine.volatility_profile import VolatilityProfile
from trading_ai.strategy_engine.volatility_regime import VolatilityRegimeClassifier


class VolatilityEngine:
    def __init__(self):
        self.hv = HistoricalVolatility()
        self.iv_rank_calc = IVRank()
        self.iv_percentile_calc = IVPercentile()
        self.expected_move = ExpectedMoveEngine()
        self.regime = VolatilityRegimeClassifier()

    def _iv_history_from_df(self, df: pd.DataFrame) -> list[float]:
        if df is None or df.empty:
            return []

        for col in ["implied_volatility", "iv", "entry_iv"]:
            if col in df.columns:
                return [
                    float(v)
                    for v in df[col].dropna().tolist()
                    if float(v) > 0
                ]

        return []

    def _current_iv(self, df: pd.DataFrame, fallback_hv: float) -> float:
        iv_history = self._iv_history_from_df(df)

        if iv_history:
            return float(iv_history[-1])

        return float(fallback_hv or 0.30)

    def analyze(
        self,
        symbol: str,
        price_history: pd.DataFrame,
        option_history: pd.DataFrame | None = None,
    ) -> VolatilityProfile:
        price_history = price_history.copy()

        hv20 = self.hv.calculate(price_history, 20)
        hv30 = self.hv.calculate(price_history, 30)
        hv60 = self.hv.calculate(price_history, 60)
        hv90 = self.hv.calculate(price_history, 90)

        iv_source = option_history if option_history is not None else price_history
        iv_history = self._iv_history_from_df(iv_source)

        current_iv = self._current_iv(iv_source, hv30)

        iv_low = min(iv_history) if iv_history else current_iv
        iv_high = max(iv_history) if iv_history else current_iv

        iv_rank = self.iv_rank_calc.calculate(
            current_iv=current_iv,
            iv_low=iv_low,
            iv_high=iv_high,
        )

        iv_percentile = self.iv_percentile_calc.calculate(
            current_iv=current_iv,
            iv_history=iv_history,
        )

        hv_base = hv30 if hv30 > 0 else hv20
        iv_hv_ratio = current_iv / hv_base if hv_base > 0 else 0.0

        regime = self.regime.classify(
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            iv_hv_ratio=iv_hv_ratio,
        )

        signal = self.regime.signal(regime)

        close = float(price_history["close"].iloc[-1])

        confidence = self._confidence(
            iv_history=iv_history,
            hv30=hv30,
            current_iv=current_iv,
        )

        return VolatilityProfile(
            symbol=symbol,
            hv20=round(hv20, 4),
            hv30=round(hv30, 4),
            hv60=round(hv60, 4),
            hv90=round(hv90, 4),
            current_iv=round(current_iv, 4),
            iv_rank=round(iv_rank, 2),
            iv_percentile=round(iv_percentile, 2),
            iv_hv_ratio=round(iv_hv_ratio, 2),
            volatility_regime=regime,
            volatility_signal=signal,
            expected_move_1d=round(self.expected_move.calculate(close, current_iv, 1), 2),
            expected_move_5d=round(self.expected_move.calculate(close, current_iv, 5), 2),
            expected_move_10d=round(self.expected_move.calculate(close, current_iv, 10), 2),
            expected_move_30d=round(self.expected_move.calculate(close, current_iv, 30), 2),
            confidence=round(confidence, 2),
        )

    def _confidence(
        self,
        iv_history: list[float],
        hv30: float,
        current_iv: float,
    ) -> float:
        score = 0.0

        if len(iv_history) >= 30:
            score += 40.0
        elif len(iv_history) >= 10:
            score += 25.0
        elif len(iv_history) > 0:
            score += 10.0

        if hv30 > 0:
            score += 30.0

        if current_iv > 0:
            score += 30.0

        return min(score, 100.0)
