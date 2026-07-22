from __future__ import annotations
from datetime import date
from math import sqrt
from statistics import mean, pstdev
from typing import Any, Iterable, Mapping
from .contracts import CrossAssetFeatureProfile, CrossAssetGovernanceStatus, CrossAssetUniverseMember
from .policy import CrossAssetFeaturePolicy

class CrossAssetFeatureEngine:
    def __init__(self, policy: CrossAssetFeaturePolicy | None = None) -> None:
        self.policy = policy or CrossAssetFeaturePolicy()

    def evaluate(self, *, member: CrossAssetUniverseMember, as_of_date: date,
                 rows: Iterable[Mapping[str, Any]],
                 benchmark_rows: Iterable[Mapping[str, Any]] | None = None) -> CrossAssetFeatureProfile:
        obs = sorted((self._normalize(r) for r in rows), key=lambda r: r["date"])
        obs = [r for r in obs if r["date"] <= as_of_date]
        closes = [r["close"] for r in obs]
        highs = [r["high"] for r in obs]
        lows = [r["low"] for r in obs]
        volumes = [r["volume"] for r in obs]
        latest_close = closes[-1] if closes else None
        latest_volume = volumes[-1] if volumes else None
        r1, r5, r21 = self._ret(closes, 1), self._ret(closes, 5), self._ret(closes, 21)
        rv = self._rv(closes, 21)
        atr = self._atr(highs, lows, closes, 14)
        atr_pct = atr / latest_close if atr is not None and latest_close not in (None, 0) else None
        ema20, ema50 = self._ema(closes, 20), self._ema(closes, 50)
        trend = self._trend(latest_close, ema20, ema50)
        strength = abs(ema20 - ema50) / latest_close if latest_close not in (None, 0) and ema20 is not None and ema50 is not None else None

        benchmark_return = None
        if benchmark_rows is not None:
            b = sorted((self._normalize(r) for r in benchmark_rows), key=lambda r: r["date"])
            benchmark_return = self._ret([r["close"] for r in b if r["date"] <= as_of_date], 21)
        relative_strength = r21 - benchmark_return if r21 is not None and benchmark_return is not None else None

        avg_volume = mean(volumes[-20:]) if volumes else None
        volume_ratio = latest_volume / avg_volume if latest_volume is not None and avg_volume not in (None, 0) else None
        liquidity = self._liquidity(avg_volume)
        volatility = self._volatility(rv, atr_pct)
        status, reasons = self._govern(len(obs), latest_close, avg_volume, atr_pct, member, relative_strength)

        return CrossAssetFeatureProfile(
            member.symbol, member.asset_class, member.group, member.benchmark_symbol, as_of_date,
            len(obs), latest_close, latest_volume, r1, r5, r21, rv, atr, atr_pct,
            ema20, ema50, trend, strength, volatility, benchmark_return,
            relative_strength, volume_ratio, liquidity, status, tuple(reasons)
        )

    def _govern(self, count, close, avg_volume, atr_pct, member, rs):
        p = self.policy
        if count < p.minimum_observations_review:
            return CrossAssetGovernanceStatus.EXCLUDED, [f"observation count {count} < {p.minimum_observations_review}"]
        status, reasons = CrossAssetGovernanceStatus.READY, []
        if count < p.minimum_observations_ready:
            status = CrossAssetGovernanceStatus.REVIEW
            reasons.append(f"observation count {count} < {p.minimum_observations_ready}")
        if close is None or close < p.minimum_latest_close:
            return CrossAssetGovernanceStatus.EXCLUDED, ["latest close is missing or invalid"]
        if avg_volume is None or avg_volume < p.minimum_average_volume_20d_review:
            return CrossAssetGovernanceStatus.EXCLUDED, ["average volume below minimum"]
        if avg_volume < p.minimum_average_volume_20d_ready:
            status = CrossAssetGovernanceStatus.REVIEW
            reasons.append("average volume below READY threshold")
        if atr_pct is None:
            status = CrossAssetGovernanceStatus.REVIEW
            reasons.append("ATR percentage unavailable")
        elif atr_pct > p.maximum_atr_pct_review:
            return CrossAssetGovernanceStatus.EXCLUDED, ["ATR percentage exceeds maximum"]
        elif atr_pct > p.maximum_atr_pct_ready:
            status = CrossAssetGovernanceStatus.REVIEW
            reasons.append("ATR percentage exceeds READY threshold")
        if p.require_benchmark_for_relative_strength and member.benchmark_symbol and rs is None:
            status = CrossAssetGovernanceStatus.REVIEW
            reasons.append("benchmark-relative strength unavailable")
        return status, reasons

    @staticmethod
    def _normalize(row):
        d = row["date"]
        return {"date": d if isinstance(d, date) else date.fromisoformat(str(d)),
                "high": float(row["high"]), "low": float(row["low"]),
                "close": float(row["close"]), "volume": float(row.get("volume", 0) or 0)}

    @staticmethod
    def _ret(v, n):
        return None if len(v) <= n or v[-n-1] == 0 else v[-1] / v[-n-1] - 1

    def _rv(self, v, n):
        if len(v) <= n: return None
        s = v[-n-1:]
        r = [s[i] / s[i-1] - 1 for i in range(1, len(s)) if s[i-1] != 0]
        return pstdev(r) * sqrt(self.policy.annualization_factor) if len(r) >= 2 else None

    @staticmethod
    def _atr(h, l, c, n):
        if len(c) < n + 1: return None
        tr = [max(h[i]-l[i], abs(h[i]-c[i-1]), abs(l[i]-c[i-1])) for i in range(1, len(c))]
        return mean(tr[-n:])

    @staticmethod
    def _ema(v, n):
        if len(v) < n: return None
        x, m = mean(v[:n]), 2 / (n + 1)
        for y in v[n:]: x = y * m + x * (1 - m)
        return x

    @staticmethod
    def _trend(close, e20, e50):
        if close is None or e20 is None or e50 is None: return "NOT_OBSERVED"
        if close > e20 > e50: return "UP"
        if close < e20 < e50: return "DOWN"
        return "MIXED"

    @staticmethod
    def _volatility(rv, atr):
        if rv is None or atr is None: return "NOT_OBSERVED"
        if rv >= 0.40 or atr >= 0.05: return "HIGH"
        if rv <= 0.15 and atr <= 0.02: return "LOW"
        return "NORMAL"

    def _liquidity(self, avg):
        if avg is None: return "NOT_OBSERVED"
        if avg >= self.policy.minimum_average_volume_20d_ready * 10: return "DEEP"
        if avg >= self.policy.minimum_average_volume_20d_ready: return "ADEQUATE"
        if avg >= self.policy.minimum_average_volume_20d_review: return "THIN"
        return "ILLIQUID"
