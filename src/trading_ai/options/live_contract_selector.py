from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math

from trading_ai.options.live_snapshot import (
    LiveOptionContract,
    LiveOptionDataError,
    PolygonOptionSnapshotProvider,
)


@dataclass(frozen=True)
class LiveContractSelectionPolicy:
    target_abs_delta: float = 0.45
    maximum_spread_pct: float = 0.25
    minimum_open_interest: int = 100
    minimum_volume: int = 10
    liquidity_data_mode: str = "adaptive"
    expiration_window_days: int = 10
    strike_window_pct: float = 0.15

    # Contract-ranking weights. Liquidity receives 55% of the total score so
    # executable contracts are preferred over otherwise-similar contracts.
    delta_weight: float = 0.20
    expiration_weight: float = 0.15
    strike_weight: float = 0.10
    spread_weight: float = 0.25
    open_interest_weight: float = 0.18
    volume_weight: float = 0.12

    # Adaptive mode remains usable when Polygon does not provide a two-sided
    # quote, but a last-only contract must not score like a tradable quote.
    unavailable_liquidity_score: float = 20.0

    # Smooth expiration curve. A contract exactly on the requested expiration
    # scores 100; the score decays continuously as it moves away.
    minimum_expiration_score: float = 5.0

    def validate(self):
        if self.liquidity_data_mode not in {"adaptive", "strict"}:
            raise ValueError("liquidity_data_mode must be adaptive or strict")
        if self.maximum_spread_pct <= 0:
            raise ValueError("maximum_spread_pct must be greater than zero")
        if self.expiration_window_days <= 0:
            raise ValueError("expiration_window_days must be greater than zero")
        if not math.isclose(sum(self.weights().values()), 1.0, abs_tol=1e-9):
            raise ValueError("selection weights must total 1.0")

    def weights(self):
        return {
            "delta": self.delta_weight,
            "expiration": self.expiration_weight,
            "strike": self.strike_weight,
            "spread": self.spread_weight,
            "open_interest": self.open_interest_weight,
            "volume": self.volume_weight,
        }


@dataclass(frozen=True)
class ContractScoreBreakdown:
    total_score: float
    liquidity_score: float
    delta_score: float
    expiration_score: float
    strike_score: float
    spread_score: float
    open_interest_score: float
    volume_score: float
    open_interest_available: bool
    volume_available: bool
    spread_available: bool


@dataclass(frozen=True)
class SelectedLiveOptionContract:
    contract: LiveOptionContract
    score: ContractScoreBreakdown

    def __getattr__(self, name):
        return getattr(self.contract, name)


@dataclass
class EligibilityDiagnostics:
    total: int = 0
    accepted: int = 0
    no_price: int = 0
    expired: int = 0
    missing_greeks: int = 0
    low_open_interest: int = 0
    low_volume: int = 0
    wide_spread: int = 0
    missing_open_interest: int = 0
    missing_volume: int = 0
    missing_spread: int = 0

    def summary(self):
        return (
            f"total={self.total}, accepted={self.accepted}, "
            f"no_price={self.no_price}, expired={self.expired}, "
            f"missing_greeks={self.missing_greeks}, low_OI={self.low_open_interest}, "
            f"low_volume={self.low_volume}, wide_spread={self.wide_spread}, "
            f"missing_OI={self.missing_open_interest}, "
            f"missing_volume={self.missing_volume}, "
            f"missing_spread={self.missing_spread}"
        )


class LiveOptionContractSelector:
    def __init__(self, provider=None, policy=None):
        self.provider = provider or PolygonOptionSnapshotProvider()
        self.policy = policy or LiveContractSelectionPolicy()
        self.policy.validate()
        self.last_diagnostics = EligibilityDiagnostics()

    @staticmethod
    def _available_oi(c):
        return c.open_interest > 0

    @staticmethod
    def _available_volume(c):
        return c.volume > 0

    @staticmethod
    def _available_spread(c):
        return (
            math.isfinite(c.spread_pct)
            and c.bid > 0
            and c.ask > 0
            and c.ask >= c.bid
        )

    @staticmethod
    def _clamp(x):
        return max(0.0, min(100.0, float(x)))

    @staticmethod
    def _log_norm(value, maximum):
        return (
            0.0
            if maximum <= 0
            else 100.0 * math.log1p(max(value, 0)) / math.log1p(maximum)
        )

    def _eligible(self, contracts):
        d = EligibilityDiagnostics()
        accepted = []
        for c in contracts:
            d.total += 1
            if c.entry_price <= 0:
                d.no_price += 1
                continue
            if c.dte <= 0:
                d.expired += 1
                continue
            if not all(
                math.isfinite(x)
                for x in (c.delta, c.gamma, c.theta, c.vega)
            ):
                d.missing_greeks += 1
                continue

            oi_ok = self._available_oi(c)
            vol_ok = self._available_volume(c)
            spr_ok = self._available_spread(c)

            if not oi_ok:
                d.missing_open_interest += 1
                if self.policy.liquidity_data_mode == "strict":
                    continue
            elif c.open_interest < self.policy.minimum_open_interest:
                d.low_open_interest += 1
                continue

            if not vol_ok:
                d.missing_volume += 1
                if self.policy.liquidity_data_mode == "strict":
                    continue
            elif c.volume < self.policy.minimum_volume:
                d.low_volume += 1
                continue

            if not spr_ok:
                d.missing_spread += 1
                if self.policy.liquidity_data_mode == "strict":
                    continue
            elif c.spread_pct > self.policy.maximum_spread_pct:
                d.wide_spread += 1
                continue

            d.accepted += 1
            accepted.append(c)

        self.last_diagnostics = d
        return accepted

    def _expiration_score(self, expiration_date, target_expiration):
        """Smooth preference curve centered on the requested expiration."""
        error_days = abs((expiration_date - target_expiration).days)
        sigma = max(float(self.policy.expiration_window_days) / 2.0, 1.0)
        gaussian = 100.0 * math.exp(-0.5 * (error_days / sigma) ** 2)
        return self._clamp(max(self.policy.minimum_expiration_score, gaussian))

    def _spread_score(self, c):
        """Score real Polygon bid/ask values using executable spread quality."""
        if not self._available_spread(c):
            return self.policy.unavailable_liquidity_score

        # Linear score inside the configured maximum spread. A locked market
        # scores 100; a quote at the maximum accepted spread scores 0.
        return self._clamp(
            100.0 * (1.0 - c.spread_pct / self.policy.maximum_spread_pct)
        )

    def _score(self, c, target_expiration, target_strike, max_oi, max_vol):
        delta_score = self._clamp(
            100
            * (
                1
                - abs(abs(c.delta) - self.policy.target_abs_delta)
                / 0.25
            )
        )
        expiration_score = self._expiration_score(
            date.fromisoformat(c.expiration_date),
            target_expiration,
        )
        strike_err = abs(c.strike - target_strike) / max(target_strike, 0.01)
        strike_score = self._clamp(
            100 * (1 - strike_err / self.policy.strike_window_pct)
        )

        oi_av = self._available_oi(c)
        vol_av = self._available_volume(c)
        spr_av = self._available_spread(c)

        oi_score = (
            self._log_norm(c.open_interest, max_oi)
            if oi_av
            else self.policy.unavailable_liquidity_score
        )
        vol_score = (
            self._log_norm(c.volume, max_vol)
            if vol_av
            else self.policy.unavailable_liquidity_score
        )
        spread_score = self._spread_score(c)

        w = self.policy.weights()
        total = (
            delta_score * w["delta"]
            + expiration_score * w["expiration"]
            + strike_score * w["strike"]
            + spread_score * w["spread"]
            + oi_score * w["open_interest"]
            + vol_score * w["volume"]
        )
        liquidity_weight = (
            w["spread"] + w["open_interest"] + w["volume"]
        )
        liquidity = (
            spread_score * w["spread"]
            + oi_score * w["open_interest"]
            + vol_score * w["volume"]
        ) / liquidity_weight

        return ContractScoreBreakdown(
            round(total, 6),
            round(liquidity, 6),
            round(delta_score, 6),
            round(expiration_score, 6),
            round(strike_score, 6),
            round(spread_score, 6),
            round(oi_score, 6),
            round(vol_score, 6),
            oi_av,
            vol_av,
            spr_av,
        )

    def rank(self, *, underlying, signal, target_expiration, target_strike, as_of):
        contracts = self.provider.chain(
            underlying,
            signal=signal,
            target_expiration=target_expiration,
            target_strike=target_strike,
            as_of=as_of,
            expiration_window_days=self.policy.expiration_window_days,
            strike_window_pct=self.policy.strike_window_pct,
        )
        eligible = self._eligible(contracts)
        if not eligible:
            raise LiveOptionDataError(
                f"No listed {signal} contracts for {underlying} passed filters. "
                f"Mode={self.policy.liquidity_data_mode}; "
                f"OI>={self.policy.minimum_open_interest}, "
                f"volume>={self.policy.minimum_volume}, "
                f"spread<={self.policy.maximum_spread_pct:.1%}. "
                f"Diagnostics: {self.last_diagnostics.summary()}."
            )

        max_oi = max((c.open_interest for c in eligible), default=0)
        max_vol = max((c.volume for c in eligible), default=0)
        ranked = [
            SelectedLiveOptionContract(
                c,
                self._score(
                    c,
                    target_expiration,
                    target_strike,
                    max_oi,
                    max_vol,
                ),
            )
            for c in eligible
        ]
        return sorted(
            ranked,
            key=lambda x: (
                x.score.total_score,
                x.score.liquidity_score,
                x.score.spread_score,
                x.open_interest,
                x.volume,
            ),
            reverse=True,
        )

    def select(self, **kwargs):
        return self.rank(**kwargs)[0]
