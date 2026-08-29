from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import date
from math import sqrt
from statistics import mean
from typing import Iterable, Sequence

from sqlalchemy import text

REGIME_AUTHORITY_VERSION = "M77.3-HISTORICAL-REGIME-AUTHORITY-1.0"


def _pctile(values: Sequence[float], value: float) -> float | None:
    clean = sorted(float(v) for v in values if v is not None)
    if not clean:
        return None
    count = sum(v <= value for v in clean)
    return count / len(clean) * 100.0


def _avg(values):
    values = [float(v) for v in values if v is not None]
    return None if not values else mean(values)


@dataclass(frozen=True)
class HistoricalRegimeSnapshot:
    as_of: date
    regime: str
    trend_state: str
    volatility_state: str
    breadth_state: str
    spy_close: float | None
    spy_sma50: float | None
    spy_sma200: float | None
    spy_return20_pct: float | None
    spy_realized_vol20_pct: float | None
    vol20_percentile_252: float | None
    breadth_above_50d_pct: float | None
    breadth_eligible_symbols: int
    evidence_quality: str
    unavailable_reasons: tuple[str, ...]

    def as_dict(self):
        return {
            "as_of": self.as_of,
            "regime": self.regime,
            "trend_state": self.trend_state,
            "volatility_state": self.volatility_state,
            "breadth_state": self.breadth_state,
            "spy_close": self.spy_close,
            "spy_sma50": self.spy_sma50,
            "spy_sma200": self.spy_sma200,
            "spy_return20_pct": self.spy_return20_pct,
            "spy_realized_vol20_pct": self.spy_realized_vol20_pct,
            "vol20_percentile_252": self.vol20_percentile_252,
            "breadth_above_50d_pct": self.breadth_above_50d_pct,
            "breadth_eligible_symbols": self.breadth_eligible_symbols,
            "evidence_quality": self.evidence_quality,
            "unavailable_reasons": list(self.unavailable_reasons),
        }


class HistoricalRegimeAuthorityService:
    """Read-only point-in-time market-regime reconstruction from price_history.

    The authority intentionally uses only information available on or before each
    replay date. It does not read current market-state publications, future bars,
    sector membership, option/dealer evidence, or production intelligence tables.
    """

    def __init__(self, session):
        self.session = session

    def _load_price_history(self, end: date):
        rows = self.session.execute(
            text(
                """
                SELECT symbol, date, close
                FROM price_history
                WHERE date <= :end
                  AND close IS NOT NULL
                  AND close > 0
                ORDER BY symbol, date
                """
            ),
            {"end": end},
        ).mappings().all()
        by_symbol = defaultdict(list)
        for row in rows:
            by_symbol[str(row["symbol"])].append(
                (row["date"], float(row["close"]))
            )
        return by_symbol

    @staticmethod
    def _symbol_features(series):
        out = {}
        closes = []
        vol20_history = []
        previous = None
        returns = deque(maxlen=20)
        for as_of, close in series:
            closes.append(close)
            if previous is not None and previous > 0:
                returns.append(close / previous - 1.0)
            previous = close

            sma50 = mean(closes[-50:]) if len(closes) >= 50 else None
            sma200 = mean(closes[-200:]) if len(closes) >= 200 else None
            ret20 = (
                (close / closes[-21] - 1.0) * 100.0
                if len(closes) >= 21 and closes[-21] > 0
                else None
            )
            vol20 = None
            if len(returns) >= 20:
                r = list(returns)
                rmean = mean(r)
                variance = sum((value - rmean) ** 2 for value in r) / max(1, len(r) - 1)
                vol20 = sqrt(variance) * sqrt(252.0) * 100.0
                vol20_history.append(vol20)
            vol_percentile = (
                _pctile(vol20_history[-252:], vol20)
                if vol20 is not None
                else None
            )
            out[as_of] = {
                "close": close,
                "sma50": sma50,
                "sma200": sma200,
                "ret20": ret20,
                "vol20": vol20,
                "vol_percentile": vol_percentile,
                "above50": None if sma50 is None else close > sma50,
            }
        return out

    @staticmethod
    def _trend_state(spy):
        close, sma50, sma200, ret20 = (
            spy.get("close"), spy.get("sma50"), spy.get("sma200"), spy.get("ret20")
        )
        if None in (close, sma50, sma200, ret20):
            return "UNKNOWN"
        if close > sma50 > sma200 and ret20 > 0:
            return "BULL_TREND"
        if close < sma50 < sma200 and ret20 < 0:
            return "BEAR_TREND"
        if close > sma50 and sma50 <= sma200:
            return "TRANSITION_UP"
        if close < sma50 and sma50 >= sma200:
            return "TRANSITION_DOWN"
        return "RANGE_MIXED"

    @staticmethod
    def _volatility_state(percentile):
        if percentile is None:
            return "UNKNOWN"
        if percentile >= 90:
            return "EXTREME"
        if percentile >= 75:
            return "HIGH"
        if percentile <= 25:
            return "LOW"
        return "NORMAL"

    @staticmethod
    def _breadth_state(breadth):
        if breadth is None:
            return "UNKNOWN"
        if breadth >= 65:
            return "BROAD_STRONG"
        if breadth <= 35:
            return "BROAD_WEAK"
        return "MIXED"

    @staticmethod
    def _composite(trend, vol, breadth):
        if "UNKNOWN" in (trend, vol, breadth):
            return "UNKNOWN"
        stressed = vol in {"HIGH", "EXTREME"}
        if trend == "BULL_TREND":
            return "BULL_STRESSED" if stressed or breadth == "BROAD_WEAK" else "BULL_HEALTHY"
        if trend == "BEAR_TREND":
            return "BEAR_STRESSED" if stressed else "BEAR_ORDERLY"
        if trend in {"TRANSITION_UP", "TRANSITION_DOWN"}:
            return trend
        return "RANGE_STRESSED" if stressed else "RANGE_NORMAL"

    def build_authority(self, replay_dates: Iterable[date]):
        replay_dates = sorted(set(replay_dates))
        if not replay_dates:
            return {}
        by_symbol = self._load_price_history(max(replay_dates))
        features = {
            symbol: self._symbol_features(series)
            for symbol, series in by_symbol.items()
        }
        spy = features.get("SPY", {})
        snapshots = {}
        for as_of in replay_dates:
            reasons = []
            spy_row = spy.get(as_of)
            if not spy_row:
                reasons.append("SPY_BAR_UNAVAILABLE")
                snapshots[as_of] = HistoricalRegimeSnapshot(
                    as_of, "UNKNOWN", "UNKNOWN", "UNKNOWN", "UNKNOWN",
                    None, None, None, None, None, None, None, 0,
                    "INSUFFICIENT", tuple(reasons),
                )
                continue

            breadth_values = []
            for symbol, series_features in features.items():
                if symbol in {"SPX", "NDX", "RUT"}:
                    continue
                row = series_features.get(as_of)
                if row and row.get("above50") is not None:
                    breadth_values.append(bool(row["above50"]))
            breadth = (
                sum(breadth_values) / len(breadth_values) * 100.0
                if breadth_values else None
            )
            trend = self._trend_state(spy_row)
            vol = self._volatility_state(spy_row.get("vol_percentile"))
            breadth_state = self._breadth_state(breadth)
            if trend == "UNKNOWN":
                reasons.append("SPY_TREND_WARMUP_INCOMPLETE")
            if vol == "UNKNOWN":
                reasons.append("VOLATILITY_WARMUP_INCOMPLETE")
            if breadth_state == "UNKNOWN":
                reasons.append("BREADTH_UNAVAILABLE")
            regime = self._composite(trend, vol, breadth_state)
            quality = "FULL" if not reasons else "PARTIAL"
            snapshots[as_of] = HistoricalRegimeSnapshot(
                as_of=as_of,
                regime=regime,
                trend_state=trend,
                volatility_state=vol,
                breadth_state=breadth_state,
                spy_close=spy_row.get("close"),
                spy_sma50=spy_row.get("sma50"),
                spy_sma200=spy_row.get("sma200"),
                spy_return20_pct=spy_row.get("ret20"),
                spy_realized_vol20_pct=spy_row.get("vol20"),
                vol20_percentile_252=spy_row.get("vol_percentile"),
                breadth_above_50d_pct=breadth,
                breadth_eligible_symbols=len(breadth_values),
                evidence_quality=quality,
                unavailable_reasons=tuple(reasons),
            )
        return snapshots
