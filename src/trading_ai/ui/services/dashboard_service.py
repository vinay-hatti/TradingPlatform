from __future__ import annotations

from datetime import datetime, timezone
import os
from typing import Any

from trading_ai.ui.adapters.artifact_sources import (
    ArtifactResult,
    RepositoryArtifactAdapters,
)
from trading_ai.ui.models.dashboard import (
    DashboardSnapshot,
    DashboardSourceStatus,
    MetricCard,
    OpportunitySummary,
    SystemComponentHealth,
)


def value(obj: Any, *names: str, default: Any = None) -> Any:
    if obj is None:
        return default
    for name in names:
        if isinstance(obj, dict) and name in obj:
            candidate = obj.get(name)
            if candidate not in (None, ""):
                return candidate
        elif hasattr(obj, name):
            candidate = getattr(obj, name)
            if candidate not in (None, ""):
                return candidate
    return default


def number(raw: Any, default: float = 0.0) -> float:
    try:
        if raw in (None, ""):
            return default
        text = str(raw).replace("$", "").replace(",", "").replace("%", "").strip()
        return float(text)
    except (TypeError, ValueError):
        return default


def probability(raw: Any) -> float | None:
    if raw in (None, ""):
        return None
    result = number(raw)
    if result > 1.0:
        result /= 100.0
    return max(0.0, min(1.0, result))


def is_open(position: dict[str, Any]) -> bool:
    explicit = str(value(position, "status", default="")).upper()
    if explicit:
        return explicit == "OPEN"
    return bool(value(position, "is_open", default=False))


class DashboardService:
    def __init__(
        self,
        adapters: RepositoryArtifactAdapters | None = None,
    ) -> None:
        self.adapters = adapters or RepositoryArtifactAdapters()

    def _opportunities(
        self,
        scanner: ArtifactResult,
        optimized: ArtifactResult,
    ) -> list[OpportunitySummary]:
        rows = optimized.data if optimized.available else scanner.data
        source = optimized.source if optimized.available else scanner.source
        opportunities: list[OpportunitySummary] = []

        for row in rows or []:
            status = str(value(row, "status", default="ACCEPTED")).upper()
            if status not in {"ACCEPTED", "APPROVED", "SELECTED", "QUALIFIED", ""}:
                continue

            symbol = str(value(row, "symbol", "ticker", default="")).upper()
            if not symbol:
                continue

            raw_signal = str(
                value(row, "signal", "direction", "option_type", default="WATCH")
            ).upper()
            direction = (
                "CALL" if "CALL" in raw_signal
                else "PUT" if "PUT" in raw_signal
                else "WATCH"
            )
            score = number(
                value(
                    row,
                    "rank_score",
                    "ai_score",
                    "adjusted_score",
                    "option_score",
                    "score",
                    default=0,
                )
            )
            if score <= 1:
                score *= 100

            contract = value(
                row,
                "contract",
                "contract_ticker",
                "option_symbol",
                default=None,
            )
            if contract is None:
                strike = value(row, "strike", default=None)
                expiry = value(row, "expiry", default=None)
                if strike or expiry:
                    contract = " · ".join(
                        item for item in (str(strike or ""), str(expiry or "")) if item
                    )

            opportunities.append(
                OpportunitySummary(
                    symbol=symbol,
                    direction=direction,
                    score=max(0.0, min(100.0, score)),
                    probability_of_profit=probability(
                        value(
                            row,
                            "probability_of_profit",
                            "win_probability",
                            "pop",
                            default=None,
                        )
                    ),
                    regime=str(
                        value(
                            row,
                            "regime",
                            "market_regime",
                            default="Unknown",
                        )
                    ),
                    contract=str(contract) if contract else None,
                    expected_value=number(
                        value(row, "expected_value", "expected_return", default=0)
                    ),
                    liquidity_score=number(
                        value(row, "liquidity_score", default=0)
                    ),
                    source=source,
                )
            )

        opportunities.sort(
            key=lambda item: (
                item.score,
                item.probability_of_profit or 0.0,
            ),
            reverse=True,
        )
        return opportunities[:10]

    @staticmethod
    def _portfolio_summary(
        positions_result: ArtifactResult,
        cash_result: ArtifactResult,
    ) -> dict[str, float]:
        positions = positions_result.data or []
        open_positions = [item for item in positions if is_open(item)]
        closed_positions = [item for item in positions if not is_open(item)]

        open_value = sum(
            number(value(item, "current_price", "market_price", default=0))
            * int(number(value(item, "quantity", "contracts", default=0)))
            * 100.0
            for item in open_positions
        )
        unrealized = sum(
            number(value(item, "unrealized_pnl", default=0))
            for item in open_positions
        )
        realized = sum(
            number(value(item, "realized_pnl", default=0))
            for item in closed_positions
        )
        cash = number(
            value(cash_result.data, "cash", default=100000.0),
            100000.0,
        )
        return {
            "open_positions": float(len(open_positions)),
            "closed_positions": float(len(closed_positions)),
            "cash": cash,
            "open_value": open_value,
            "net_liquidation": cash + open_value,
            "unrealized_pnl": unrealized,
            "realized_pnl": realized,
        }

    @staticmethod
    def _risk_summary(optimized: ArtifactResult) -> dict[str, float]:
        accepted = [
            row
            for row in (optimized.data or [])
            if str(value(row, "status", default="ACCEPTED")).upper()
            in {"ACCEPTED", "APPROVED", "SELECTED", ""}
        ]
        latest = accepted[-1] if accepted else {}
        return {
            "portfolio_heat": number(
                value(latest, "risk_portfolio_heat", "portfolio_heat", default=0)
            ),
            "cash_reserve": number(
                value(latest, "risk_cash_reserve", "cash_reserve", default=0)
            ),
            "symbol_exposure": number(
                value(latest, "risk_symbol_exposure", default=0)
            ),
            "sector_exposure": number(
                value(latest, "risk_sector_exposure", default=0)
            ),
            "strategy_exposure": number(
                value(latest, "risk_strategy_exposure", default=0)
            ),
            "net_delta": number(value(latest, "risk_net_delta", default=0)),
        }

    @staticmethod
    def _execution_summary(executions: ArtifactResult) -> dict[str, float]:
        records = executions.data or []
        fill_count = 0
        total_slippage = 0.0
        total_latency = 0.0
        latency_count = 0

        for record in records:
            fills = value(record, "fills", default=[]) or []
            fill_count += len(fills)
            for fill in fills:
                total_slippage += abs(
                    number(
                        value(
                            fill,
                            "slippage_pct",
                            "slippage_percentage",
                            default=0,
                        )
                    )
                )
                latency = number(
                    value(fill, "latency_ms", "execution_latency_ms", default=0)
                )
                if latency:
                    total_latency += latency
                    latency_count += 1

        return {
            "execution_count": float(len(records)),
            "fill_count": float(fill_count),
            "average_slippage_pct": (
                total_slippage / fill_count if fill_count else 0.0
            ),
            "average_latency_ms": (
                total_latency / latency_count if latency_count else 0.0
            ),
        }

    @staticmethod
    def _runtime_components(result: ArtifactResult) -> list[SystemComponentHealth]:
        if not result.available:
            return []

        payload = result.data or {}
        registries = payload.get("registries", {}) if isinstance(payload, dict) else {}
        if not registries:
            return []

        latest = max(
            registries.values(),
            key=lambda item: str(item.get("updated_at", "")),
        )
        components = []
        for item in latest.get("services", []):
            raw_status = str(
                value(item, "status", "state", "health", default="unknown")
            ).lower()
            status = (
                "healthy" if raw_status in {"healthy", "ready", "running", "up"}
                else "offline" if raw_status in {"offline", "down", "failed"}
                else "degraded" if raw_status in {"degraded", "warning"}
                else "unknown"
            )
            components.append(
                SystemComponentHealth(
                    name=str(value(item, "service_name", "name", default="Service")),
                    status=status,
                    detail=str(
                        value(
                            item,
                            "detail",
                            "message",
                            "recommendation",
                            default="Runtime health registry",
                        )
                    ),
                    as_of=result.as_of,
                    source=result.source,
                )
            )
        return components

    @staticmethod
    def _source_health(
        label: str,
        result: ArtifactResult,
        *,
        optional: bool = False,
    ) -> SystemComponentHealth:
        if result.available:
            status = "healthy"
        elif optional:
            status = "unknown"
        else:
            status = "degraded"
        return SystemComponentHealth(
            name=label,
            status=status,
            detail=result.detail,
            latency_ms=round(result.latency_ms, 2),
            as_of=result.as_of,
            source=result.source,
        )

    def snapshot(self) -> DashboardSnapshot:
        scanner = self.adapters.scanner()
        optimized = self.adapters.optimized_portfolio()
        positions = self.adapters.paper_positions()
        executions = self.adapters.paper_executions()
        cash = self.adapters.paper_cash()
        runtime = self.adapters.runtime_health()

        opportunities = self._opportunities(scanner, optimized)
        portfolio = self._portfolio_summary(positions, cash)
        risk = self._risk_summary(optimized)
        execution = self._execution_summary(executions)

        regimes = [
            item.regime
            for item in opportunities
            if item.regime and item.regime != "Unknown"
        ]
        market_regime = regimes[0] if regimes else "No current scan"
        probabilities = [
            item.probability_of_profit
            for item in opportunities
            if item.probability_of_profit is not None
        ]
        ai_confidence = (
            sum(probabilities) / len(probabilities)
            if probabilities
            else (
                sum(item.score for item in opportunities)
                / len(opportunities)
                / 100.0
                if opportunities
                else 0.0
            )
        )

        runtime_health = self._runtime_components(runtime)
        artifact_health = [
            self._source_health("Scanner Results", scanner),
            self._source_health("Optimized Portfolio", optimized, optional=True),
            self._source_health("Paper Positions", positions, optional=True),
            self._source_health("Paper Executions", executions, optional=True),
        ]
        system_health = runtime_health or artifact_health

        notices = []
        if scanner.available:
            notices.append(scanner.detail)
        else:
            notices.append(
                "Dashboard is operational, but no current scanner artifact exists."
            )
        if optimized.available:
            notices.append(optimized.detail)
        if positions.available:
            notices.append(positions.detail)
        if runtime.available:
            notices.append(runtime.detail)

        sources = [
            scanner,
            optimized,
            positions,
            executions,
            cash,
            runtime,
        ]

        return DashboardSnapshot(
            generated_at=datetime.now(timezone.utc),
            environment=os.getenv("TRADING_AI_ENV", "development"),
            market_status=(
                "Artifact data available"
                if scanner.available
                else "Awaiting scan"
            ),
            market_regime=market_regime,
            risk_mode=(
                "Governed"
                if optimized.available
                else "Scanner only"
            ),
            ai_confidence=max(0.0, min(1.0, ai_confidence)),
            metrics=[
                MetricCard(
                    key="opportunities",
                    label="Qualified Opportunities",
                    value=str(len(opportunities)),
                    detail="Latest ranked scanner or optimized-portfolio rows",
                    severity="positive" if opportunities else "warning",
                    source=optimized.source if optimized.available else scanner.source,
                    as_of=optimized.as_of if optimized.available else scanner.as_of,
                ),
                MetricCard(
                    key="active_positions",
                    label="Open Paper Positions",
                    value=str(int(portfolio["open_positions"])),
                    detail=f"Net liquidation ${portfolio['net_liquidation']:,.2f}",
                    source=positions.source,
                    as_of=positions.as_of,
                ),
                MetricCard(
                    key="portfolio_heat",
                    label="Portfolio Heat",
                    value=f"{risk['portfolio_heat'] * 100:.2f}%",
                    detail=f"Cash reserve {risk['cash_reserve'] * 100:.2f}%",
                    severity="warning" if risk["portfolio_heat"] >= 0.5 else "normal",
                    source=optimized.source,
                    as_of=optimized.as_of,
                ),
                MetricCard(
                    key="paper_pnl",
                    label="Paper P&L",
                    value=f"${portfolio['unrealized_pnl'] + portfolio['realized_pnl']:,.2f}",
                    detail=(
                        f"Unrealized ${portfolio['unrealized_pnl']:,.2f} · "
                        f"Realized ${portfolio['realized_pnl']:,.2f}"
                    ),
                    source=positions.source,
                    as_of=positions.as_of,
                ),
                MetricCard(
                    key="executions",
                    label="Paper Executions",
                    value=str(int(execution["execution_count"])),
                    detail=(
                        f"{int(execution['fill_count'])} fills · "
                        f"{execution['average_slippage_pct']:.3f}% avg slippage"
                    ),
                    source=executions.source,
                    as_of=executions.as_of,
                ),
                MetricCard(
                    key="net_delta",
                    label="Net Delta",
                    value=f"{risk['net_delta']:,.2f}",
                    detail="Latest optimized portfolio risk row",
                    source=optimized.source,
                    as_of=optimized.as_of,
                ),
            ],
            opportunities=opportunities,
            system_health=system_health,
            sources=[
                DashboardSourceStatus(
                    source=item.source,
                    status="healthy" if item.available else "unknown",
                    detail=item.detail,
                    latency_ms=round(item.latency_ms, 2),
                    records=(
                        len(item.data)
                        if item.available and isinstance(item.data, list)
                        else None
                    ),
                    as_of=item.as_of,
                )
                for item in sources
            ],
            notices=notices,
            raw={
                "project_root": str(self.adapters.root),
                "artifact_paths": {
                    item.source: item.path for item in sources
                },
                "portfolio": portfolio,
                "risk": risk,
                "execution": execution,
            },
        )
