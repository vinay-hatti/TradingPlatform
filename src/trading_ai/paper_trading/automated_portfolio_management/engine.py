from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict
from typing import Iterable, Mapping

from .policy import AutomatedPortfolioManagementPolicy
from .profile import (
    PortfolioExposureBucket,
    PortfolioGreeks,
    PortfolioHealthScore,
    PortfolioPositionInput,
    PortfolioRecommendation,
    PortfolioRiskBreach,
    PortfolioState,
)


def _safe_pct(numerator: float, denominator: float) -> float:
    return 0.0 if denominator == 0 else numerator / denominator * 100.0


def _clamp(value: float, lower: float = 0.0, upper: float = 100.0) -> float:
    return max(lower, min(upper, value))


class AutomatedPortfolioManagementEngine:
    def __init__(
        self,
        policy: AutomatedPortfolioManagementPolicy | None = None,
    ) -> None:
        self.policy = policy or AutomatedPortfolioManagementPolicy()
        self.policy.validate()

    def state(
        self,
        positions: Iterable[PortfolioPositionInput],
        account: Mapping[str, float],
    ) -> PortfolioState:
        rows = tuple(positions)
        cash = float(account.get("cash", 0.0) or 0.0)
        buying_power = float(account.get("buying_power", cash) or 0.0)
        realized = float(account.get("realized_pnl", 0.0) or 0.0)
        daily = float(account.get("daily_pnl", 0.0) or 0.0)
        margin_used = float(account.get("margin_used", 0.0) or 0.0)

        long_value = sum(max(0.0, row.market_value) for row in rows)
        short_value = sum(abs(min(0.0, row.market_value)) for row in rows)
        gross = long_value + short_value
        net = long_value - short_value
        unrealized = sum(row.unrealized_pnl for row in rows)
        nlv = float(
            account.get("net_liquidation_value", cash + net) or 0.0
        )
        weighted_beta = (
            sum(row.beta * row.market_value for row in rows) / nlv
            if nlv
            else 0.0
        )
        option_contract_count = int(
            sum(
                abs(row.quantity)
                for row in rows
                if row.security_type.upper() in {"OPT", "OPTION"}
            )
        )
        return PortfolioState(
            portfolio_id=str(account.get("portfolio_id") or "PAPER-PRIMARY"),
            cash=round(cash, 2),
            buying_power=round(buying_power, 2),
            net_liquidation_value=round(nlv, 2),
            gross_market_value=round(gross, 2),
            net_market_value=round(net, 2),
            gross_exposure_pct=round(_safe_pct(gross, nlv), 4),
            net_exposure_pct=round(_safe_pct(net, nlv), 4),
            capital_utilization_pct=round(_safe_pct(gross, nlv), 4),
            margin_utilization_pct=round(_safe_pct(margin_used, nlv), 4),
            unrealized_pnl=round(unrealized, 2),
            realized_pnl=round(realized, 2),
            daily_pnl=round(daily, 2),
            open_position_count=len(rows),
            option_contract_count=option_contract_count,
            long_market_value=round(long_value, 2),
            short_market_value=round(short_value, 2),
            portfolio_beta=round(weighted_beta, 6),
            metadata={
                "cash_pct": round(_safe_pct(cash, nlv), 4),
                "paper_only": True,
                "live_trading_enabled": False,
            },
        )

    def greeks(
        self,
        positions: Iterable[PortfolioPositionInput],
        nlv: float,
    ) -> PortfolioGreeks:
        rows = tuple(positions)
        delta = sum(row.delta * row.quantity * row.multiplier for row in rows)
        gamma = sum(row.gamma * row.quantity * row.multiplier for row in rows)
        theta = sum(row.theta * row.quantity * row.multiplier for row in rows)
        vega = sum(row.vega * row.quantity * row.multiplier for row in rows)
        rho = sum(row.rho * row.quantity * row.multiplier for row in rows)
        reference = sum(
            abs(row.current_price * row.quantity * row.multiplier)
            for row in rows
            if row.security_type.upper() in {"OPT", "OPTION"}
        )
        delta_notional = delta * (reference if reference else 1.0)
        gamma_notional = gamma * (reference if reference else 1.0)
        vega_notional = vega * (reference if reference else 1.0)
        return PortfolioGreeks(
            delta=round(delta, 8),
            gamma=round(gamma, 8),
            theta=round(theta, 8),
            vega=round(vega, 8),
            rho=round(rho, 8),
            delta_notional=round(delta_notional, 8),
            gamma_notional=round(gamma_notional, 8),
            vega_notional=round(vega_notional, 8),
            metadata={
                "delta_notional_pct": round(_safe_pct(delta_notional, nlv), 6),
                "gamma_notional_pct": round(_safe_pct(gamma_notional, nlv), 6),
                "vega_notional_pct": round(_safe_pct(vega_notional, nlv), 6),
            },
        )

    def exposures(
        self,
        positions: Iterable[PortfolioPositionInput],
        nlv: float,
        attribute: str,
    ) -> tuple[PortfolioExposureBucket, ...]:
        grouped: dict[str, list[PortfolioPositionInput]] = defaultdict(list)
        for row in positions:
            value = getattr(row, attribute)
            grouped[str(value or "UNKNOWN").upper()].append(row)

        result: list[PortfolioExposureBucket] = []
        for key, rows in grouped.items():
            market = sum(row.market_value for row in rows)
            absolute = sum(abs(row.market_value) for row in rows)
            result.append(
                PortfolioExposureBucket(
                    key=key,
                    market_value=round(market, 2),
                    absolute_market_value=round(absolute, 2),
                    capital_pct=round(_safe_pct(absolute, nlv), 4),
                    net_pct=round(_safe_pct(market, nlv), 4),
                    position_count=len(rows),
                )
            )
        return tuple(
            sorted(result, key=lambda row: row.capital_pct, reverse=True)
        )

    def risk_breaches(
        self,
        state: PortfolioState,
        greeks: PortfolioGreeks,
        symbol_exposure: Iterable[PortfolioExposureBucket],
        sector_exposure: Iterable[PortfolioExposureBucket],
        industry_exposure: Iterable[PortfolioExposureBucket],
        *,
        drawdown_pct: float,
    ) -> tuple[PortfolioRiskBreach, ...]:
        breaches: list[PortfolioRiskBreach] = []

        def add(code, severity, actual, limit, message, **metadata):
            breaches.append(
                PortfolioRiskBreach(
                    code=code,
                    severity=severity,
                    actual=round(float(actual), 6),
                    limit=round(float(limit), 6),
                    message=message,
                    metadata=metadata,
                )
            )

        for bucket in symbol_exposure:
            if bucket.capital_pct > self.policy.maximum_symbol_allocation_pct:
                add(
                    "SYMBOL_CONCENTRATION",
                    "HIGH",
                    bucket.capital_pct,
                    self.policy.maximum_symbol_allocation_pct,
                    f"{bucket.key} exceeds symbol allocation limit",
                    key=bucket.key,
                )
        for bucket in sector_exposure:
            if bucket.capital_pct > self.policy.maximum_sector_allocation_pct:
                add(
                    "SECTOR_CONCENTRATION",
                    "HIGH",
                    bucket.capital_pct,
                    self.policy.maximum_sector_allocation_pct,
                    f"{bucket.key} exceeds sector allocation limit",
                    key=bucket.key,
                )
        for bucket in industry_exposure:
            if bucket.capital_pct > self.policy.maximum_industry_allocation_pct:
                add(
                    "INDUSTRY_CONCENTRATION",
                    "MODERATE",
                    bucket.capital_pct,
                    self.policy.maximum_industry_allocation_pct,
                    f"{bucket.key} exceeds industry allocation limit",
                    key=bucket.key,
                )

        checks = (
            (
                "GROSS_EXPOSURE",
                abs(state.gross_exposure_pct),
                self.policy.maximum_gross_exposure_pct,
                "CRITICAL",
            ),
            (
                "NET_EXPOSURE",
                abs(state.net_exposure_pct),
                self.policy.maximum_net_exposure_pct,
                "HIGH",
            ),
            (
                "CAPITAL_UTILIZATION",
                state.capital_utilization_pct,
                self.policy.maximum_capital_utilization_pct,
                "HIGH",
            ),
            (
                "MARGIN_UTILIZATION",
                state.margin_utilization_pct,
                self.policy.maximum_margin_utilization_pct,
                "CRITICAL",
            ),
            (
                "OPEN_POSITIONS",
                state.open_position_count,
                self.policy.maximum_open_positions,
                "MODERATE",
            ),
            (
                "OPTION_CONTRACTS",
                state.option_contract_count,
                self.policy.maximum_option_contracts,
                "MODERATE",
            ),
            (
                "DRAWDOWN",
                abs(drawdown_pct),
                self.policy.maximum_drawdown_pct,
                "CRITICAL",
            ),
            (
                "DELTA_NOTIONAL",
                abs(float(greeks.metadata["delta_notional_pct"])),
                self.policy.maximum_absolute_delta_notional_pct,
                "HIGH",
            ),
            (
                "GAMMA_NOTIONAL",
                abs(float(greeks.metadata["gamma_notional_pct"])),
                self.policy.maximum_absolute_gamma_notional_pct,
                "HIGH",
            ),
            (
                "VEGA_NOTIONAL",
                abs(float(greeks.metadata["vega_notional_pct"])),
                self.policy.maximum_absolute_vega_notional_pct,
                "HIGH",
            ),
        )
        for code, actual, limit, severity in checks:
            if actual > limit:
                add(code, severity, actual, limit, f"{code} limit exceeded")

        daily_loss_pct = abs(min(0.0, _safe_pct(state.daily_pnl, state.net_liquidation_value)))
        if daily_loss_pct > self.policy.maximum_daily_loss_pct:
            add(
                "DAILY_LOSS",
                "CRITICAL",
                daily_loss_pct,
                self.policy.maximum_daily_loss_pct,
                "daily loss limit exceeded",
            )

        cash_pct = float(state.metadata.get("cash_pct", 0.0))
        if cash_pct < self.policy.minimum_cash_pct:
            add(
                "CASH_RESERVE",
                "HIGH",
                cash_pct,
                self.policy.minimum_cash_pct,
                "cash reserve below minimum",
            )

        return tuple(
            sorted(
                breaches,
                key=lambda row: (
                    {"CRITICAL": 0, "HIGH": 1, "MODERATE": 2}.get(
                        row.severity, 3
                    ),
                    row.code,
                ),
            )
        )

    def recommendations(
        self,
        breaches: Iterable[PortfolioRiskBreach],
    ) -> tuple[PortfolioRecommendation, ...]:
        mapping = {
            "SYMBOL_CONCENTRATION": (
                "REDUCE_POSITION",
                "Reduce concentrated symbol exposure",
            ),
            "SECTOR_CONCENTRATION": (
                "REDUCE_SECTOR",
                "Reduce sector concentration or add diversifying exposure",
            ),
            "INDUSTRY_CONCENTRATION": (
                "ROTATE_INDUSTRY",
                "Rotate capital toward less concentrated industries",
            ),
            "GROSS_EXPOSURE": (
                "DELEVERAGE",
                "Reduce gross exposure and preserve buying power",
            ),
            "NET_EXPOSURE": (
                "FLATTEN_DIRECTIONAL_BIAS",
                "Reduce directional portfolio bias",
            ),
            "CAPITAL_UTILIZATION": (
                "RAISE_CASH",
                "Close or reduce lower-conviction positions",
            ),
            "MARGIN_UTILIZATION": (
                "REDUCE_MARGIN",
                "Reduce leveraged positions immediately",
            ),
            "OPEN_POSITIONS": (
                "CONSOLIDATE_POSITIONS",
                "Close lower-ranked positions",
            ),
            "OPTION_CONTRACTS": (
                "REDUCE_OPTION_COUNT",
                "Reduce aggregate option contract exposure",
            ),
            "DRAWDOWN": (
                "DEFENSIVE_MODE",
                "Suspend new risk and reduce open exposure",
            ),
            "DELTA_NOTIONAL": (
                "FLATTEN_DELTA",
                "Reduce directional delta exposure",
            ),
            "GAMMA_NOTIONAL": (
                "REDUCE_GAMMA",
                "Reduce convexity and near-expiry option risk",
            ),
            "VEGA_NOTIONAL": (
                "REDUCE_VEGA",
                "Reduce volatility sensitivity",
            ),
            "DAILY_LOSS": (
                "DAILY_RISK_LOCK",
                "Stop adding risk for the remainder of the session",
            ),
            "CASH_RESERVE": (
                "INCREASE_CASH",
                "Raise portfolio cash reserve",
            ),
        }
        output: list[PortfolioRecommendation] = []
        for breach in breaches:
            action, rationale = mapping.get(
                breach.code,
                ("REVIEW_PORTFOLIO", breach.message),
            )
            output.append(
                PortfolioRecommendation(
                    code=f"REC_{breach.code}",
                    priority=breach.severity,
                    action=action,
                    rationale=rationale,
                    target=str(breach.metadata.get("key") or "PORTFOLIO"),
                    estimated_impact=(
                        f"Bring {breach.code} from {breach.actual:.2f} "
                        f"toward {breach.limit:.2f}"
                    ),
                    metadata={"source_breach": breach.code},
                )
            )
        return tuple(output)

    def health(
        self,
        state: PortfolioState,
        greeks: PortfolioGreeks,
        symbol_exposure: Iterable[PortfolioExposureBucket],
        sector_exposure: Iterable[PortfolioExposureBucket],
        breaches: Iterable[PortfolioRiskBreach],
        *,
        drawdown_pct: float,
        execution_score: float,
    ) -> PortfolioHealthScore:
        symbol_max = max(
            (row.capital_pct for row in symbol_exposure),
            default=0.0,
        )
        sector_max = max(
            (row.capital_pct for row in sector_exposure),
            default=0.0,
        )
        liquidity = _clamp(float(state.metadata.get("cash_pct", 0.0)) * 2.5)
        diversification = _clamp(
            100.0
            - max(
                0.0,
                symbol_max - self.policy.maximum_symbol_allocation_pct / 2.0,
            )
            * 2.0
            - max(
                0.0,
                sector_max - self.policy.maximum_sector_allocation_pct / 2.0,
            )
        )
        greek_pressure = max(
            abs(float(greeks.metadata["delta_notional_pct"]))
            / max(self.policy.maximum_absolute_delta_notional_pct, 1.0),
            abs(float(greeks.metadata["gamma_notional_pct"]))
            / max(self.policy.maximum_absolute_gamma_notional_pct, 1.0),
            abs(float(greeks.metadata["vega_notional_pct"]))
            / max(self.policy.maximum_absolute_vega_notional_pct, 1.0),
        )
        greek_score = _clamp(100.0 - greek_pressure * 50.0)
        severity_penalty = sum(
            {"CRITICAL": 20.0, "HIGH": 12.0, "MODERATE": 6.0}.get(
                row.severity, 3.0
            )
            for row in breaches
        )
        risk_score = _clamp(100.0 - severity_penalty)
        drawdown_score = _clamp(
            100.0
            - abs(drawdown_pct)
            / max(self.policy.maximum_drawdown_pct, 1.0)
            * 100.0
        )
        execution = _clamp(execution_score)
        overall = round(
            liquidity * 0.15
            + diversification * 0.20
            + greek_score * 0.20
            + risk_score * 0.25
            + drawdown_score * 0.10
            + execution * 0.10,
            2,
        )
        grade = (
            "A"
            if overall >= 90
            else "B"
            if overall >= 80
            else "C"
            if overall >= 70
            else "D"
            if overall >= 60
            else "F"
        )
        return PortfolioHealthScore(
            overall=overall,
            liquidity=round(liquidity, 2),
            diversification=round(diversification, 2),
            greeks=round(greek_score, 2),
            risk=round(risk_score, 2),
            drawdown=round(drawdown_score, 2),
            execution=round(execution, 2),
            grade=grade,
            metadata={
                "minimum_health_score": self.policy.minimum_health_score,
                "healthy": overall >= self.policy.minimum_health_score,
            },
        )
