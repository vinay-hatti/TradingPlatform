from datetime import date, datetime, timezone
from types import SimpleNamespace

from trading_ai.published_state.profile import PublishedMarketState
from trading_ai.strategy_engine.institutional_decision_service import InstitutionalDecisionService


class FakeResolver:
    def require(self):
        return PublishedMarketState(
            publication_name="current_market_state",
            run_id="ingestion-47",
            published_at=datetime(2026, 7, 25, 21, 0, tzinfo=timezone.utc),
            as_of_date=date(2026, 7, 23),
            market_intelligence_timestamp=datetime(2026, 7, 25, 20, 0, tzinfo=timezone.utc),
            option_snapshot_timestamp=datetime(2026, 7, 25, 17, 45, tzinfo=timezone.utc),
            option_snapshot_id="polygon-test-snapshot",
            readiness_status="DEGRADED",
            scanner_ready=True,
            decision_context_ready=True,
            details={"option_snapshot_completeness_pct": 99.51},
            age_seconds=60.0,
            degraded=True,
        )


class FakeEngine:
    def run(self, request):
        decision = SimpleNamespace(symbol="AAPL")
        return SimpleNamespace(
            decisions=[decision],
            warnings=[],
            metadata={},
        )


def main():
    service = InstitutionalDecisionService(
        engine=FakeEngine(),
        published_state_resolver=FakeResolver(),
        enforce_published_state=True,
    )
    result = service.run(SimpleNamespace())
    lineage = result.metadata["published_market_state"]
    assert lineage["ingestion_run_id"] == "ingestion-47"
    assert lineage["option_snapshot_id"] == "polygon-test-snapshot"
    assert lineage["published_state_degraded"] is True
    assert result.decisions[0].market_as_of_date == "2026-07-23"
    assert result.decisions[0].option_snapshot_completeness_pct == 99.51
    assert any("DEGRADED" in warning for warning in result.warnings)

    legacy = InstitutionalDecisionService(engine=FakeEngine())
    legacy_result = legacy.run(SimpleNamespace())
    assert legacy_result.metadata["published_market_state"]["publication_status"] == "NOT_ENFORCED"

    bypass = InstitutionalDecisionService(
        engine=FakeEngine(),
        enforce_published_state=True,
        allow_unpublished_state=True,
    )
    bypass_result = bypass.run(SimpleNamespace())
    assert bypass_result.metadata["published_market_state"]["bypassed"] is True
    assert any("bypassed" in warning.lower() for warning in bypass_result.warnings)
    print("Milestone 47 Phase 3 institutional-decision published-state assertions passed.")


if __name__ == "__main__":
    main()
