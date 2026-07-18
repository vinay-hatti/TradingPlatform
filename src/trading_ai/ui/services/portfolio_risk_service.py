from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from trading_ai.ui.adapters.artifact_sources import RepositoryArtifactAdapters
from trading_ai.ui.models.portfolio_risk import (
    PortfolioPosition,
    PortfolioRiskResponse,
    PortfolioSummary,
    RiskLimit,
    RiskSnapshot,
)


def value(row: Any, *names: str, default=None):
    for name in names:
        candidate = row.get(name) if isinstance(row, dict) else getattr(row, name, None)
        if candidate not in (None, ""):
            return candidate
    return default


def number(raw: Any, default: float | None = None) -> float | None:
    try:
        if raw in (None, ""):
            return default
        return float(
            str(raw)
            .replace("$", "")
            .replace(",", "")
            .replace("%", "")
            .strip()
        )
    except (TypeError, ValueError):
        return default


def timestamp(path: Path) -> datetime:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)


class PortfolioRiskService:
    POSITION_PATTERNS = (
        "paper_trading/**/*.csv",
        "paper_trading/**/*.json",
        "portfolio/**/*.csv",
        "portfolio/**/*.json",
        "**/positions*.csv",
        "**/positions*.json",
        "**/portfolio_snapshot*.json",
        "**/paper_account*.json",
    )
    RISK_PATTERNS = (
        "risk/**/*.json",
        "risk/**/*.csv",
        "**/risk_snapshot*.json",
        "**/risk_report*.json",
        "**/portfolio_risk*.json",
        "**/runtime_health*.json",
    )

    def __init__(
        self,
        artifacts: RepositoryArtifactAdapters | None = None,
        stale_after_seconds: int = 3600,
    ):
        self.artifacts = artifacts or RepositoryArtifactAdapters()
        self.stale_after_seconds = stale_after_seconds

    @property
    def reports_root(self) -> Path:
        return self.artifacts.root / "reports"

    def _files(self, patterns: tuple[str, ...]) -> list[Path]:
        found: dict[str, Path] = {}
        for pattern in patterns:
            for path in self.reports_root.glob(pattern):
                if path.is_file():
                    found[str(path.resolve())] = path
        return sorted(
            found.values(),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

    @staticmethod
    def _read(path: Path) -> Any:
        if path.suffix.lower() == ".json":
            return json.loads(path.read_text(encoding="utf-8"))
        with path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))

    @staticmethod
    def _rows(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []
        for key in (
            "positions",
            "open_positions",
            "portfolio",
            "holdings",
            "trades",
            "items",
            "data",
        ):
            candidate = payload.get(key)
            if isinstance(candidate, list):
                return [
                    item
                    for item in candidate
                    if isinstance(item, dict)
                ]
        return []

    @staticmethod
    def _position(row: dict[str, Any], path: Path) -> PortfolioPosition | None:
        symbol = str(
            value(
                row,
                "symbol",
                "ticker",
                "underlying_symbol",
                "underlying",
                default="",
            )
        ).strip().upper()
        if not symbol:
            return None

        quantity = number(
            value(
                row,
                "quantity",
                "qty",
                "contracts",
                "position_size",
                "shares",
                default=0,
            ),
            0.0,
        ) or 0.0
        entry = number(
            value(
                row,
                "entry_price",
                "average_entry_price",
                "avg_price",
                "cost_per_unit",
                "premium_paid",
            )
        )
        current = number(
            value(
                row,
                "current_price",
                "mark_price",
                "market_price",
                "last_price",
                "close",
            )
        )
        multiplier = number(
            value(
                row,
                "multiplier",
                "contract_multiplier",
                default=100 if value(row, "option_type", "contract") else 1,
            ),
            1.0,
        ) or 1.0

        market_value = number(
            value(
                row,
                "market_value",
                "position_value",
                "current_value",
            )
        )
        if market_value is None and current is not None:
            market_value = quantity * current * multiplier
        market_value = market_value or 0.0

        cost_basis = number(
            value(
                row,
                "cost_basis",
                "entry_value",
                "invested_capital",
            )
        )
        if cost_basis is None and entry is not None:
            cost_basis = quantity * entry * multiplier
        cost_basis = cost_basis or 0.0

        unrealized = number(
            value(
                row,
                "unrealized_pnl",
                "unrealized_pl",
                "open_pnl",
                "pnl",
            )
        )
        if unrealized is None:
            unrealized = market_value - cost_basis

        realized = number(
            value(
                row,
                "realized_pnl",
                "realized_pl",
                default=0,
            ),
            0.0,
        ) or 0.0

        direction = str(
            value(
                row,
                "direction",
                "side",
                "signal",
                "option_type",
                default="LONG" if quantity >= 0 else "SHORT",
            )
        ).upper()

        return PortfolioPosition(
            symbol=symbol,
            strategy=str(
                value(
                    row,
                    "strategy",
                    "strategy_name",
                    "position_type",
                    default="Unknown",
                )
            ),
            direction=direction,
            quantity=quantity,
            entry_price=entry,
            current_price=current,
            market_value=market_value,
            cost_basis=cost_basis,
            unrealized_pnl=unrealized or 0.0,
            realized_pnl=realized,
            delta=(number(value(row, "delta"), 0.0) or 0.0) * quantity,
            gamma=(number(value(row, "gamma"), 0.0) or 0.0) * quantity,
            theta=(number(value(row, "theta"), 0.0) or 0.0) * quantity,
            vega=(number(value(row, "vega"), 0.0) or 0.0) * quantity,
            risk_score=number(value(row, "risk_score", "position_risk_score")),
            status=str(value(row, "status", default="OPEN")).upper(),
            source=str(path.relative_to(path.parents[1])),
            as_of=timestamp(path),
        )

    def _load_positions(self):
        files = self._files(self.POSITION_PATTERNS)
        for path in files:
            try:
                rows = self._rows(self._read(path))
            except Exception:
                continue
            positions = [
                item
                for item in (
                    self._position(row, path)
                    for row in rows
                )
                if item is not None
            ]
            if positions:
                return positions, path
        return [], None

    def _load_risk_payload(self):
        for path in self._files(self.RISK_PATTERNS):
            try:
                payload = self._read(path)
            except Exception:
                continue
            if isinstance(payload, dict):
                return payload, path
        return {}, None

    @staticmethod
    def _nested(payload: dict[str, Any], *paths: str):
        for path in paths:
            current: Any = payload
            valid = True
            for part in path.split("."):
                if not isinstance(current, dict) or part not in current:
                    valid = False
                    break
                current = current[part]
            if valid and current not in (None, ""):
                return current
        return None

    def get(self) -> PortfolioRiskResponse:
        positions, position_path = self._load_positions()
        risk_payload, risk_path = self._load_risk_payload()
        notices: list[str] = []

        total_market_value = sum(item.market_value for item in positions)
        total_cost_basis = sum(item.cost_basis for item in positions)
        unrealized = sum(item.unrealized_pnl for item in positions)
        realized = sum(item.realized_pnl for item in positions)

        capital = number(
            self._nested(
                risk_payload,
                "capital",
                "account.capital",
                "account.equity",
                "portfolio.capital",
                "portfolio_value",
                "equity",
            )
        )
        if capital is None:
            capital = total_market_value if total_market_value else total_cost_basis

        cash = number(
            self._nested(
                risk_payload,
                "cash",
                "account.cash",
                "account.buying_power",
                "buying_power",
            ),
            0.0,
        ) or 0.0

        gross = sum(abs(item.market_value) for item in positions)
        long_exposure = sum(
            item.market_value
            for item in positions
            if item.market_value > 0
        )
        short_exposure = sum(
            abs(item.market_value)
            for item in positions
            if item.market_value < 0
        )
        net = long_exposure - short_exposure

        denominator = capital or gross or 1.0
        for item in positions:
            item.allocation_pct = (
                abs(item.market_value) / denominator * 100.0
            )

        sorted_allocations = sorted(
            (item.allocation_pct for item in positions),
            reverse=True,
        )
        largest_position = (
            sorted_allocations[0]
            if sorted_allocations
            else 0.0
        )
        top_three = sum(sorted_allocations[:3])

        portfolio_delta = sum(item.delta for item in positions)
        portfolio_gamma = sum(item.gamma for item in positions)
        portfolio_theta = sum(item.theta for item in positions)
        portfolio_vega = sum(item.vega for item in positions)

        max_drawdown = number(
            self._nested(
                risk_payload,
                "max_drawdown_pct",
                "risk.max_drawdown_pct",
                "metrics.max_drawdown_pct",
                "drawdown.max_drawdown_pct",
            )
        )
        value_at_risk = number(
            self._nested(
                risk_payload,
                "value_at_risk",
                "var",
                "risk.value_at_risk",
                "risk.var",
            )
        )
        expected_shortfall = number(
            self._nested(
                risk_payload,
                "expected_shortfall",
                "cvar",
                "risk.expected_shortfall",
                "risk.cvar",
            )
        )
        buying_power_utilization = number(
            self._nested(
                risk_payload,
                "buying_power_utilization_pct",
                "risk.buying_power_utilization_pct",
                "account.buying_power_utilization_pct",
            )
        )
        risk_utilization = number(
            self._nested(
                risk_payload,
                "risk_utilization_pct",
                "risk.utilization_pct",
                "utilization_pct",
            )
        )

        limits = [
            RiskLimit(
                name="Largest position",
                current_value=largest_position,
                limit_value=20.0,
                utilization_pct=largest_position / 20.0 * 100.0,
                status="BREACH" if largest_position > 20 else "OK",
                detail="Maximum single-position allocation.",
            ),
            RiskLimit(
                name="Top-three concentration",
                current_value=top_three,
                limit_value=50.0,
                utilization_pct=top_three / 50.0 * 100.0,
                status="BREACH" if top_three > 50 else "OK",
                detail="Combined allocation of the three largest positions.",
            ),
            RiskLimit(
                name="Gross exposure",
                current_value=gross,
                limit_value=capital,
                utilization_pct=gross / denominator * 100.0,
                status="BREACH" if gross > denominator else "OK",
                detail="Gross exposure compared with portfolio capital.",
            ),
        ]

        if buying_power_utilization is not None:
            limits.append(
                RiskLimit(
                    name="Buying power utilization",
                    current_value=buying_power_utilization,
                    limit_value=80.0,
                    utilization_pct=buying_power_utilization / 80.0 * 100.0,
                    status=(
                        "BREACH"
                        if buying_power_utilization > 80
                        else "OK"
                    ),
                    detail="Configured buying-power usage threshold.",
                )
            )

        if risk_utilization is not None:
            limits.append(
                RiskLimit(
                    name="Risk utilization",
                    current_value=risk_utilization,
                    limit_value=100.0,
                    utilization_pct=risk_utilization,
                    status=(
                        "BREACH"
                        if risk_utilization > 100
                        else "WARNING"
                        if risk_utilization > 80
                        else "OK"
                    ),
                    detail="Risk budget utilization.",
                )
            )

        breach_count = sum(
            1 for item in limits if item.status == "BREACH"
        )
        warning_count = sum(
            1 for item in limits if item.status == "WARNING"
        )
        risk_level = (
            "CRITICAL"
            if breach_count
            else "ELEVATED"
            if warning_count
            else "NORMAL"
            if positions
            else "UNKNOWN"
        )

        available_paths = [
            path
            for path in (position_path, risk_path)
            if path is not None
        ]
        latest_as_of = (
            max(timestamp(path) for path in available_paths)
            if available_paths
            else None
        )
        age = (
            max(
                0.0,
                (
                    datetime.now(timezone.utc) - latest_as_of
                ).total_seconds(),
            )
            if latest_as_of
            else None
        )

        if not positions:
            notices.append(
                "No portfolio position artifact was found."
            )
        if not risk_payload:
            notices.append(
                "No dedicated risk snapshot was found; derived risk metrics "
                "are based on position artifacts."
            )

        source_parts = []
        if position_path:
            source_parts.append(f"positions={position_path}")
        if risk_path:
            source_parts.append(f"risk={risk_path}")
        source_detail = (
            "; ".join(source_parts)
            if source_parts
            else "No portfolio or risk artifact available."
        )

        summary = PortfolioSummary(
            capital=capital or 0.0,
            cash=cash,
            gross_exposure=gross,
            net_exposure=net,
            long_exposure=long_exposure,
            short_exposure=short_exposure,
            total_market_value=total_market_value,
            total_cost_basis=total_cost_basis,
            unrealized_pnl=unrealized,
            realized_pnl=realized,
            total_pnl=unrealized + realized,
            return_pct=(
                (unrealized + realized) / total_cost_basis * 100.0
                if total_cost_basis
                else None
            ),
            open_positions=len(positions),
            winning_positions=sum(
                1 for item in positions if item.unrealized_pnl > 0
            ),
            losing_positions=sum(
                1 for item in positions if item.unrealized_pnl < 0
            ),
        )

        risk = RiskSnapshot(
            portfolio_delta=portfolio_delta,
            portfolio_gamma=portfolio_gamma,
            portfolio_theta=portfolio_theta,
            portfolio_vega=portfolio_vega,
            largest_position_pct=largest_position,
            top_three_concentration_pct=top_three,
            max_drawdown_pct=max_drawdown,
            value_at_risk=value_at_risk,
            expected_shortfall=expected_shortfall,
            buying_power_utilization_pct=buying_power_utilization,
            risk_utilization_pct=risk_utilization,
            risk_level=risk_level,
        )

        return PortfolioRiskResponse(
            generated_at=datetime.now(timezone.utc),
            available=bool(positions or risk_payload),
            stale=(
                age is None
                or age > self.stale_after_seconds
            ),
            age_seconds=round(age, 2) if age is not None else None,
            source_detail=source_detail,
            summary=summary,
            risk=risk,
            positions=positions,
            limits=limits,
            notices=notices,
        )
