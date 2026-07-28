from __future__ import annotations

from dataclasses import asdict
from typing import Any, Mapping

from .adapter import PortfolioInputAdapter
from .engine import AutomatedPortfolioManagementEngine
from .policy import AutomatedPortfolioManagementPolicy
from .profile import AutomatedPortfolioManagementResult


class AutomatedPortfolioManagementService:
    def __init__(
        self,
        policy: AutomatedPortfolioManagementPolicy | None = None,
    ) -> None:
        self.policy = policy or AutomatedPortfolioManagementPolicy()
        self.policy.validate()
        self.adapter = PortfolioInputAdapter()
        self.engine = AutomatedPortfolioManagementEngine(self.policy)

    def execute(
        self,
        lifecycle_report: Mapping[str, Any],
        market_data: Mapping[str, Any],
        account_snapshot: Mapping[str, Any],
        *,
        drawdown_pct: float = 0.0,
        execution_score: float = 100.0,
    ) -> AutomatedPortfolioManagementResult:
        positions = self.adapter.from_payload(lifecycle_report, market_data)
        account = dict(account_snapshot)
        account.setdefault(
            "portfolio_id",
            lifecycle_report.get("portfolio_id") or "PAPER-PRIMARY",
        )
        state = self.engine.state(positions, account)
        greeks = self.engine.greeks(
            positions, state.net_liquidation_value
        )
        by_symbol = self.engine.exposures(
            positions, state.net_liquidation_value, "symbol"
        )
        by_sector = self.engine.exposures(
            positions, state.net_liquidation_value, "sector"
        )
        by_industry = self.engine.exposures(
            positions, state.net_liquidation_value, "industry"
        )
        by_asset = self.engine.exposures(
            positions, state.net_liquidation_value, "security_type"
        )
        breaches = self.engine.risk_breaches(
            state,
            greeks,
            by_symbol,
            by_sector,
            by_industry,
            drawdown_pct=drawdown_pct,
        )
        recommendations = self.engine.recommendations(breaches)
        health = self.engine.health(
            state,
            greeks,
            by_symbol,
            by_sector,
            breaches,
            drawdown_pct=drawdown_pct,
            execution_score=execution_score,
        )
        status = (
            "PHASE4_PORTFOLIO_RISK_BREACHED"
            if breaches
            else "PHASE4_PORTFOLIO_HEALTHY"
        )
        if not positions:
            status = "PHASE4_NO_OPEN_POSITIONS"

        daily_snapshot = {
            "beginning_equity": round(
                state.net_liquidation_value - state.daily_pnl, 2
            ),
            "ending_equity": state.net_liquidation_value,
            "daily_pnl": state.daily_pnl,
            "daily_return_pct": round(
                0.0
                if state.net_liquidation_value - state.daily_pnl == 0
                else state.daily_pnl
                / (state.net_liquidation_value - state.daily_pnl)
                * 100.0,
                6,
            ),
            "unrealized_pnl": state.unrealized_pnl,
            "realized_pnl": state.realized_pnl,
            "gross_exposure_pct": state.gross_exposure_pct,
            "net_exposure_pct": state.net_exposure_pct,
            "cash_pct": state.metadata.get("cash_pct", 0.0),
            "drawdown_pct": round(float(drawdown_pct), 6),
            "open_positions": state.open_position_count,
            "option_contracts": state.option_contract_count,
            "portfolio_beta": state.portfolio_beta,
            "health_score": health.overall,
            "health_grade": health.grade,
        }
        warnings: list[str] = []
        if any(row.key == "UNKNOWN" for row in by_sector):
            warnings.append("UNKNOWN_SECTOR_EXPOSURE_PRESENT")
        if health.overall < self.policy.minimum_health_score:
            warnings.append("PORTFOLIO_HEALTH_BELOW_MINIMUM")

        return AutomatedPortfolioManagementResult(
            milestone=51,
            phase=4,
            portfolio_id=state.portfolio_id,
            state=asdict(state),
            greeks=asdict(greeks),
            exposure_by_symbol=tuple(asdict(row) for row in by_symbol),
            exposure_by_sector=tuple(asdict(row) for row in by_sector),
            exposure_by_industry=tuple(asdict(row) for row in by_industry),
            exposure_by_asset_class=tuple(asdict(row) for row in by_asset),
            risk_breaches=tuple(asdict(row) for row in breaches),
            recommendations=tuple(asdict(row) for row in recommendations),
            health=asdict(health),
            daily_snapshot=daily_snapshot,
            status=status,
            warnings=tuple(warnings),
            metadata={
                "environment": "PAPER",
                "live_trading_enabled": False,
                "position_count": len(positions),
            },
        )
