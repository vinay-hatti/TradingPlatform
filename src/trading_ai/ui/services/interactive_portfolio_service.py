from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from trading_ai.ui.models.interactive_portfolio import (
    ExposureCell,
    PortfolioPosition,
    PortfolioSummary,
    RebalanceConstraint,
    RebalanceProposal,
    ScenarioPoint,
    ScenarioRequest,
)


class InteractivePortfolioService:
    def __init__(self, state_path: str | Path = "reports/ui/paper_trading_state.json"):
        self.state_path = Path(state_path)

    @staticmethod
    def _now():
        return datetime.now(timezone.utc)

    @staticmethod
    def _number(value, default=0.0):
        try:
            return float(value if value is not None else default)
        except (TypeError, ValueError):
            return default

    def _raw_positions(self) -> list[dict]:
        if not self.state_path.exists():
            return []
        payload = json.loads(self.state_path.read_text(encoding="utf-8"))
        if isinstance(payload, list):
            return payload
        for key in ("positions", "paper_positions", "open_positions"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
            if isinstance(value, dict):
                return list(value.values())
        accounts = payload.get("accounts")
        if isinstance(accounts, dict):
            rows = []
            for account_id, account in accounts.items():
                for item in account.get("positions", []):
                    rows.append({"account_id": account_id, **item})
            return rows
        return []

    def positions(self, account_id: str = "paper-account") -> list[PortfolioPosition]:
        result = []
        for index, row in enumerate(self._raw_positions()):
            row_account = str(row.get("account_id") or account_id)
            if account_id and row_account != account_id:
                continue
            quantity = self._number(row.get("quantity", row.get("qty", 0)))
            average = self._number(row.get("average_price", row.get("avg_price", 0)))
            mark = self._number(row.get("mark_price", row.get("current_price", row.get("last_price", average))))
            instrument = str(row.get("instrument_type", "OPTION" if row.get("option_type") else "EQUITY")).upper()
            multiplier = self._number(row.get("multiplier", 100 if instrument == "OPTION" else 1), 1)
            market_value = self._number(row.get("market_value"), quantity * mark * multiplier)
            pnl = self._number(row.get("unrealized_pnl"), (mark - average) * quantity * multiplier)
            option_type = row.get("option_type")
            if option_type:
                option_type = str(option_type).upper()
                option_type = "CALL" if option_type in ("C", "CALLS") else "PUT" if option_type in ("P", "PUTS") else option_type
            result.append(PortfolioPosition(
                position_id=str(row.get("position_id", row.get("id", f"position-{index}"))),
                account_id=row_account,
                symbol=str(row.get("symbol", row.get("underlying_symbol", "UNKNOWN"))).upper(),
                instrument_type="OPTION" if instrument == "OPTION" else "EQUITY",
                quantity=quantity,
                average_price=average,
                mark_price=mark,
                multiplier=multiplier,
                option_expiry=row.get("option_expiry", row.get("expiry")),
                option_strike=self._number(row.get("option_strike", row.get("strike"))) or None,
                option_type=option_type if option_type in ("CALL", "PUT") else None,
                delta=self._number(row.get("delta")),
                gamma=self._number(row.get("gamma")),
                theta=self._number(row.get("theta")),
                vega=self._number(row.get("vega")),
                implied_volatility=self._number(row.get("implied_volatility", row.get("iv"))),
                underlying_price=self._number(row.get("underlying_price", row.get("spot_price"))),
                market_value=market_value,
                unrealized_pnl=pnl,
            ))
        return result

    def summary(self, account_id: str = "paper-account") -> PortfolioSummary:
        positions = self.positions(account_id)
        greek = lambda p, name: getattr(p, name) * p.quantity * p.multiplier
        return PortfolioSummary(
            generated_at=self._now(),
            account_id=account_id,
            total_market_value=sum(p.market_value for p in positions),
            total_unrealized_pnl=sum(p.unrealized_pnl for p in positions),
            gross_exposure=sum(abs(p.market_value) for p in positions),
            net_exposure=sum(p.market_value for p in positions),
            net_delta=sum(greek(p, "delta") for p in positions),
            net_gamma=sum(greek(p, "gamma") for p in positions),
            net_theta=sum(greek(p, "theta") for p in positions),
            net_vega=sum(greek(p, "vega") for p in positions),
            long_positions=sum(1 for p in positions if p.quantity > 0),
            short_positions=sum(1 for p in positions if p.quantity < 0),
            symbols=len({p.symbol for p in positions}),
            positions=positions,
        )

    def exposure_matrix(self, account_id: str = "paper-account") -> list[ExposureCell]:
        cells = {}
        for p in self.positions(account_id):
            key = (p.symbol, p.option_expiry or "EQUITY")
            cell = cells.setdefault(key, {
                "delta": 0, "gamma": 0, "theta": 0, "vega": 0,
                "market_value": 0, "unrealized_pnl": 0,
            })
            scale = p.quantity * p.multiplier
            for name in ("delta", "gamma", "theta", "vega"):
                cell[name] += getattr(p, name) * scale
            cell["market_value"] += p.market_value
            cell["unrealized_pnl"] += p.unrealized_pnl
        return [
            ExposureCell(symbol=s, expiration=e, **values)
            for (s, e), values in sorted(cells.items())
        ]

    def scenarios(self, request: ScenarioRequest) -> list[ScenarioPoint]:
        summary = self.summary(request.account_id)
        points = []
        reference = sum(
            abs(p.underlying_price * p.quantity * p.multiplier)
            for p in summary.positions if p.underlying_price
        ) or max(summary.gross_exposure, 1)
        for shock in request.underlying_shocks_pct:
            underlying_move = reference * shock
            delta_pnl = summary.net_delta * (underlying_move / reference)
            gamma_pnl = 0.5 * summary.net_gamma * (underlying_move / reference) ** 2
            for vol in request.volatility_shocks_points:
                vega_pnl = summary.net_vega * vol
                for days in request.days_forward:
                    theta_pnl = summary.net_theta * days
                    pnl = delta_pnl + gamma_pnl + vega_pnl + theta_pnl
                    points.append(ScenarioPoint(
                        underlying_shock_pct=shock,
                        volatility_shock_points=vol,
                        days_forward=days,
                        estimated_pnl=pnl,
                        estimated_market_value=summary.total_market_value + pnl,
                        delta_pnl=delta_pnl,
                        gamma_pnl=gamma_pnl,
                        vega_pnl=vega_pnl,
                        theta_pnl=theta_pnl,
                    ))
        return points

    def rebalance(self, account_id: str, constraints: RebalanceConstraint) -> RebalanceProposal:
        summary = self.summary(account_id)
        target = max(-constraints.max_abs_delta, min(constraints.max_abs_delta, summary.net_delta))
        change = target - summary.net_delta
        symbol_exposure = {}
        for p in summary.positions:
            symbol_exposure[p.symbol] = symbol_exposure.get(p.symbol, 0) + abs(p.market_value)
        symbol = max(symbol_exposure, key=symbol_exposure.get) if symbol_exposure else "SPY"
        spot = next((p.underlying_price for p in summary.positions if p.symbol == symbol and p.underlying_price), 0) or 1
        quantity = max(1, round(abs(change)))
        side = "BUY" if change > 0 else "SELL"
        warnings = ["Proposal requires Phase 3 preview and independent approval before submission."]
        if abs(summary.net_vega) > constraints.max_abs_vega:
            warnings.append("Portfolio vega exceeds configured tolerance; delta hedge alone is insufficient.")
        concentration = (symbol_exposure.get(symbol, 0) / constraints.account_equity) if constraints.account_equity else 0
        rationale = [
            f"Current portfolio delta is {summary.net_delta:.2f}.",
            f"Configured absolute delta limit is {constraints.max_abs_delta:.2f}.",
            f"Largest gross symbol exposure is {symbol}.",
        ]
        return RebalanceProposal(
            proposal_id=f"rebalance-{uuid4().hex[:16]}",
            created_at=self._now(),
            account_id=account_id,
            objective="Reduce portfolio delta toward configured tolerance",
            current_delta=summary.net_delta,
            target_delta=target,
            estimated_delta_change=change,
            estimated_notional=quantity * spot,
            symbol=symbol,
            side=side,
            quantity=quantity,
            rationale=rationale,
            warnings=warnings,
            phase3_handoff={
                "environment": "PAPER",
                "account_id": account_id,
                "strategy_name": f"Delta Rebalance — {symbol}",
                "order_type": "MARKET",
                "contracts": quantity,
                "underlying_price": spot,
                "reason": "Phase 4 governed portfolio rebalance proposal",
                "requires_phase3_preview": True,
                "requires_four_eye_approval": True,
            },
        )
