from __future__ import annotations

from trading_ai.ui.adapters.common import AdapterResult, utcnow
from trading_ai.ui.services.dashboard_service import DashboardService


class OfflineAdapters:
    def _offline(self, name):
        return AdapterResult(
            name, False, None, "service unavailable", 1.0, utcnow()
        )

    def scanner(self): return self._offline("scanner")
    def regime(self): return self._offline("market_regime")
    def portfolio(self): return self._offline("portfolio")
    def risk(self): return self._offline("risk")
    def execution(self): return self._offline("execution")
    def market_data(self): return self._offline("market_data")


def main() -> None:
    snapshot = DashboardService(OfflineAdapters()).snapshot()
    assert snapshot.opportunities == []
    assert snapshot.market_regime == "Unavailable"
    assert all(item.status == "degraded" for item in snapshot.system_health)
    assert snapshot.notices
    print("All Milestone 31 Phase 2 degraded-mode assertions passed.")


if __name__ == "__main__":
    main()
