from __future__ import annotations

from collections import defaultdict
from typing import Any


class PortfolioRiskExposureService:
    def evaluate(self, registry: dict[str, Any]) -> dict[str, Any]:
        positions = [p for p in registry.get("positions", []) if str(p.get("status", "")).upper() == "OPEN"]
        nav = float(registry.get("net_liquidation_value", 0.0) or 0.0)
        committed = sum(float(p.get("capital_committed", 0.0) or 0.0) for p in positions)

        aggregates = {
            "delta": sum(float(p.get("delta", 0.0) or 0.0) for p in positions),
            "gamma": sum(float(p.get("gamma", 0.0) or 0.0) for p in positions),
            "theta": sum(float(p.get("theta", 0.0) or 0.0) for p in positions),
            "vega": sum(float(p.get("vega", 0.0) or 0.0) for p in positions),
            "rho": sum(float(p.get("rho", 0.0) or 0.0) for p in positions),
            "maximum_loss": sum(max(0.0, float(p.get("maximum_loss", 0.0) or 0.0)) for p in positions),
            "unrealized_pnl": sum(float(p.get("unrealized_pnl", 0.0) or 0.0) for p in positions),
            "realized_pnl": sum(float(p.get("realized_pnl", 0.0) or 0.0) for p in registry.get("positions", [])),
        }

        dimensions: dict[str, dict[str, float]] = {
            "symbol": defaultdict(float),
            "sector": defaultdict(float),
            "strategy": defaultdict(float),
            "direction": defaultdict(float),
            "correlation_group": defaultdict(float),
        }
        for position in positions:
            capital = float(position.get("capital_committed", 0.0) or 0.0)
            dimensions["symbol"][str(position.get("symbol", "UNKNOWN")).upper()] += capital
            dimensions["sector"][str(position.get("sector", "UNKNOWN")).upper()] += capital
            dimensions["strategy"][str(position.get("strategy_type", "UNKNOWN")).upper()] += capital
            dimensions["direction"][str(position.get("direction", "UNKNOWN")).upper()] += capital
            key = str(position.get("correlation_group", "") or "UNGROUPED").upper()
            dimensions["correlation_group"][key] += capital

        concentration: dict[str, Any] = {}
        denominator = committed if committed > 0 else 1.0
        for name, values in dimensions.items():
            rows = [
                {"key": key, "capital_committed": round(value, 2), "capital_pct": round(value / denominator * 100.0, 4)}
                for key, value in sorted(values.items(), key=lambda item: item[1], reverse=True)
            ]
            concentration[name] = rows
            concentration[f"largest_{name}_pct"] = rows[0]["capital_pct"] if rows else 0.0

        illiquid = 0.0
        for position in positions:
            metadata = position.get("metadata", {}) or {}
            volume = float(metadata.get("option_volume", metadata.get("volume", 0.0)) or 0.0)
            oi = float(metadata.get("open_interest", 0.0) or 0.0)
            spread = float(metadata.get("spread_pct", 0.0) or 0.0)
            if volume < 10 or oi < 50 or spread > 0.25:
                illiquid += float(position.get("capital_committed", 0.0) or 0.0)
        liquidity = {
            "illiquid_capital": round(illiquid, 2),
            "illiquid_capital_pct": round(illiquid / denominator * 100.0, 4) if committed else 0.0,
            "liquid_capital": round(max(0.0, committed - illiquid), 2),
        }
        return {
            "positions": positions,
            "nav": nav,
            "cash_balance": float(registry.get("cash_balance", 0.0) or 0.0),
            "capital_committed": round(committed, 2),
            "capital_utilization_pct": round(committed / nav * 100.0, 4) if nav > 0 else 0.0,
            "cash_reserve_pct": round(float(registry.get("cash_balance", 0.0) or 0.0) / nav * 100.0, 4) if nav > 0 else 0.0,
            "aggregates": aggregates,
            "concentration": concentration,
            "liquidity": liquidity,
        }
