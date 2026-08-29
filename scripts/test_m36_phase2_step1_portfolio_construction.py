import json
import tempfile
from pathlib import Path

from trading_ai.portfolio_management.construction_service import PortfolioConstructionOrchestrationService


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        registry = root / "registry.json"
        registry.write_text(json.dumps({
            "account": {"portfolio_id": "PRIMARY", "initial_capital": 100000},
            "cash_balance": 100000,
            "net_liquidation_value": 100000,
            "positions": [],
            "cash_ledger": [],
        }), encoding="utf-8")
        candidates = root / "candidates.json"
        candidates.write_text(json.dumps({"ranked_opportunities": [
            {"ranking_score": 92, "raw_ranking_score": 94, "allowed": True, "selected": True, "action": "TRADE", "opportunity": {
                "symbol": "AAPL", "strategy": "BULL_CALL_SPREAD", "direction": "CALL", "market_regime": "TREND_UP",
                "strategy_score": 90, "portfolio_fit_score": 85, "capital_required": 250, "maximum_loss": 250,
                "expected_profit": 200, "expected_return_pct": 80, "readiness": "READY", "recommendation": "TRADE",
                "sector": "TECHNOLOGY", "correlation_group": "MEGA_CAP", "risk_profile": "DEFINED_RISK",
                "greeks": {"delta": 20, "gamma": 1, "theta": -4, "vega": 12, "rho": 2}
            }},
            {"ranking_score": 45, "raw_ranking_score": 45, "allowed": True, "selected": True, "action": "WATCHLIST", "opportunity": {
                "symbol": "XYZ", "strategy": "LONG_CALL", "direction": "CALL", "strategy_score": 50,
                "portfolio_fit_score": 20, "capital_required": 100, "maximum_loss": 100, "readiness": "RESEARCH_ONLY", "recommendation": "WATCHLIST"
            }}
        ]}), encoding="utf-8")
        output = root / "construction.json"
        run = PortfolioConstructionOrchestrationService().construct_file(candidates, registry, output)
        assert run.candidate_count == 2
        assert run.eligible_candidate_count == 1
        assert run.proposed_position_count == 1
        assert run.rejected_candidate_count >= 1
        assert run.proposed_positions[0]["symbol"] == "AAPL"
        assert output.exists()
    print("Milestone 36 Phase 2 Step 1 portfolio-construction assertions passed.")


if __name__ == "__main__":
    main()
