from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path

from trading_ai.position_monitoring.portfolio_greeks_policy import (
    PortfolioGreeksMonitoringPolicy,
)
from trading_ai.position_monitoring.portfolio_greeks_profile import (
    RealTimePositionGreeks,
)
from trading_ai.position_monitoring.portfolio_greeks_repository import (
    JsonPortfolioGreeksRepository,
)
from trading_ai.position_monitoring.portfolio_greeks_serialization import (
    dumps,
)
from trading_ai.position_monitoring.portfolio_greeks_service import (
    PortfolioGreeksMonitoringService,
)


def main() -> None:
    now = datetime.now(timezone.utc)
    greeks = (
        RealTimePositionGreeks(
            position_id="position-aapl-long",
            symbol="AAPL_200C",
            underlying_symbol="AAPL",
            quantity=2,
            multiplier=100,
            side="LONG",
            delta=0.55,
            gamma=0.025,
            vega=0.20,
            theta=-0.08,
            rho=0.10,
            underlying_price=205.0,
            implied_volatility=0.30,
            option_price=6.0,
            timestamp=now.isoformat(),
            source="paper-greeks",
        ),
        RealTimePositionGreeks(
            position_id="position-aapl-short",
            symbol="AAPL_210C",
            underlying_symbol="AAPL",
            quantity=-1,
            multiplier=100,
            side="SHORT",
            delta=0.30,
            gamma=0.018,
            vega=0.15,
            theta=-0.05,
            rho=0.06,
            underlying_price=205.0,
            implied_volatility=0.28,
            option_price=2.5,
            timestamp=now.isoformat(),
            source="paper-greeks",
        ),
        RealTimePositionGreeks(
            position_id="position-msft-long",
            symbol="MSFT_400P",
            underlying_symbol="MSFT",
            quantity=1,
            multiplier=100,
            side="LONG",
            delta=-0.40,
            gamma=0.020,
            vega=0.22,
            theta=-0.07,
            rho=-0.08,
            underlying_price=395.0,
            implied_volatility=0.25,
            option_price=7.0,
            timestamp=now.isoformat(),
            source="paper-greeks",
        ),
    )

    with tempfile.TemporaryDirectory() as temp:
        repository = JsonPortfolioGreeksRepository(
            Path(temp) / "portfolio_greeks.json"
        )
        service = PortfolioGreeksMonitoringService(
            repository=repository
        )
        decision = service.evaluate_and_publish(
            account_id="PAPER-001",
            snapshot_id="greeks-snapshot-001",
            current_equity=100000.0,
            option_position_ids=tuple(
                item.position_id for item in greeks
            ),
            greeks=greeks,
            as_of=now,
        )
        assert decision.allowed
        assert decision.recommendation == "PUBLISH"
        assert decision.risk_state is not None

        state = decision.risk_state
        assert state.delta == 40.0
        assert state.gamma == 5.2
        assert state.vega == 47.0
        assert state.theta == -18.0
        assert state.rho == 6.0
        assert len(state.by_underlying) == 2
        assert len(state.surface_points) == 192
        assert state.worst_scenario_id is not None
        assert state.worst_scenario_loss >= 0
        assert state.worst_scenario_loss_pct_of_equity is not None

        aapl = next(
            item for item in state.by_underlying
            if item.underlying_symbol == "AAPL"
        )
        assert aapl.delta == 80.0
        assert aapl.gamma == 3.2
        assert len(aapl.surface_points) == 96

        saved = repository.get("greeks-snapshot-001")
        assert saved is not None
        assert saved.delta == 40.0
        latest = repository.latest_for_account("PAPER-001")
        assert latest is not None
        assert latest.snapshot_id == "greeks-snapshot-001"

        strict = PortfolioGreeksMonitoringService(
            policy=PortfolioGreeksMonitoringPolicy(
                maximum_absolute_delta=30.0,
                maximum_scenario_loss=100.0,
                maximum_scenario_loss_pct_of_equity=0.001,
            ),
            repository=repository,
        ).evaluate_and_publish(
            account_id="PAPER-001",
            snapshot_id="greeks-strict",
            current_equity=100000.0,
            option_position_ids=tuple(
                item.position_id for item in greeks
            ),
            greeks=greeks,
            as_of=now,
        )
        assert not strict.allowed
        assert "ABSOLUTE_DELTA" in strict.rejection_reasons
        assert (
            "MAXIMUM_SCENARIO_LOSS" in strict.rejection_reasons
            or "SCENARIO_LOSS_PCT_EQUITY"
            in strict.rejection_reasons
        )
        assert repository.get("greeks-strict") is None

        stale_greeks = (
            RealTimePositionGreeks(
                **{
                    **greeks[0].__dict__,
                    "timestamp": (
                        now - timedelta(seconds=120)
                    ).isoformat(),
                }
            ),
            *greeks[1:],
        )
        stale = service.evaluate_and_publish(
            account_id="PAPER-001",
            snapshot_id="greeks-stale",
            current_equity=100000.0,
            option_position_ids=tuple(
                item.position_id for item in stale_greeks
            ),
            greeks=stale_greeks,
            as_of=now,
        )
        assert not stale.allowed
        assert "GREEKS_FRESHNESS" in stale.rejection_reasons
        assert "STALE_GREEKS:position-aapl-long" in stale.warnings

        missing = service.evaluate_and_publish(
            account_id="PAPER-001",
            snapshot_id="greeks-missing",
            current_equity=100000.0,
            option_position_ids=(
                "position-aapl-long",
                "position-aapl-short",
                "position-msft-long",
                "position-missing",
            ),
            greeks=greeks,
            as_of=now,
        )
        assert not missing.allowed
        assert "GREEKS_COVERAGE" in missing.rejection_reasons

        payload = dumps(decision)
        assert '"snapshot_id": "greeks-snapshot-001"' in payload
        assert '"delta": 40.0' in payload
        assert '"recommendation": "PUBLISH"' in payload

    print(
        "All real-time portfolio Greeks, exposure-surface, and "
        "scenario-risk monitoring assertions passed."
    )


if __name__ == "__main__":
    main()
