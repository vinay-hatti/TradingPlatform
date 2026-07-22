from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date
from statistics import median
from typing import Iterable, Sequence

from .contracts import (
    GovernanceStatus,
    ObservationStatus,
    OptionChainQualityProfile,
)
from .policy import OptionChainQualityPolicy


@dataclass(frozen=True)
class OptionContractQualityRow:
    underlying_symbol: str
    quote_date: date
    bid: float | None
    ask: float | None
    last: float | None
    volume: int | None
    open_interest: int | None
    implied_volatility: float | None
    delta: float | None
    gamma: float | None
    theta: float | None
    vega: float | None


class OptionChainQualityEngine:
    BASE_WEIGHTS = {
        "quote": 0.20,
        "trade": 0.10,
        "liquidity": 0.20,
        "spread": 0.20,
        "iv": 0.15,
        "greeks": 0.15,
    }

    def __init__(
        self,
        policy: OptionChainQualityPolicy | None = None,
    ) -> None:
        self.policy = policy or OptionChainQualityPolicy()

    def evaluate(
        self,
        rows: Iterable[OptionContractQualityRow],
        *,
        quote_date: date,
        expected_symbols: Sequence[str] | None = None,
    ) -> tuple[OptionChainQualityProfile, ...]:
        materialized = tuple(rows)
        grouped: dict[str, list[OptionContractQualityRow]] = defaultdict(list)

        for row in materialized:
            symbol = str(row.underlying_symbol).strip().upper()
            if symbol:
                grouped[symbol].append(row)

        if expected_symbols is not None:
            for symbol in expected_symbols:
                normalized = str(symbol).strip().upper()
                if normalized:
                    grouped.setdefault(normalized, [])

        # Provider/run-level capability detection. If not one contract has an
        # NBBO quote, quote and spread dimensions are unavailable rather than
        # universally bad.
        run_quote_observed = any(
            row.bid is not None and row.ask is not None
            for row in materialized
        )

        return tuple(
            self._evaluate_symbol(
                symbol=symbol,
                quote_date=quote_date,
                rows=grouped[symbol],
                run_quote_observed=run_quote_observed,
            )
            for symbol in sorted(grouped)
        )

    def _evaluate_symbol(
        self,
        *,
        symbol: str,
        quote_date: date,
        rows: Sequence[OptionContractQualityRow],
        run_quote_observed: bool,
    ) -> OptionChainQualityProfile:
        count = len(rows)
        quoted = traded = liquid = valid_spread = 0
        crossed = locked = negative = 0
        iv_available = delta_available = full_greeks = 0
        spreads: list[float] = []

        for row in rows:
            if any(
                value is not None and value < 0
                for value in (row.bid, row.ask, row.last)
            ):
                negative += 1

            has_quote = row.bid is not None and row.ask is not None
            if has_quote:
                quoted += 1
                if row.ask < row.bid:
                    crossed += 1
                elif row.ask == row.bid:
                    locked += 1
                    valid_spread += 1
                    spreads.append(0.0)
                else:
                    midpoint = (row.bid + row.ask) / 2.0
                    if midpoint > 0:
                        valid_spread += 1
                        spreads.append((row.ask - row.bid) / midpoint)

            if row.last is not None:
                traded += 1

            if (
                (row.volume or 0) >= self.policy.minimum_volume
                and (row.open_interest or 0) >= self.policy.minimum_open_interest
            ):
                liquid += 1

            if row.implied_volatility is not None and row.implied_volatility > 0:
                iv_available += 1
            if row.delta is not None:
                delta_available += 1
            if all(
                value is not None
                for value in (row.delta, row.gamma, row.theta, row.vega)
            ):
                full_greeks += 1

        quote_score = self._ratio(quoted, count)
        trade_score = self._ratio(traded, count)
        liquidity_score = self._ratio(liquid, count)
        spread_score = self._ratio(valid_spread, quoted) if quoted else 0.0
        iv_score = self._ratio(iv_available, count)
        greeks_score = self._ratio(full_greeks, count)

        quote_status = self._observation_status(
            observed=quoted,
            total=count,
            dimension_available=run_quote_observed,
        )
        spread_status = self._observation_status(
            observed=valid_spread,
            total=quoted,
            dimension_available=run_quote_observed,
        )

        scores = {
            "quote": quote_score,
            "trade": trade_score,
            "liquidity": liquidity_score,
            "spread": spread_score,
            "iv": iv_score,
            "greeks": greeks_score,
        }
        observed_dimensions = {"trade", "liquidity", "iv", "greeks"}
        if run_quote_observed:
            observed_dimensions.update({"quote", "spread"})

        weight_total = sum(
            self.BASE_WEIGHTS[name] for name in observed_dimensions
        )
        overall = (
            sum(
                self.BASE_WEIGHTS[name] * scores[name]
                for name in observed_dimensions
            ) / weight_total
            if weight_total
            else 0.0
        )
        overall = self.policy.clamp(overall)

        status, reasons, notes = self._govern(
            contract_count=count,
            quote_score=quote_score,
            trade_score=trade_score,
            liquidity_score=liquidity_score,
            spread_score=spread_score,
            iv_score=iv_score,
            greeks_score=greeks_score,
            overall_score=overall,
            crossed=crossed,
            negative=negative,
            run_quote_observed=run_quote_observed,
        )

        return OptionChainQualityProfile(
            symbol=symbol,
            quote_date=quote_date,
            contract_count=count,
            quoted_contracts=quoted,
            traded_contracts=traded,
            liquid_contracts=liquid,
            valid_spread_contracts=valid_spread,
            crossed_market_contracts=crossed,
            locked_market_contracts=locked,
            negative_market_value_contracts=negative,
            iv_available_contracts=iv_available,
            delta_available_contracts=delta_available,
            full_greeks_contracts=full_greeks,
            quote_observation_status=quote_status,
            spread_observation_status=spread_status,
            quote_completeness_score=round(quote_score, 6),
            trade_completeness_score=round(trade_score, 6),
            liquidity_score=round(liquidity_score, 6),
            spread_integrity_score=round(spread_score, 6),
            iv_completeness_score=round(iv_score, 6),
            greeks_completeness_score=round(greeks_score, 6),
            overall_quality_score=round(overall, 6),
            average_spread_pct=(
                round(sum(spreads) / len(spreads), 8) if spreads else None
            ),
            median_spread_pct=(
                round(float(median(spreads)), 8) if spreads else None
            ),
            maximum_spread_pct=round(max(spreads), 8) if spreads else None,
            governance_status=status,
            governance_reasons=tuple(reasons),
            informational_notes=tuple(notes),
        )

    def _govern(
        self,
        *,
        contract_count: int,
        quote_score: float,
        trade_score: float,
        liquidity_score: float,
        spread_score: float,
        iv_score: float,
        greeks_score: float,
        overall_score: float,
        crossed: int,
        negative: int,
        run_quote_observed: bool,
    ):
        failures: list[str] = []
        reasons: list[str] = []
        notes: list[str] = []

        if contract_count == 0:
            failures.append("no option contracts")
        if negative > 0:
            failures.append(f"negative market values: {negative}")

        # Only govern dimensions that the provider actually supplied.
        if run_quote_observed:
            if quote_score < self.policy.review_quote_completeness:
                failures.append(
                    f"quote completeness {quote_score:.3f} < "
                    f"{self.policy.review_quote_completeness:.3f}"
                )
            elif quote_score < self.policy.minimum_quote_completeness:
                reasons.append(
                    f"quote completeness {quote_score:.3f} < "
                    f"{self.policy.minimum_quote_completeness:.3f}"
                )

            if spread_score < self.policy.review_spread_integrity_score:
                failures.append(
                    f"spread integrity {spread_score:.3f} < "
                    f"{self.policy.review_spread_integrity_score:.3f}"
                )
            elif spread_score < self.policy.minimum_spread_integrity_score:
                reasons.append(
                    f"spread integrity {spread_score:.3f} < "
                    f"{self.policy.minimum_spread_integrity_score:.3f}"
                )
        else:
            notes.append(
                "NBBO quote/spread data not observed for this provider run; "
                "dimensions excluded from governance score"
            )

        if liquidity_score < self.policy.review_liquidity_score:
            failures.append(
                f"liquidity {liquidity_score:.3f} < "
                f"{self.policy.review_liquidity_score:.3f}"
            )
        elif liquidity_score < self.policy.minimum_liquidity_score:
            reasons.append(
                f"liquidity {liquidity_score:.3f} < "
                f"{self.policy.minimum_liquidity_score:.3f}"
            )

        if iv_score < self.policy.review_iv_completeness:
            failures.append(
                f"IV completeness {iv_score:.3f} < "
                f"{self.policy.review_iv_completeness:.3f}"
            )
        elif iv_score < self.policy.minimum_iv_completeness:
            reasons.append(
                f"IV completeness {iv_score:.3f} < "
                f"{self.policy.minimum_iv_completeness:.3f}"
            )

        if greeks_score < self.policy.review_greeks_completeness:
            failures.append(
                f"Greeks completeness {greeks_score:.3f} < "
                f"{self.policy.review_greeks_completeness:.3f}"
            )
        elif greeks_score < self.policy.minimum_greeks_completeness:
            reasons.append(
                f"Greeks completeness {greeks_score:.3f} < "
                f"{self.policy.minimum_greeks_completeness:.3f}"
            )

        if overall_score < self.policy.review_overall_score:
            failures.append(
                f"overall quality {overall_score:.3f} < "
                f"{self.policy.review_overall_score:.3f}"
            )
        elif overall_score < self.policy.ready_overall_score:
            reasons.append(
                f"overall quality {overall_score:.3f} < "
                f"{self.policy.ready_overall_score:.3f}"
            )

        if failures:
            return GovernanceStatus.FAILED, failures, notes

        # Sparse but otherwise valid chains are reviewable, not corrupt.
        if contract_count < self.policy.minimum_contracts_per_symbol:
            reasons.append(
                f"sparse chain: contracts {contract_count} < "
                f"{self.policy.minimum_contracts_per_symbol}"
            )

        if crossed > 0:
            reasons.append(f"crossed markets: {crossed}")

        if reasons:
            return GovernanceStatus.REVIEW, reasons, notes

        return GovernanceStatus.READY, [], notes

    @staticmethod
    def _observation_status(
        *,
        observed: int,
        total: int,
        dimension_available: bool,
    ) -> ObservationStatus:
        if not dimension_available:
            return ObservationStatus.NOT_OBSERVED
        if total <= 0 or observed <= 0:
            return ObservationStatus.NOT_OBSERVED
        if observed < total:
            return ObservationStatus.PARTIAL
        return ObservationStatus.OBSERVED

    @staticmethod
    def _ratio(numerator: int, denominator: int) -> float:
        return numerator / denominator if denominator > 0 else 0.0
