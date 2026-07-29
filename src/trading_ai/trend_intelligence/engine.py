from __future__ import annotations
from datetime import datetime, timezone
import math
import numpy as np
import pandas as pd
from .contracts import TrendHorizon, TrendSnapshot
from .policy import TrendIntelligencePolicy


def clamp(v, lo=0.0, hi=100.0):
    return max(lo, min(float(v), hi))


def _ema(s: pd.Series, span: int) -> pd.Series:
    return s.ewm(span=span, adjust=False, min_periods=max(2, span // 3)).mean()


def _slope_pct(series: pd.Series, lookback: int) -> float:
    x = series.dropna().tail(max(lookback, 3))
    if len(x) < 3 or float(x.iloc[0]) == 0:
        return 0.0
    return float((x.iloc[-1] / x.iloc[0] - 1.0) * 100.0)


def _persistence(close: pd.Series, direction: int, lookback: int) -> float:
    returns = close.pct_change().dropna().tail(lookback)
    if returns.empty:
        return 0.0
    aligned = (returns > 0).mean() if direction >= 0 else (returns < 0).mean()
    return float(aligned * 100.0)


def _horizon(name: str, close: pd.Series, fast: int, slow: int, slope_lb: int) -> TrendHorizon:
    ef, es = _ema(close, fast), _ema(close, slow)
    px, f, s = float(close.iloc[-1]), float(ef.iloc[-1]), float(es.iloc[-1])
    slope = _slope_pct(es, slope_lb)
    px_anchor = (px / s - 1.0) * 100.0 if s else 0.0
    spread = (f / s - 1.0) * 100.0 if s else 0.0
    direction = 1 if px >= s and f >= s and slope >= 0 else -1 if px <= s and f <= s and slope <= 0 else 0
    persistence = _persistence(close, direction or (1 if slope >= 0 else -1), slope_lb)
    magnitude = min(35.0, abs(px_anchor) * 4.0 + abs(spread) * 5.0 + abs(slope) * 2.0)
    quality = clamp(45.0 + magnitude + (persistence - 50.0) * 0.35)
    if direction > 0:
        state = "STRONG_BULLISH" if quality >= 75 else "BULLISH"
        label = "UP"
        score = clamp(55.0 + quality * 0.45)
    elif direction < 0:
        state = "STRONG_BEARISH" if quality >= 75 else "BEARISH"
        label = "DOWN"
        score = clamp(45.0 - quality * 0.45)
    else:
        state = "PULLBACK" if px > s and f < s else "REVERSAL" if px < s and f > s else "SIDEWAYS"
        label = "NEUTRAL"
        score = 50.0
    confidence = clamp(40.0 + min(len(close), slow) / slow * 35.0 + abs(spread) * 3.0 + abs(slope) * 1.5)
    return TrendHorizon(name, label, state, round(score, 2), round(quality, 2), round(confidence, 2), round(slope, 4), round(px_anchor, 4), round(persistence, 2), slope_lb)


def _return(series: pd.Series, lookback: int) -> float:
    x = series.dropna().tail(lookback + 1)
    return float((x.iloc[-1] / x.iloc[0] - 1.0) * 100.0) if len(x) > 1 and x.iloc[0] else 0.0


def _grade(v: float) -> str:
    if v >= 10: return "A+"
    if v >= 5: return "A"
    if v >= 2: return "B"
    if v > -2: return "C"
    if v > -5: return "D"
    return "F"


class TrendIntelligenceEngine:
    VERSION = "trend.v1"
    def __init__(self, policy: TrendIntelligencePolicy | None = None):
        self.policy = policy or TrendIntelligencePolicy()

    def analyze(self, symbol: str, prices: pd.DataFrame, *, benchmark: pd.DataFrame | None = None,
                sector_prices: pd.DataFrame | None = None, sector: str = "Unknown", sector_etf: str = "") -> TrendSnapshot:
        df = prices.copy()
        df.columns = [str(c).lower() for c in df.columns]
        df = df.sort_values("date").drop_duplicates("date")
        close = pd.to_numeric(df["close"], errors="coerce").dropna()
        if len(close) < 30:
            raise ValueError(f"insufficient price history for {symbol}: {len(close)} rows")
        p = self.policy
        short = _horizon("SHORT_TERM", close, p.short_fast, p.short_slow, p.slope_lookback_short)
        intermediate = _horizon("INTERMEDIATE_TERM", close, p.intermediate_fast, p.intermediate_slow, p.slope_lookback_intermediate)
        long = _horizon("LONG_TERM", close, p.long_fast, min(p.long_slow, max(40, len(close)//2)), p.slope_lookback_long)
        signed = lambda h: 1 if h.direction == "UP" else -1 if h.direction == "DOWN" else 0
        weighted_direction = signed(short)*0.25 + signed(intermediate)*0.35 + signed(long)*0.40
        agreement = 100.0 if abs(weighted_direction) >= .99 else 82.0 if abs(weighted_direction) >= .70 else 62.0 if abs(weighted_direction) >= .35 else 45.0
        quality = clamp(short.strength*.25 + intermediate.strength*.35 + long.strength*.40)
        confidence = clamp(short.confidence*.25 + intermediate.confidence*.35 + long.confidence*.40)
        alignment = clamp(agreement*.55 + quality*.25 + confidence*.20)
        call_alignment = clamp(50 + weighted_direction*50) * .70 + alignment*.30
        put_alignment = clamp(50 - weighted_direction*50) * .70 + alignment*.30
        direction_series = np.sign(close.pct_change().fillna(0).rolling(5).mean())
        current_sign = 1 if weighted_direction > .15 else -1 if weighted_direction < -.15 else 0
        age = 0
        for v in reversed(direction_series.tolist()):
            if not math.isfinite(float(v)):
                break
            if current_sign and int(np.sign(v)) == current_sign: age += 1
            else: break
        if abs(weighted_direction) < .20: stage = "ACCUMULATION"
        elif age <= 10: stage = "EARLY_TREND"
        elif age <= 45 and quality >= 55: stage = "ESTABLISHED_TREND"
        elif age > 90 or (quality < 50 and age > 30): stage = "MATURE_OR_EXHAUSTION"
        else: stage = "MATURE_TREND"
        stock_ret = _return(close, min(p.relative_strength_lookback, len(close)-1))
        bench_ret = _return(pd.to_numeric(benchmark["close"], errors="coerce").dropna(), p.relative_strength_lookback) if benchmark is not None and not benchmark.empty else 0.0
        sector_ret = _return(pd.to_numeric(sector_prices["close"], errors="coerce").dropna(), p.relative_strength_lookback) if sector_prices is not None and not sector_prices.empty else 0.0
        rs_spy, rs_sector = stock_ret-bench_ret, stock_ret-sector_ret
        market_align = clamp(50 + np.sign(weighted_direction) * np.sign(bench_ret) * min(abs(bench_ret)*3, 35))
        sector_align = clamp(50 + np.sign(weighted_direction) * np.sign(sector_ret) * min(abs(sector_ret)*3, 35))
        asof = str(pd.to_datetime(df["date"]).max().date())
        warnings=[]
        if len(close) < p.minimum_history_days: warnings.append(f"PARTIAL_LONG_TERM_HISTORY:{len(close)}")
        return TrendSnapshot(symbol, asof, datetime.now(timezone.utc), short, intermediate, long,
            round(alignment,2), {"CALL":round(call_alignment,2),"PUT":round(put_alignment,2)}, round(quality,2),
            round(confidence,2), stage, age, round(rs_spy,4), round(rs_sector,4), _grade((rs_spy+rs_sector)/2),
            sector, sector_etf, round(market_align,2), round(sector_align,2), warnings=warnings,
            metadata={"weighted_direction":round(weighted_direction,4),"price_rows":len(close),"stock_return_63d_pct":round(stock_ret,4),"benchmark_return_63d_pct":round(bench_ret,4),"sector_return_63d_pct":round(sector_ret,4)})
