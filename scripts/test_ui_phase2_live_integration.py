from __future__ import annotations

from trading_ai.ui.adapters.common import AdapterResult, utcnow
from trading_ai.ui.models.dashboard import DashboardSnapshot
from trading_ai.ui.services.dashboard_service import DashboardService


class FakeAdapters:
    def scanner(self):
        return AdapterResult(
            "scanner", True,
            [
                {
                    "symbol": "SPY",
                    "signal": "CALL",
                    "score": 94,
                    "probability_of_profit": 0.82,
                    "market_regime": "Bull Trend",
                    "contract_ticker": "O:SPY260821C00700000",
                }
            ],
            "ok", 4.2, utcnow(),
        )

    def regime(self):
        return AdapterResult(
            "market_regime", True,
            {"regime": "Bull Trend"},
            "ok", 2.1, utcnow(),
        )

    def portfolio(self):
        return AdapterResult(
            "portfolio", True,
            {"active_positions": 3, "daily_pnl": 1250.50},
            "ok", 3.5, utcnow(),
        )

    def risk(self):
        return AdapterResult(
            "risk", True,
            {"capital_at_risk_pct": 12.4, "risk_mode": "Moderate"},
            "ok", 3.8, utcnow(),
        )

    def execution(self):
        return AdapterResult(
            "execution", True,
            {"average_slippage_pct": 0.18},
            "ok", 2.8, utcnow(),
        )

    def market_data(self):
        return AdapterResult(
            "market_data", True,
            {"market_status": "Open"},
            "ok", 1.7, utcnow(),
        )


def main() -> None:
    snapshot = DashboardService(FakeAdapters()).snapshot()
    assert isinstance(snapshot, DashboardSnapshot)
    assert snapshot.market_regime == "Bull Trend"
    assert snapshot.market_status == "Open"
    assert snapshot.risk_mode == "Moderate"
    assert snapshot.ai_confidence == 0.82
    assert snapshot.opportunities[0].symbol == "SPY"
    assert len(snapshot.system_health) == 6
    assert all(item.status == "healthy" for item in snapshot.system_health)
    print("All Milestone 31 Phase 2 live-integration assertions passed.")


if __name__ == "__main__":
    main()
