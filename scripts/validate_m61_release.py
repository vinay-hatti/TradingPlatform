from __future__ import annotations

from importlib import import_module
from pathlib import Path

from trading_ai.database.base import Base
import trading_ai.stock_intelligence.models  # noqa: F401

EXPECTED_TABLES = {
    "stock_scanner_runs", "stock_scanner_candidates", "stock_scanner_timeframe_states",
    "stock_trade_plans", "stock_scanner_publications", "stock_support_resistance_levels",
    "stock_supply_demand_zones", "stock_accumulation_distribution_snapshots",
    "stock_breakout_snapshots", "stock_context_snapshots", "stock_opportunity_score_snapshots",
    "stock_position_intelligence_snapshots", "stock_outcome_observations",
    "stock_outcome_attribution_snapshots", "stock_probability_calibration_snapshots",
    "stock_management_policy_performance",
}


def main() -> None:
    missing = EXPECTED_TABLES - set(Base.metadata.tables)
    assert not missing, f"Missing SQLAlchemy tables: {sorted(missing)}"
    app_text = Path("src/trading_ai/production_api/app.py").read_text()
    assert "app.include_router(stock_intelligence_router)" in app_text
    router_text = Path("src/trading_ai/stock_intelligence/router.py").read_text()
    assert '@router.get("/candidates"' in router_text
    assert '@router.get("/candidates/{candidate_id}"' in router_text
    migration = Path("migrations/versions/m61_001_stock_intelligence.py").read_text()
    assert 'down_revision="20260803_m59"' in migration
    for name in (
        "multi_timeframe", "levels", "participation", "breakout", "context", "scoring",
        "position_intelligence", "orchestration", "publication", "option_integration", "outcome",
    ):
        import_module(f"trading_ai.stock_intelligence.{name}")
    print("Milestone 61 release validation passed.")


if __name__ == "__main__":
    main()
