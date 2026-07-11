from collections import Counter, defaultdict

from trading_ai.strategy_engine.portfolio_allocator import (
    PortfolioAllocator,
)
from trading_ai.strategy_engine.portfolio_construction_result import (
    PortfolioConstructionResult,
    PortfolioRejection,
)
from trading_ai.strategy_engine.portfolio_exposure import (
    PortfolioExposure,
)
from trading_ai.strategy_engine.portfolio_risk_limits import (
    PortfolioRiskLimits,
)


class PortfolioConstructor:
    """
    Greedy institutional portfolio constructor.

    Ranked opportunities are evaluated from highest to lowest score.
    Each accepted position changes the remaining capital, risk,
    concentration, and Greeks capacity.
    """

    def __init__(
        self,
        limits: PortfolioRiskLimits | None = None,
    ):
        self.limits = (
            limits
            or PortfolioRiskLimits()
        )

        self.limits.validate()

        self.allocator = PortfolioAllocator(
            self.limits
        )

    def construct(
        self,
        ranked_opportunities,
    ) -> PortfolioConstructionResult:
        ordered = sorted(
            ranked_opportunities,
            key=lambda item: (
                item.allowed,
                item.selected,
                item.ranking_score,
                item.raw_ranking_score,
            ),
            reverse=True,
        )

        positions = []
        rejected = []

        for ranked in ordered:
            reasons = self._candidate_rejections(
                ranked
            )

            if reasons:
                rejected.append(
                    PortfolioRejection(
                        symbol=(
                            ranked.opportunity.symbol
                        ),
                        strategy=(
                            ranked.opportunity.strategy
                        ),
                        ranking_score=(
                            ranked.ranking_score
                        ),
                        reasons=reasons,
                        warnings=list(
                            ranked.warnings
                        ),
                    )
                )
                continue

            current_exposure = self.calculate_exposure(
                positions
            )

            remaining_exposure = max(
                self.limits.maximum_portfolio_exposure_dollars
                - current_exposure.total_capital_allocated,
                0.0,
            )

            remaining_risk = max(
                self.limits.maximum_total_risk_dollars
                - current_exposure.total_maximum_loss,
                0.0,
            )

            position = self.allocator.allocate(
                ranked_opportunity=ranked,
                remaining_exposure_dollars=(
                    remaining_exposure
                ),
                remaining_risk_dollars=(
                    remaining_risk
                ),
            )

            if position is None:
                rejected.append(
                    PortfolioRejection(
                        symbol=(
                            ranked.opportunity.symbol
                        ),
                        strategy=(
                            ranked.opportunity.strategy
                        ),
                        ranking_score=(
                            ranked.ranking_score
                        ),
                        reasons=[
                            "POSITION_SIZE_BELOW_MINIMUM_OR_CAPACITY_EXHAUSTED"
                        ],
                        warnings=list(
                            ranked.warnings
                        ),
                    )
                )
                continue

            position_reasons = (
                self._position_rejections(
                    position=position,
                    existing_positions=positions,
                )
            )

            if position_reasons:
                rejected.append(
                    PortfolioRejection(
                        symbol=position.symbol,
                        strategy=position.strategy,
                        ranking_score=(
                            position.ranking_score
                        ),
                        reasons=position_reasons,
                        warnings=position.warnings,
                    )
                )
                continue

            positions.append(position)

            if (
                len(positions)
                >= self.limits.maximum_positions
            ):
                break

        exposure = self.calculate_exposure(
            positions
        )

        warnings = self._portfolio_warnings(
            exposure
        )

        recommendations = (
            self._portfolio_recommendations(
                exposure=exposure,
                positions=positions,
                rejected=rejected,
            )
        )

        risk_score = self._risk_score(
            exposure
        )

        diversification_score = (
            self._diversification_score(
                exposure
            )
        )

        capital_efficiency_score = (
            self._capital_efficiency_score(
                exposure
            )
        )

        portfolio_score = round(
            risk_score * 0.40
            + diversification_score * 0.35
            + capital_efficiency_score * 0.25,
            2,
        )

        valid = (
            bool(positions)
            and not self._hard_portfolio_violations(
                exposure
            )
        )

        readiness = self._readiness(
            positions=positions,
            portfolio_score=portfolio_score,
            valid=valid,
        )

        return PortfolioConstructionResult(
            positions=positions,
            rejected=rejected,
            exposure=exposure,
            valid=valid,
            readiness=readiness,
            portfolio_score=portfolio_score,
            diversification_score=round(
                diversification_score,
                2,
            ),
            risk_score=round(
                risk_score,
                2,
            ),
            capital_efficiency_score=round(
                capital_efficiency_score,
                2,
            ),
            warnings=warnings,
            recommendations=recommendations,
            metadata={
                "limits": self.limits,
                "candidate_count": len(
                    ranked_opportunities
                ),
                "accepted_count": len(positions),
                "rejected_count": len(rejected),
            },
        )

    # -------------------------------------------------
    # Candidate-level checks
    # -------------------------------------------------

    def _candidate_rejections(
        self,
        ranked,
    ) -> list[str]:
        opportunity = ranked.opportunity
        reasons = []

        if not ranked.allowed:
            reasons.append(
                "RANKED_OPPORTUNITY_NOT_ALLOWED"
            )

        if not ranked.selected:
            reasons.append(
                "RANKED_OPPORTUNITY_NOT_SELECTED"
            )

        if (
            ranked.ranking_score
            < self.limits.minimum_ranking_score
        ):
            reasons.append(
                "RANKING_SCORE_BELOW_PORTFOLIO_MINIMUM"
            )

        if (
            opportunity.strategy_score
            < self.limits.minimum_strategy_score
        ):
            reasons.append(
                "STRATEGY_SCORE_BELOW_PORTFOLIO_MINIMUM"
            )

        if (
            opportunity.portfolio_fit_score
            < self.limits.minimum_portfolio_fit_score
        ):
            reasons.append(
                "PORTFOLIO_FIT_BELOW_MINIMUM"
            )

        if (
            opportunity.risk_profile
            == "UNDEFINED_RISK"
            and not self.limits.allow_undefined_risk
        ):
            reasons.append(
                "UNDEFINED_RISK_NOT_ALLOWED"
            )

        if (
            opportunity.maximum_loss <= 0
            and not self.limits.allow_zero_maximum_loss
        ):
            reasons.append(
                "MAXIMUM_LOSS_UNAVAILABLE"
            )

        if (
            not self.limits.allow_research_positions
            and opportunity.readiness
            not in {
                "LIVE_CANDIDATE",
                "PAPER_TRADING",
                "RESEARCH_READY",
            }
        ):
            reasons.append(
                "READINESS_NOT_PORTFOLIO_ELIGIBLE"
            )

        return list(dict.fromkeys(reasons))

    # -------------------------------------------------
    # Position-level portfolio checks
    # -------------------------------------------------

    def _position_rejections(
        self,
        position,
        existing_positions,
    ) -> list[str]:
        reasons = []

        proposed = (
            list(existing_positions)
            + [position]
        )

        exposure = self.calculate_exposure(
            proposed
        )

        if (
            exposure.total_capital_allocated
            > self.limits.maximum_portfolio_exposure_dollars
            + 0.01
        ):
            reasons.append(
                "MAXIMUM_PORTFOLIO_EXPOSURE_EXCEEDED"
            )

        if (
            exposure.total_maximum_loss
            > self.limits.maximum_total_risk_dollars
            + 0.01
        ):
            reasons.append(
                "MAXIMUM_TOTAL_RISK_EXCEEDED"
            )

        if (
            position.capital_required
            > self.limits.maximum_position_dollars
            + 0.01
        ):
            reasons.append(
                "MAXIMUM_POSITION_SIZE_EXCEEDED"
            )

        if (
            position.maximum_loss
            > self.limits.maximum_risk_per_trade_dollars
            + 0.01
        ):
            reasons.append(
                "MAXIMUM_RISK_PER_TRADE_EXCEEDED"
            )

        reasons.extend(
            self._count_limit_rejections(
                position,
                proposed,
            )
        )

        reasons.extend(
            self._exposure_limit_rejections(
                position,
                exposure,
            )
        )

        reasons.extend(
            self._greeks_limit_rejections(
                exposure
            )
        )

        return list(dict.fromkeys(reasons))

    def _count_limit_rejections(
        self,
        position,
        proposed_positions,
    ) -> list[str]:
        reasons = []

        symbol_count = sum(
            1
            for item in proposed_positions
            if item.symbol == position.symbol
        )

        sector_count = sum(
            1
            for item in proposed_positions
            if item.sector == position.sector
        )

        strategy_count = sum(
            1
            for item in proposed_positions
            if item.strategy == position.strategy
        )

        direction_count = sum(
            1
            for item in proposed_positions
            if item.direction == position.direction
        )

        correlation_count = sum(
            1
            for item in proposed_positions
            if (
                position.correlation_group
                and item.correlation_group
                == position.correlation_group
            )
        )

        if (
            symbol_count
            > self.limits.maximum_positions_per_symbol
        ):
            reasons.append(
                "MAXIMUM_POSITIONS_PER_SYMBOL_EXCEEDED"
            )

        if (
            sector_count
            > self.limits.maximum_positions_per_sector
        ):
            reasons.append(
                "MAXIMUM_POSITIONS_PER_SECTOR_EXCEEDED"
            )

        if (
            strategy_count
            > self.limits.maximum_positions_per_strategy
        ):
            reasons.append(
                "MAXIMUM_POSITIONS_PER_STRATEGY_EXCEEDED"
            )

        if (
            direction_count
            > self.limits.maximum_positions_per_direction
        ):
            reasons.append(
                "MAXIMUM_POSITIONS_PER_DIRECTION_EXCEEDED"
            )

        if (
            position.correlation_group
            and correlation_count
            > self.limits.maximum_positions_per_correlation_group
        ):
            reasons.append(
                "MAXIMUM_POSITIONS_PER_CORRELATION_GROUP_EXCEEDED"
            )

        return reasons

    def _exposure_limit_rejections(
        self,
        position,
        exposure,
    ) -> list[str]:
        reasons = []
        capital = self.limits.initial_capital

        symbol_pct = (
            exposure.symbol_exposure.get(
                position.symbol,
                0.0,
            )
            / capital
        )

        sector_pct = (
            exposure.sector_exposure.get(
                position.sector,
                0.0,
            )
            / capital
        )

        strategy_pct = (
            exposure.strategy_exposure.get(
                position.strategy,
                0.0,
            )
            / capital
        )

        direction_pct = (
            exposure.direction_exposure.get(
                position.direction,
                0.0,
            )
            / capital
        )

        correlation_pct = 0.0

        if position.correlation_group:
            correlation_pct = (
                exposure.correlation_group_exposure.get(
                    position.correlation_group,
                    0.0,
                )
                / capital
            )

        if (
            symbol_pct
            > self.limits.maximum_symbol_exposure_pct
            + 0.000001
        ):
            reasons.append(
                "MAXIMUM_SYMBOL_EXPOSURE_EXCEEDED"
            )

        if (
            sector_pct
            > self.limits.maximum_sector_exposure_pct
            + 0.000001
        ):
            reasons.append(
                "MAXIMUM_SECTOR_EXPOSURE_EXCEEDED"
            )

        if (
            strategy_pct
            > self.limits.maximum_strategy_exposure_pct
            + 0.000001
        ):
            reasons.append(
                "MAXIMUM_STRATEGY_EXPOSURE_EXCEEDED"
            )

        if (
            direction_pct
            > self.limits.maximum_direction_exposure_pct
            + 0.000001
        ):
            reasons.append(
                "MAXIMUM_DIRECTION_EXPOSURE_EXCEEDED"
            )

        if (
            position.correlation_group
            and correlation_pct
            > self.limits.maximum_correlation_group_exposure_pct
            + 0.000001
        ):
            reasons.append(
                "MAXIMUM_CORRELATION_GROUP_EXPOSURE_EXCEEDED"
            )

        return reasons

    def _greeks_limit_rejections(
        self,
        exposure,
    ) -> list[str]:
        reasons = []

        if (
            abs(exposure.net_delta)
            > self.limits.maximum_absolute_delta
        ):
            reasons.append(
                "MAXIMUM_ABSOLUTE_DELTA_EXCEEDED"
            )

        if (
            exposure.net_delta
            < self.limits.minimum_net_delta
            or exposure.net_delta
            > self.limits.maximum_net_delta
        ):
            reasons.append(
                "NET_DELTA_BAND_EXCEEDED"
            )

        if (
            abs(exposure.net_gamma)
            > self.limits.maximum_absolute_gamma
        ):
            reasons.append(
                "MAXIMUM_ABSOLUTE_GAMMA_EXCEEDED"
            )

        if (
            abs(exposure.net_theta)
            > self.limits.maximum_absolute_theta
        ):
            reasons.append(
                "MAXIMUM_ABSOLUTE_THETA_EXCEEDED"
            )

        if (
            abs(exposure.net_vega)
            > self.limits.maximum_absolute_vega
        ):
            reasons.append(
                "MAXIMUM_ABSOLUTE_VEGA_EXCEEDED"
            )

        if (
            abs(exposure.net_rho)
            > self.limits.maximum_absolute_rho
        ):
            reasons.append(
                "MAXIMUM_ABSOLUTE_RHO_EXCEEDED"
            )

        return reasons

    # -------------------------------------------------
    # Exposure aggregation
    # -------------------------------------------------

    def calculate_exposure(
        self,
        positions,
    ) -> PortfolioExposure:
        total_capital = sum(
            position.capital_required
            for position in positions
        )

        total_risk = sum(
            position.maximum_loss
            for position in positions
        )

        total_expected_profit = sum(
            position.expected_profit
            for position in positions
        )

        symbol_exposure = defaultdict(float)
        sector_exposure = defaultdict(float)
        strategy_exposure = defaultdict(float)
        direction_exposure = defaultdict(float)
        correlation_exposure = defaultdict(float)

        symbol_counts = Counter()
        sector_counts = Counter()
        strategy_counts = Counter()
        direction_counts = Counter()
        correlation_counts = Counter()

        for position in positions:
            capital = position.capital_required

            symbol_exposure[
                position.symbol
            ] += capital

            sector_exposure[
                position.sector
            ] += capital

            strategy_exposure[
                position.strategy
            ] += capital

            direction_exposure[
                position.direction
            ] += capital

            symbol_counts[
                position.symbol
            ] += 1

            sector_counts[
                position.sector
            ] += 1

            strategy_counts[
                position.strategy
            ] += 1

            direction_counts[
                position.direction
            ] += 1

            if position.correlation_group:
                correlation_exposure[
                    position.correlation_group
                ] += capital

                correlation_counts[
                    position.correlation_group
                ] += 1

        initial_capital = (
            self.limits.initial_capital
        )

        available_capital = max(
            initial_capital
            - total_capital
            - self.limits.reserve_cash_dollars,
            0.0,
        )

        return PortfolioExposure(
            initial_capital=initial_capital,
            total_capital_allocated=round(
                total_capital,
                2,
            ),
            total_maximum_loss=round(
                total_risk,
                2,
            ),
            total_expected_profit=round(
                total_expected_profit,
                2,
            ),
            exposure_pct=round(
                total_capital / initial_capital,
                4,
            ),
            risk_pct=round(
                total_risk / initial_capital,
                4,
            ),
            expected_return_on_capital_pct=round(
                total_expected_profit
                / initial_capital,
                4,
            ),
            available_capital=round(
                available_capital,
                2,
            ),
            reserve_cash=round(
                self.limits.reserve_cash_dollars,
                2,
            ),
            net_delta=round(
                sum(
                    position.delta
                    for position in positions
                ),
                4,
            ),
            net_gamma=round(
                sum(
                    position.gamma
                    for position in positions
                ),
                5,
            ),
            net_theta=round(
                sum(
                    position.theta
                    for position in positions
                ),
                4,
            ),
            net_vega=round(
                sum(
                    position.vega
                    for position in positions
                ),
                4,
            ),
            net_rho=round(
                sum(
                    position.rho
                    for position in positions
                ),
                4,
            ),
            gross_delta=round(
                sum(
                    abs(position.delta)
                    for position in positions
                ),
                4,
            ),
            gross_gamma=round(
                sum(
                    abs(position.gamma)
                    for position in positions
                ),
                5,
            ),
            gross_theta=round(
                sum(
                    abs(position.theta)
                    for position in positions
                ),
                4,
            ),
            gross_vega=round(
                sum(
                    abs(position.vega)
                    for position in positions
                ),
                4,
            ),
            position_count=len(positions),
            symbol_exposure=dict(
                symbol_exposure
            ),
            sector_exposure=dict(
                sector_exposure
            ),
            strategy_exposure=dict(
                strategy_exposure
            ),
            direction_exposure=dict(
                direction_exposure
            ),
            correlation_group_exposure=dict(
                correlation_exposure
            ),
            symbol_counts=dict(symbol_counts),
            sector_counts=dict(sector_counts),
            strategy_counts=dict(
                strategy_counts
            ),
            direction_counts=dict(
                direction_counts
            ),
            correlation_group_counts=dict(
                correlation_counts
            ),
        )

    # -------------------------------------------------
    # Portfolio scoring and status
    # -------------------------------------------------

    def _risk_score(
        self,
        exposure,
    ) -> float:
        score = 100.0

        risk_utilization = (
            exposure.total_maximum_loss
            / self.limits.maximum_total_risk_dollars
            if self.limits.maximum_total_risk_dollars > 0
            else 1.0
        )

        exposure_utilization = (
            exposure.total_capital_allocated
            / self.limits.maximum_portfolio_exposure_dollars
            if self.limits.maximum_portfolio_exposure_dollars > 0
            else 1.0
        )

        if risk_utilization > 1:
            score -= 50
        elif risk_utilization > 0.90:
            score -= 25
        elif risk_utilization > 0.75:
            score -= 12

        if exposure_utilization > 1:
            score -= 40
        elif exposure_utilization > 0.90:
            score -= 18
        elif exposure_utilization > 0.75:
            score -= 8

        if (
            abs(exposure.net_delta)
            > self.limits.maximum_absolute_delta
            * 0.80
        ):
            score -= 10

        if (
            abs(exposure.net_vega)
            > self.limits.maximum_absolute_vega
            * 0.80
        ):
            score -= 10

        return max(
            0.0,
            min(100.0, score),
        )

    def _diversification_score(
        self,
        exposure,
    ) -> float:
        if exposure.position_count <= 1:
            return 45.0

        score = 100.0

        if exposure.symbol_counts:
            max_symbol_count = max(
                exposure.symbol_counts.values()
            )

            if max_symbol_count > 1:
                score -= (
                    max_symbol_count - 1
                ) * 20.0

        if exposure.sector_counts:
            max_sector_count = max(
                exposure.sector_counts.values()
            )

            if max_sector_count > 2:
                score -= (
                    max_sector_count - 2
                ) * 10.0

        if exposure.direction_counts:
            max_direction_count = max(
                exposure.direction_counts.values()
            )

            if (
                max_direction_count
                / exposure.position_count
                > 0.75
            ):
                score -= 15.0

        if exposure.correlation_group_counts:
            max_correlation_count = max(
                exposure.correlation_group_counts.values()
            )

            if max_correlation_count > 2:
                score -= (
                    max_correlation_count - 2
                ) * 12.0

        unique_symbols = len(
            exposure.symbol_counts
        )

        unique_sectors = len(
            exposure.sector_counts
        )

        score += min(
            unique_symbols * 2.0,
            10.0,
        )

        score += min(
            unique_sectors * 2.0,
            8.0,
        )

        return max(
            0.0,
            min(100.0, score),
        )

    def _capital_efficiency_score(
        self,
        exposure,
    ) -> float:
        if (
            exposure.total_capital_allocated
            <= 0
        ):
            return 0.0

        expected_return = (
            exposure.total_expected_profit
            / exposure.total_capital_allocated
        )

        if expected_return >= 0.50:
            return 100.0

        if expected_return >= 0.30:
            return 90.0

        if expected_return >= 0.20:
            return 80.0

        if expected_return >= 0.15:
            return 70.0

        if expected_return >= 0.10:
            return 60.0

        if expected_return >= 0.05:
            return 45.0

        return 30.0

    def _hard_portfolio_violations(
        self,
        exposure,
    ) -> list[str]:
        violations = []

        if (
            exposure.total_capital_allocated
            > self.limits.maximum_portfolio_exposure_dollars
            + 0.01
        ):
            violations.append(
                "PORTFOLIO_EXPOSURE_LIMIT"
            )

        if (
            exposure.total_maximum_loss
            > self.limits.maximum_total_risk_dollars
            + 0.01
        ):
            violations.append(
                "PORTFOLIO_RISK_LIMIT"
            )

        violations.extend(
            self._greeks_limit_rejections(
                exposure
            )
        )

        return violations

    def _portfolio_warnings(
        self,
        exposure,
    ) -> list[str]:
        warnings = []

        if exposure.position_count == 0:
            warnings.append(
                "No portfolio positions were accepted"
            )

        if (
            exposure.exposure_pct
            > self.limits.maximum_portfolio_exposure_pct
            * 0.90
        ):
            warnings.append(
                "Portfolio exposure is near its maximum"
            )

        if (
            exposure.risk_pct
            > self.limits.maximum_total_risk_pct
            * 0.90
        ):
            warnings.append(
                "Portfolio maximum loss is near its limit"
            )

        if (
            abs(exposure.net_delta)
            > self.limits.maximum_absolute_delta
            * 0.80
        ):
            warnings.append(
                "Portfolio delta is near its limit"
            )

        if (
            abs(exposure.net_vega)
            > self.limits.maximum_absolute_vega
            * 0.80
        ):
            warnings.append(
                "Portfolio vega is near its limit"
            )

        return warnings

    def _portfolio_recommendations(
        self,
        exposure,
        positions,
        rejected,
    ) -> list[str]:
        recommendations = []

        if not positions:
            recommendations.append(
                "Do not deploy capital; no opportunity passed portfolio limits."
            )
            return recommendations

        if exposure.position_count < 3:
            recommendations.append(
                "Increase diversification before live deployment."
            )

        bullish_count = exposure.direction_counts.get(
            "CALL",
            0,
        )

        bearish_count = exposure.direction_counts.get(
            "PUT",
            0,
        )

        if (
            bullish_count
            > bearish_count + 2
        ):
            recommendations.append(
                "Portfolio is materially bullish; consider bearish or neutral hedges."
            )

        if (
            bearish_count
            > bullish_count + 2
        ):
            recommendations.append(
                "Portfolio is materially bearish; consider bullish or neutral hedges."
            )

        if rejected:
            recommendations.append(
                f"{len(rejected)} ranked opportunities were excluded by portfolio limits."
            )

        if (
            exposure.exposure_pct
            < self.limits.maximum_portfolio_exposure_pct
            * 0.50
        ):
            recommendations.append(
                "Significant capital remains available; retain reserve until more qualified candidates appear."
            )

        return recommendations

    def _readiness(
        self,
        positions,
        portfolio_score,
        valid,
    ) -> str:
        if not valid:
            return "REJECTED"

        if not positions:
            return "NO_POSITIONS"

        all_live = all(
            position.readiness
            == "LIVE_CANDIDATE"
            for position in positions
        )

        if (
            all_live
            and portfolio_score >= 85
            and len(positions) >= 3
        ):
            return "LIVE_PORTFOLIO_CANDIDATE"

        if portfolio_score >= 70:
            return "PAPER_TRADING_PORTFOLIO"

        return "RESEARCH_PORTFOLIO"
