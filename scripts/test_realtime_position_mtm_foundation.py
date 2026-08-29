from __future__ import annotations

from datetime import datetime, timedelta, timezone
import tempfile
from pathlib import Path

from trading_ai.paper_trading.paper_position_profile import (
    PaperPositionProfile,
)
from trading_ai.position_monitoring.position_monitoring_profile import (
    RealTimePositionSnapshot,
    RealTimeQuoteSnapshot,
)
from trading_ai.position_monitoring.position_monitoring_serialization import (
    dumps,
)
from trading_ai.position_monitoring.position_monitoring_service import (
    PositionMonitoringService,
)
from trading_ai.position_monitoring.position_snapshot_mapper import (
    paper_position_to_realtime_snapshot,
)
from trading_ai.position_monitoring.position_snapshot_repository import (
    JsonPositionSnapshotRepository,
)


def main() -> None:
    now = datetime.now(timezone.utc)

    paper_position = PaperPositionProfile(
        position_id="paper-position-001",
        session_id="paper-session-001",
        account_id="PAPER-001",
        aggregate_id="agg-001",
        symbol="AAPL_CALL_200",
        asset_class="OPTION",
        side="LONG",
        quantity=2,
        average_cost=5.0,
        multiplier=100,
        market_price=5.0,
        market_value=1000.0,
        cost_basis=1000.0,
        realized_pnl=50.0,
        unrealized_pnl=0.0,
        total_commissions=2.6,
        metadata={
            "underlying_symbol": "AAPL",
            "sector": "TECHNOLOGY",
            "strategy_name": "LONG_CALL",
        },
    )
    mapped = paper_position_to_realtime_snapshot(paper_position)
    assert mapped.position_id == paper_position.position_id
    assert mapped.underlying_symbol == "AAPL"
    assert mapped.realized_pnl == 50.0

    short_position = RealTimePositionSnapshot(
        position_id="position-short-001",
        account_id="PAPER-001",
        symbol="MSFT",
        underlying_symbol="MSFT",
        asset_class="EQUITY",
        side="SHORT",
        quantity=-10,
        average_cost=400.0,
        multiplier=1,
        sector="TECHNOLOGY",
        strategy_name="SHORT_MOMENTUM",
    )

    quotes = {
        "AAPL_CALL_200": RealTimeQuoteSnapshot(
            symbol="AAPL_CALL_200",
            bid=6.45,
            ask=6.55,
            last=6.50,
            timestamp=now.isoformat(),
            source="paper-feed",
        ),
        "MSFT": RealTimeQuoteSnapshot(
            symbol="MSFT",
            bid=389.0,
            ask=391.0,
            last=390.0,
            timestamp=now.isoformat(),
            source="paper-feed",
        ),
    }

    with tempfile.TemporaryDirectory() as temp:
        repository = JsonPositionSnapshotRepository(
            Path(temp) / "snapshots.json"
        )
        service = PositionMonitoringService(repository=repository)
        decision = service.evaluate_and_publish(
            account_id="PAPER-001",
            starting_equity=100000.0,
            peak_equity=102000.0,
            cash_balance=95000.0,
            positions=(mapped, short_position),
            quotes=quotes,
            as_of=now,
            snapshot_id="snapshot-001",
        )
        assert decision.allowed
        assert decision.recommendation == "PUBLISH"
        assert decision.risk_state is not None

        state = decision.risk_state
        assert state.open_position_count == 2
        assert state.missing_quote_count == 0
        assert state.stale_position_count == 0
        assert state.realized_pnl == 50.0
        assert state.unrealized_pnl == 400.0
        assert state.total_pnl == 450.0
        assert state.current_equity == 100450.0
        assert state.intraday_drawdown == 1550.0
        assert round(state.drawdown_pct or 0.0, 4) == 0.0155
        assert state.long_exposure == 1300.0
        assert state.short_exposure == 3900.0
        assert state.gross_exposure == 5200.0
        assert state.net_exposure == -2600.0
        assert state.by_underlying["AAPL"] == 1300.0
        assert state.by_underlying["MSFT"] == -3900.0
        assert state.by_sector["TECHNOLOGY"] == -2600.0

        saved = repository.get("snapshot-001")
        assert saved is not None
        assert saved.total_pnl == 450.0
        latest = repository.latest_for_account("PAPER-001")
        assert latest is not None
        assert latest.snapshot_id == "snapshot-001"

        stale_quotes = dict(quotes)
        stale_quotes["MSFT"] = RealTimeQuoteSnapshot(
            symbol="MSFT",
            bid=389.0,
            ask=391.0,
            last=390.0,
            timestamp=(now - timedelta(seconds=90)).isoformat(),
            source="paper-feed",
        )
        stale = service.evaluate_and_publish(
            account_id="PAPER-001",
            starting_equity=100000.0,
            peak_equity=102000.0,
            cash_balance=95000.0,
            positions=(mapped, short_position),
            quotes=stale_quotes,
            as_of=now,
            snapshot_id="snapshot-stale",
        )
        assert not stale.allowed
        assert "QUOTE_FRESHNESS" in stale.rejection_reasons
        assert "STALE_QUOTE:MSFT" in stale.warnings
        assert repository.get("snapshot-stale") is None

        missing = service.evaluate_and_publish(
            account_id="PAPER-001",
            starting_equity=100000.0,
            peak_equity=102000.0,
            cash_balance=95000.0,
            positions=(mapped, short_position),
            quotes={"AAPL_CALL_200": quotes["AAPL_CALL_200"]},
            as_of=now,
            snapshot_id="snapshot-missing",
        )
        assert not missing.allowed
        assert "QUOTE_COVERAGE" in missing.rejection_reasons

        payload = dumps(decision)
        assert '"snapshot_id": "snapshot-001"' in payload
        assert '"gross_exposure": 5200.0' in payload
        assert '"recommendation": "PUBLISH"' in payload

    print(
        "All real-time position snapshot, mark-to-market, and "
        "intraday risk-state assertions passed."
    )


if __name__ == "__main__":
    main()
