from __future__ import annotations

from typing import Any


def strategy_position_payload(position: Any) -> dict[str, object]:
    """Convert an existing strategy_engine PortfolioPosition into registry fields."""
    return {
        "symbol": position.symbol,
        "strategy_id": str(position.metadata.get("strategy_id") or f"{position.symbol}:{position.strategy}"),
        "strategy_type": position.strategy,
        "direction": position.direction,
        "quantity": position.contracts,
        "entry_price": position.capital_required / max(position.contracts, 1) / 100.0,
        "capital_committed": position.capital_required,
        "maximum_loss": position.maximum_loss,
        "maximum_profit": position.expected_profit,
        "sector": position.sector,
        "industry": position.industry,
        "correlation_group": position.correlation_group,
        "metadata": {
            "ranking_score": position.ranking_score,
            "strategy_score": position.strategy_score,
            "portfolio_fit_score": position.portfolio_fit_score,
            "delta": position.delta,
            "gamma": position.gamma,
            "theta": position.theta,
            "vega": position.vega,
            "rho": position.rho,
        },
    }
